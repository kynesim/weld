"""
Generic operations
"""

import os
import re
import shutil
import tempfile
import traceback
import groan

try:
    import cPickle as pickle
except:
    import pickle

import welded.git as git
import welded.headers as headers
import welded.layout as layout

from welded.utils import GiveUp, run_silently, dynamic_load, run_to_stdout

def update_base(spec, base):
    """
    Update the local base checkout
    """
    b = layout.base_repo(spec.base_dir, base.name)
    if (not os.path.exists(b)):
        os.makedirs(b)
    g = os.path.join(b, ".git")
    if (not os.path.exists(g)):
        git.clone(b, base.uri, base.branch, base.tag, base.rev)
    # Now update ..
    git.pull(b, base.uri, base.branch, base.tag, base.rev)
    
def query_head_of_base(spec, base_obj):
    """
    Query the head of this base
    """
    return git.query_current_commit_id(layout.base_repo(spec.base_dir, base_obj.name))

def delete_seams(spec, base_obj, seams, base_commit):
    """
    Take the array of seam objects in seams and delete them from base_obj in spec, then
    commit the result.
    """
    # Actually remarkably easy. First, delete stuff.
    if (len(seams) == 0): 
        # It's a no-op
        return

    for s in seams:
        to_zap = os.path.join(spec.base_dir, s.dest)
        print("W: Remove %s\n"%to_zap)
        shutil.rmtree(to_zap)
        git.add_in_subdir(spec.base_dir, s.dest )
    
    # Now create the header for all this ..
    hdr = headers.seam_op(headers.SEAM_VERB_DELETED, base_obj ,seams, base_commit)
    # .. aaand commit.
    git.commit(spec.base_dir, hdr, [])

def rewrite_diff(infile, cid, changes):
    """
    Rewrite the diff in infile to account for the given changes. Files outside
    those seams are removed from the diff
    
    @return (bool, Tempfile) - the bool is True if there are any files left that
            we care about.
    """
    infile.file.seek(0)
    outfile = tempfile.NamedTemporaryFile(prefix="weldcid%s-out"%cid, delete = False)
    rec = re.compile(r'^diff\s+--git\s+a/([^\s]+)\s+b/([^\s]+)\s*$')
    are_any = False

    # State:
    #        1 - echoing a diff to output.
    #        2 - eliding a diff from output.
    state = 1
    while True:
        l = infile.file.readline()
        if (len(l) == 0):
            return (are_any, outfile)
        m = rec.match(l)
        if (m is None):
            if (state == 1):
                l = re.sub(r'^(\s*)X-Weld-State:', r'\1XX-Weld-State:', l)
                if (len(l) > 5):
                    if (l[:5] == '--- a' or l[:5] == '+++ b'):
                        # It's a diff line
                        for s in changes:
                            if (s.source is not None and len(s.source) > 0):
                                src_check = s.source + "/"
                            else:
                                src_check = ""
                            if (l[6:].startswith(src_check)):
                                x = len(src_check)
                                l = l[:6] + s.dest + '/' + l[(6+x):]
                                break

                outfile.file.write(l)
        else:
            # Right. Now, is the destination part of any of our seams?
            src_file = m.group(1)
            dest_file = m.group(2)
            state = 2
            for s in changes:
                # Need to make sure it is a '/' so that we don't get
                # unwanted prefix matches.
                if (s.source is not None and len(s.source) > 0): 
                    src_check = s.source + "/"
                else:
                    src_check = ""
                if (dest_file.startswith(src_check) and src_file.startswith(src_check)):
                    # It's going to be in this seam. 
                    # Git models moves as "remove A, put B", so there is no
                    #  moving in the filenames, we can just replace the paths.
                    l = len(src_check)
                    src_file = "%s/%s"%(s.dest, src_file[l:])
                    dest_file = "%s/%s"%(s.dest, dest_file[l:])
                    l = "diff --git a/%s b/%s\n"%(src_file, dest_file)
                    outfile.file.write(l)
                    are_any = True
                    state = 1
                    break
                    

    return (are_any, outfile)

        
