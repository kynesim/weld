"""
Generic operations
"""

import git
import utils
import layout
import headers
import os
import tempfile
import re
import shutil

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
            git.apply(spec.base_dir, temp2.name)
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
        except:
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
        utils.run_silently(["rsync", "-avz", "--exclude", ".git/", os.path.join(src, "."), os.path.join(dest, ".")])
        # Make sure you add all the files in the subdirectory
        git.add_in_subdir(spec.base_dir, dest)
    # Now commit them with an appropriate header.
    hdrs = headers.seam_op(headers.SEAM_VERB_ADDED, base_obj, seams, base_commit)
    git.commit(spec.base_dir, hdrs, [] )

FINISH_PULL_PREFIX="import pull\n" + \
    "def go(spec):"
FINISH_PULL_SUFFIX="\n"

FINISH_PUSH_PREFIX="import push\n" + \
    "def go(spec):"
FINISH_PUSH_SUFFIX="\n"

def write_finish_pull(spec, cmds_ok, cmds_abort):
    with open(layout.complete_pull_file(spec.base_dir), "w+") as f:
        f.write(FINISH_PULL_PREFIX)
        f.write(cmds_ok)
        f.write(FINISH_PULL_SUFFIX)
    with open(layout.abort_file(spec.base_dir), "w+") as f:
        f.write(FINISH_PULL_PREFIX)
        f.write(cmds_abort)
        f.write(FINISH_PULL_SUFFIX)

def write_finish_push(spec, cmds_ok, cmds_abort):
    with open(layout.continue_push_file(spec.base_dir), "w+") as f:
        f.write(FINISH_PUSH_PREFIX)
        f.write(cmds_ok)
        f.write(FINISH_PUSH_SUFFIX)
    with open(layout.abort_file(spec.base_dir), "w+") as f:
        f.write(FINISH_PUSH_PREFIX)
        f.write(cmds_abort)
        f.write(FINISH_PUSH_SUFFIX)

def do_finish_pull(spec):
    c = layout.complete_pull_file(spec.base_dir)
    if (os.path.exists(c)):
        f = utils.dynamic_load(c, no_pyc=True)
        f.go(spec)
        os.remove(c)
        os.remove(layout.abort_file(spec.base_dir))
    else:
        raise utils.GiveUp('No pending "weld pull" to complete')

def do_continue_push(spec):
    c = layout.continue_push_file(spec.base_dir)
    if (os.path.exists(c)):
        f = utils.dynamic_load(c, no_pyc=True)
        f.go(spec)
        os.remove(c)
        os.remove(layout.abort_file(spec.base_dir))
    else:
        raise utils.GiveUp('No pending "weld push" to continue')

def do_abort(spec):
    c  = layout.abort_file(spec.base_dir)
    if (os.path.exists(c)):
        f = utils.dynamic_load(c, no_pyc=True)
        f.go(spec)
        os.remove(c)
        os.remove(layout.complete_pull_file(spec.base_dir))
    else:
        raise utils.GiveUp('No pending "weld pull" or "weld push" to abort')

def count(filename):
    contents = ""
    try:
        with open(filename, 'rb') as fin:
            contents = fin.read().trim()
    except:
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

# End file.