def modify_seams(spec, base_obj, changes, old_commit, new_commit):
    """
    Take the array of seam objects in changes and apply the changes from old_commit to
    new_commit to them
    """
    if (len(changes) > 0):
        commits = git.list_changes(layout.base_repo(spec.base_dir, base_obj.name), old_commit, new_commit)
        print("W: Replaying %d commits from %s in %d seams .."%(len(commits), base_obj.name, len(changes)))
        print("W: Replay (squashed) changes. Extract diff\n")
        temp = git.show_diff(layout.base_repo(spec.base_dir, base_obj.name), old_commit, new_commit)
        print("W: Rename diff .. \n")
        (are_any, temp2) = rewrite_diff(temp, new_commit, changes)
        n = temp.name
        temp.close()
        print("W: Apply diff .. \n")
        n = temp2.name
        temp2.close()
        if (are_any):
            git.apply_patch_file(spec.base_dir, temp2.name)
        os.remove(n)
        print("W: Add .. \n")
        for s in changes:
            git.add_in_subdir(spec.base_dir, os.path.join(spec.base_dir, s.get_dest()))
        print("W: Commit .. \n")
        hdr = headers.ported_commit(base_obj, changes, new_commit)
        git.commit(spec.base_dir, hdr, [] )
            
def add_seams(spec, base_obj, seams, base_commit):
    """
    Take the array of seam objects in seams and create the new seams in seams.
    """
    if (len(seams) == 0): 
        # It's a no-op
        return

    for s in seams:
        print("W: Creating new seam (%s->%s) from %s"%(s.get_source(), s.get_dest(), base_obj.name))
        # Really, just copy the directories over. If there are files already there, keep them.
        src = os.path.join(layout.base_repo(spec.base_dir, base_obj.name), s.get_source())
        dest = os.path.join(spec.base_dir, s.get_dest())
        try:
            os.makedirs(dest)
        except Exception:
            pass

        # XXX TODO XXX TODO XXX TODO    .git directories and submodules
        # Since we're copying from the clone in our .weld directory, if the
        # source is the "top level" of said clone, then it will contain a .git
        # directory, which we do not want to copy.
        #
        # However, if the source is *not* the top level of its clone, and there
        # is a .git directory, well, that's distincly odd, but presumably we
        # might want to honour it? If we do, oddness abounds (!), and if we
        # don't, then we're not copying what is there. So what to do...
        #
        # ...the simplest thing is, of course, just to ignore all .git
        # directories, and wait for someone with a pathological case to
        # grumble to us...
        #
        # Hmm. I have a feeling if we do that we're explicitly not supporting
        # submodules, which is perhaps a Good Thing, without thinking more
        # about it, not least because a submodule looks like:
        #
        #   <top-level>/
        #      .git/...
        #      .gitmodules      -- names the submodules
        #      <stuff>
        #         <submodule>/
        #            .git
        #
        # which means that the .gitmodules is required to make sense of the
        # submodule as such, and specifically to give context to the .git
        # directory therein. So I think that the simplest thing, for now, is
        # to explicitly NOT support submodules, and ignore all .git
        # directories.
        #
        # (NB: this all goes awry if we DO have a submodule and copy its
        # .submodule file but not the submodule .git directories. So this
        # definitely needs more work)
        #
        # (and, for extra points, what is our policy on .gitignore files at
        # this level? Is the naive answer of just copying them good enough?)

        # Now just rsync it all over
        run_silently(["rsync", "-avz", "--exclude", ".git/", os.path.join(src, "."), os.path.join(dest, ".")])
        # Make sure you add all the files in the subdirectory
        git.add_in_subdir(spec.base_dir, dest)
    # Now commit them with an appropriate header.
    hdrs = headers.seam_op(headers.SEAM_VERB_ADDED, base_obj, seams, base_commit)
    git.commit(spec.base_dir, hdrs, [] )

FINISH_PULL_PREFIX="import pull\n" + \
    "def go(spec, opts):\n"
FINISH_PULL_SUFFIX="\n"

FINISH_PUSH_PREFIX="import push\n" + \
    "def go(spec, opts):"
FINISH_PUSH_SUFFIX="\n"

VERB_PREFIX="import ops\n" + \
    "def go(spec, opts):\n"
VERB_SUFFIX="\n"

def have_cmd(base_dir):
    try:
        state = read_state_data_with_file(base_dir)
        if ('cmd' in state):
            return state['cmd']
        else:
            return 'unknown'
    except:
        pass
    return None

def write_finish_pull(spec, cmds_ok, cmds_abort):
    with open(layout.complete_file(spec.base_dir), "w+") as f:
        f.write(FINISH_PULL_PREFIX)
        f.write(cmds_ok)
        f.write(FINISH_PULL_SUFFIX)
    with open(layout.abort_file(spec.base_dir), "w+") as f:
        f.write(FINISH_PULL_PREFIX)
        f.write(cmds_abort)
        f.write(FINISH_PULL_SUFFIX)

def write_finish_push(spec, cmds_ok, cmds_abort):
    with open(layout.complete_file(spec.base_dir), "w+") as f:
        f.write(FINISH_PUSH_PREFIX)
        f.write(cmds_ok)
        f.write(FINISH_PUSH_SUFFIX)
    with open(layout.abort_file(spec.base_dir), "w+") as f:
        f.write(FINISH_PUSH_PREFIX)
        f.write(cmds_abort)
        f.write(FINISH_PUSH_SUFFIX)

def clear_verbs(spec):
    """
    Clear all verbs, pending and real.
    """
    shutil.rmtree(layout.verb_dir(spec.base_dir))
    shuilt.rmtree(layout.pending_verb_dir(spec.base_dir))

def verb_me(spec, module, fn, verb = None):
    """
    Given a verb, a module and a function, import that module and call the function when
    the verb happens, with the current spec and opts as arguments
    """
    if verb is None:
        verb = fn
    return make_verb_available(spec, verb, [ 'import %s'%module,
                                             '%s.%s(spec, opts)'%(module, fn) ])


def make_verb_available(spec, cmd, code):
    try:
        os.mkdir(layout.pending_verb_dir(spec.base_dir), 0755)
    except:
        pass

    with open(layout.pending_verb_file(spec.base_dir, cmd), "w+") as f:
        f.write(VERB_PREFIX)
        for l in code:
            f.write(' ' + l + '\n')
        f.write(VERB_SUFFIX)

def write_verbs(spec, cmds, erase_old_verbs = True):
    """
    Writes a finish spec. cmds is a hash of verb -> some text to be evaluated
    on that verb

    The finish spec is written in the pending verbs directory.
    """
    if erase_old_verbs:
        shutil.rmtree(layout.pending_verb_dir(spec.base_dir))

    try:
        os.mkdir(layout.pending_verb_dir(spec.base_dir), 0755)
    except:
        pass

    for (cmd, text) in cmds:
        with open(layout.pending_verb_file(spec.base_dir, cmd), "w+") as f:
            f.write(VERB_PREFIX)
            f.write(cmds)
            f.write(VERB_SUFFIX)


def repeat_verbs(spec):
    """
    Repeat the previous verbs
    """
    vb =layout.verb_dir(spec.base_dir)
    nvb = layout.pending_verb_dir(spec.base_dir)
    if os.path.exists(vb):
        if os.path.exists(nvb):
            shutil.rmtree(nvb)
        shutil.copytree(vb,nvb)

def next_verbs(spec):
    """
    Remove the currently available verbs and replace them with the
    pending verbs
    """
    #traceback.print_stack()
    vb =layout.verb_dir(spec.base_dir)
    nvb = layout.pending_verb_dir(spec.base_dir)
    if os.path.exists(vb):
        shutil.rmtree(layout.verb_dir(spec.base_dir))
    if os.path.exists(nvb):
        shutil.move(nvb, vb)


def do(spec, verb, opts, do_next_verbs = False):
    """
    Perform a verb
    """
    c = layout.verb_file(spec.base_dir, verb)
    if (os.path.exists(c)):
        f = dynamic_load(c, no_pyc = True)
        f.go(spec, opts)
        # Success!
        if do_next_verbs:
            next_verbs(spec)
    else:
        raise GiveUp("You see no '%s' here. %s "%(verb, groan.with_demise()))

def available_verb(spec, verb):
    return os.path.exists(layout.verb_file(spec.base_dir, verb))

def list_verbs(spec):
    return list_verbs_from(spec.base_dir)

def list_verbs_from(base_dir):
    c = layout.verb_dir(base_dir)
    rv = [ ]
    if (os.path.exists(c)):
        for l in os.listdir(c):
            if (l[0] != '.'):
                dot = l.find('.')
                rv.append(l[:dot])

    return rv

def count(filename):
    contents = ""
    try:
        with open(filename, 'rb') as fin:
            contents = fin.read().trim()
    except Exception:
        pass
    contents = contents + "1\n"
    try:
        with open(filename, 'wb') as fout:
            fout.write("%s"%contents)
    except Exception as e:
        traceback.print_exc()
        raise GiveUp("Cannot increment counter in %s - %s"%(filename, e))

def spurious_modification(w):
    """
    Spuriously modify a weld and git add it so that your commit is never empty
    """
    a_file = layout.count_file(w.base_dir)
    count(a_file)
    git.add(w.base_dir, [ a_file ] )

def read_state_data(spec):
    return read_state_data_with_file(spec.base_dir)

def read_state_data_with_file(base_dir):
    with open(layout.state_data_file(base_dir), 'r') as f:
        some_input = f.read()
    return pickle.loads(some_input)

def write_state_data(spec, data):
    with open(layout.state_data_file_x(spec.base_dir), 'w') as f:
        f.write(pickle.dumps(data))
    os.rename(layout.state_data_file_x(spec.base_dir),
              layout.state_data_file(spec.base_dir))

def ensure_state_dir(weld_dir):
    try:
        os.mkdir(layout.state_dir(weld_dir), 0755)
    except:
        pass

def list_changes(where, cid_from, cid_to):
    return git.list_changes(where, cid_from, cid_to, opts = [ '--topo-order' ])

def log_changes(where, cid_from, cid_to, directories, style, verbose = False):
    if (style == "long"):
        return git.what_changed(where, 
                                cid_from,
                                cid_to,
                                directories,
                                verbose = verbose)
    elif (style == "oneline"):
        return git.log_between(where,
                               cid_from,
                               cid_to,
                               directories,
                               verbose = verbose)
    elif (style == "summary"):
        return git.what_changed(where,
                                cid_from,
                                cid_to,
                                directories,
                                verbose = verbose,
                                opts = [ '--pretty=%n%H %ci %an <%ae> %n%w(,3,3)%B' ],
                                splitre = '[0-9a-f]+')
            
            


    else:
        raise GiveUp("I do not understand the log style '%s'"%style)

def merge_advice(base, lines,base_repo):
    return ('Error merging patches to base %s\n'
            '%s\n'
            'Fix the problems:\n'
            '  pushd %s\n'
            '  git status\n'
            '  edit <the appropriate files>\n'
            '  git commit -a\n'
            '  popd\n'
            'and do "weld finish", or abort using "weld abort"'%\
            (base, lines, base_repo))

def sanitise(in_dir, state, opts, verbose = False):
    if opts.sanitise_script is not None:
        scname = os.path.join(opts.cwd, opts.sanitise_script)
    elif 'sanitise_script' in state:
        scname = state['sanitise_script']
    else:
        scname = None
    if (scname is None):
        # Nothing to do.
        return
    # Otherwise .. 
    fn = tempfile.mktemp(prefix='weld_log')
    with open(fn, 'w') as f:
        for l in state['log']:
            f.write(l)
            f.write('\n')
    # Sanitise in the context of whatever directory the 
    #   program was run from.
    an_env = os.environ.copy()
    an_env['WELD_LOG'] = fn
    if 'weld_directories' in state:
        an_env['WELD_DIRS'] = " ".join(state['weld_directories'])
    print "Sanitising - run %s in %s with log %s.. "%(scname, in_dir, fn)
    try:
        run_to_stdout(scname, cwd = in_dir, verbose = verbose, env = an_env)
    except Exception, e:
        print "%s"%e
        traceback.print_exc()
        print ("\n"
               "Retry with 'weld sanitise' and then step or commit (or finish)")
    # Now read the log back in.
    with open(fn, 'r') as f:
        state['log'] = map(lambda x: x.strip(), f.readlines())
    os.remove(fn)

def pull_base(spec, base_name):
    b = spec.query_base(base_name)
    repo = layout.base_repo(spec.base_dir, base_name)
    if not os.path.exists(repo):
        os.mkdir(repo)
        git.init(repo)
    git.pull(repo, b.uri, b.branch, b.tag, b.rev)

def push_base(spec, base_name):
    b = spec.query_base(base_name)
    repo = layout.base_repo(spec.base_dir, base_name)
    if b.branch is None:
        branch = "master"
    else:
        branch = b.branch
    git.push(repo, b.uri, "+%s:%s"%(branch,branch))


# End file.
