"""
Git utilities

@todo We rely on porcelain quite heavily here - we should stop doing that.
"""

import tempfile
import os
import re

from welded.headers import header_grep_merge, header_grep_push, header_grep_init
from welded.utils import run_silently, run_to_stdout, GiveUp

def init(where):
    run_silently(["git", "init"], cwd=where)

def add_in_subdir(where, dirname):
    if (not os.path.exists(dirname)):
        run_silently(["git", "rm", "--ignore-unmatch", "-f", "-r", dirname], cwd = where)
    else:
        run_silently(["git", "add", "-f", "-A", "%s/**"%dirname], cwd=where)

def add(where, files, verbose=True):
    run_silently(["git", "add", "-f" ] + files, cwd=where, verbose=verbose)

def clone(dir_into, from_repo, from_branch, from_tag, from_rev):
    cmd = [ "git", "clone" ]
    if (from_branch is not None):
        cmd.extend([ "--branch", from_branch ])
    # XXX There is no '-r' switch to 'git clone' - what is meant to happen?
    if (from_tag is not None):
        cmd.extend(["-r", from_tag])
    if (from_rev is not None):
        cmd.extend([ "-r", from_rev ])
    cmd.append(from_repo)
    cmd.append(dir_into)
    run_to_stdout(cmd)

def pull(dir_into, remote, from_branch, from_tag, from_rev):
    cmd = [ "git", "pull", remote ]
    # XXX Is the user going to be surprised by this precedence (and the
    # XXX consequent ignoring of values because of it?)
    if (from_branch is not None):
        cmd.append(from_branch)
    elif (from_tag is not None):
        cmd.append(from_tag)
    elif (from_rev is not None):
        cmd.append(from_rev)
    else:
        cmd.append("master")
    run_to_stdout(cmd, cwd=dir_into)

def push(where, uri = None, branch = None, verbose=True):
    """Push.

    - 'where' is the directory to run the command in.
    """
    cmd = [ 'git', 'push' ]
    if (uri is not None):
        cmd.extend([ uri])
    if (branch is not None):
        cmd.extend([ branch ])

    run_silently(cmd, cwd=where, verbose=verbose)

def commit(where, comment, headers):
    """Do a git commit with a given set of headers.

    'headers' is a list of pairs in the usual way
    """
    res = ""
    for h in headers:
        (k,v) = h
        res += "%s: %s\n"%(k,v)
    res += "\n"
    res += comment
    res += "\n"
    t = tempfile.NamedTemporaryFile(prefix='weldcommit', delete = False)
    t.write(res)
    n = t.name
    t.close()
    commit_using_file(where, n)
    os.unlink(n)

def commit_using_file(where, commit_file, all=False, verbose=True):
    """Commit with the message contained in 'commit_file'.

    If 'all' is true, then add "-a" to the command, to stage any modified or
    deleted files.

    Does not delete 'commit_file'.
    """
    cmd = ["git", "commit", "--allow-empty"]
    if all:
        cmd.append("--all")
    cmd += ["--file", commit_file]
    run_silently(cmd, cwd=where, verbose=verbose)

def commit_using_message(where, message, all=False, verbose=True):
    """Commit with the message in 'message'.

    If 'all' is true, then add "-a" to the command, to stage any modified or
    deleted files.
    """
    cmd = ["git", "commit", "--allow-empty"]
    if all:
        cmd.append("--all")
    cmd += ["-m", message]
    run_silently(cmd, cwd=where, verbose=verbose)

def checkout(where, commit_id=None, new_branch_name=None, verbose=False):
    """Checkout a commit, or create and checkout a branch.

    If 'commit_id' is given, then checkout that commit ('commit_id' should
    be a SHA1 id, or a branch name, or some other means of identifying the
    commit that is wanted).

    If 'new_branch_name' is given, then create and checkout that branch.

    If both are given, then first checkout 'commit_id', and then create and
    checkout the named branch.
    """
    if commit_id is not None:
        run_silently(['git', 'checkout', commit_id], cwd=where, verbose=verbose)

    if new_branch_name is not None:
        run_silently(['git', 'checkout', '-b', new_branch_name], cwd=where,
                     verbose=verbose)

def current_branch(where, verbose=True):
    try:
        rv, out = run_silently(["git", "symbolic-ref", "--short", "-q", "HEAD" ], cwd = where,
                           verbose = verbose)
    except GiveUp,g :
        raise GiveUp("%s - attempt to determine the current branch for a detached HEAD in %s ?"%(g,where))        

    return out.strip()


def what_changed(where, commit_from, commit_to, paths = None, verbose = False, opts = None,
                 splitre = 'commit '):
    """
    Retrieves the full log entry for a commit, as given by 
    'git whatchanged', with a list of changes.
    
    Changes are returned in a list, one at a time.
    """
    cmd = ["git", "whatchanged", "-m" ]
    if (commit_from is None):
        cmd += [ '%s'%commit_to ]
    else:
        cmd += [ "%s..%s"%(commit_from,commit_to) ]
    if (opts is not None):
        cmd += opts
    if (paths is not None):
        cmd += [ '--' ] + paths
    rv, out = run_silently(cmd, cwd = where)
    an_array = re.split('(^%s)'%splitre, out, flags=re.MULTILINE)
    # Kill anything before the first marker.
    ra = [ ]
    if (len(an_array) > 0):
        an_array = an_array[1:]
        while (len(an_array) > 0):
            ra.append( (an_array[0] + an_array[1]) )
            an_array = an_array[2:]
    return ra
   

def log(where, commit_id):
    """
    Get the log entry for a commit
    """
    rv, out = run_silently(["git", "log", "-n", "1", "--format=format:%B", commit_id],
                       cwd=where)
    return out

def log_between(where, from_id, to_id, paths=None, verbose=False, opts = None):
    """Do a git log for "<from_id>..<to_id> -- <paths>"

    Returns a sequence of lines.
    """
    cmd = ['git', '--no-pager', 'log' ]
    if (opts is not None):
        cmd += opts
    else:
        cmd += [ '--oneline' ]
    if (from_id is not None):
        cmd += [ '%s..%s'%(from_id, to_id)]
    else:
        cmd += [ '%s'%to_id ]
    if paths:
        cmd += ['--'] + paths
    rv, changes = run_silently(cmd, cwd=where, verbose=verbose)
    return changes.splitlines()


def query_current_commit_id(where):
    """
    Retrieve the commit id for the current point in where
    """
    rv, out = run_silently(["git", "log", "-n", "1", "--format=format:%H"], cwd=where)
    return out.strip()

def query_merge(where, base):
    """Return the id of the last commit which contained a merge for this 'base'

    Finds the last "X-Weld-State: Merged <base>" commit, and returns its
    SHA1 id.

    If there wasn't one, return None.
    """
    rv, out = run_silently(["git", "log", "--grep=%s"%(header_grep_merge(base)),
                            "-E", "--oneline", "--no-abbrev-commit"], cwd=where)
    lines = out.splitlines()
    if (len(lines) > 0):
        f = lines[0].split(' ')
        return f[0]
    else:
        return None

def query_push(where, base):
    """Return the id of the last commit which contained a push of this 'base'

    Finds the last "X-Weld-State: Pushed <base>" commit, and returns its
    SHA1 id.

    If there wasn't one, return None.
    """
    rv, out = run_silently(["git", "log", "--grep=%s"%(header_grep_push(base)),
                            "-E", "--oneline", "--no-abbrev-commit"], cwd=where)
    lines = out.splitlines()
    if (len(lines) > 0):
        f = lines[0].split(' ')
        return f[0]
    else:
        return None

def query_merge_or_push(where, base):
    """Return the id of the last commit which contained a merge or push of this 'base'

    Finds the last "X-Weld-State: Pushed <base>", or
    "X-Weld-State: Merged <base>" commit, and returns its SHA1 id.

    If there wasn't one, return None.
    """
    rv, out = run_silently(["git", "log",
                            "--grep=%s"%(header_grep_push(base)),
                            "--grep=%s"%(header_grep_merge(base)),
                            "-E", "--oneline", "--no-abbrev-commit"], cwd=where)
    lines = out.splitlines()
    if (len(lines) > 0):
        f = lines[0].split(' ')
        return f[0]
    else:
        return None

def query_init(where):
    """
    Query the weld init commit
    """
    rv, out = run_silently(["git", "log", "--grep=%s"%(header_grep_init()),
                            "-E", "--oneline", "--no-abbrev-commit"], cwd=where)
    lines = out.splitlines()
    if (len(lines) > 0):
        f = lines[0].split(' ')
        return f[0]
    raise GiveUp("Cannot find a weld init line in history")


def has_branch(where, branch_name):
    rv, out = run_silently(["git", "branch", "-v"], cwd=where)
    lines = out.split('\n')
    for l in lines:
        l = l[1:].strip()
        f = l.split(' ')
        if (len(f) > 1 and f[0]== branch_name):
            return True
    return False

def new_branch_name(where, base_name, commit_id=None):
    """Construct a unique branch name given 'base_name' and 'commit_id'

    If 'commit_id' is given, it should be the commit we are going to branch
    from, and the first 10 characters of it will be used in the name.

    We will prepend 'weld-', and append the commit id of the current
    commit, as well as, if necessary, an index (to ensure it is absolutely
    unique in this repository).
    """
    base_name = '%s-%s'%(base_name, commit_id[:10])
    branch_name = base_name
    count = 0
    while has_branch(where, branch_name):
        count += 1
        branch_name = '%s-%d'%(base_name, count)
    return branch_name

def tag(where, name, commit_id, force=True, verbose=False):
    """Tag with the given name.

    - 'where' is the directory to run the command in
    - 'name' is the name of the tag
    - 'commit_id' is a SHA1 commit id (a string)

    If 'force', then use '--force' to allow the tag to have existed already.
    """
    if force:
        cmd = ['git', 'tag', '--force', name, commit_id]
    else:
        cmd = ['git', 'tag', name, commit_id]
    run_silently(cmd, cwd=where, verbose=verbose)

def hard_reset(where):
    run_silently(['git', 'reset', '--hard'], cwd = where)

def diff_this(where, relative_to, commit_id, verbose=False):
    """Run "git diff" to find the changes 'commit_id' made to 'relative_to'

    - 'where' is the directory to run the command in
    - 'relative_to' is the directory we want the differences for
    - 'commit_id' is the commit whose changes we are intereseted in

    If 'verbose', prints out the command it is obeying, and also the
    difference output.

    Returns the difference output (as a string)

    Raises GiveUp if the command fails.
    """
    rv, diff = run_silently(['git', 'diff', '--relative=%s'%relative_to,
        '%s^!'%commit_id], cwd=where, verbose=verbose)
    if verbose:
        print diff
    return diff

def apply_patch(where, patch_file, directory=None, verbose=False):
    """Apply a patch.

    - 'where' is the directory to run the command in
    - 'patch_file' is the path to the file containing the patch to be applied
    - if 'directory' is given, then "--directory-<directory>" is specified,
      which prepends 'directory' to all filenames, replacing the "a" and "b"
      in the patch description with 'directory'.

    Raises GiveUp if something goes wrong with the command (i.e., git returns
    a non-zero value)
    """
    if directory is None:
        cmd = ['git', 'apply', '--index', patch_file]
    else:
        cmd = ['git', 'apply', '--index', '--directory=%s'%directory, patch_file]
    run_silently(cmd, cwd=where, verbose=verbose)

def abort_rebase(spec):
    run_silently([ "git", "rebase", "--abort" ], cwd=spec.base_dir)

def rebase(spec, upstream, branch = None, onto = None):
    """
    Rebase from_commit .. to_commit onto branch onto
    """
    cmd =  [ "git", "rebase" ]
    if (onto is not None):
        cmd.extend(["--onto", onto])
    cmd.append(upstream)
    if (branch is not None):
        cmd.append(branch)
    run_to_stdout(cmd, cwd=spec.base_dir)
  
def switch_branch(where, to_branch):
    run_silently([ "git", "checkout", to_branch ], cwd=where)

def remove_branch(where, rm_branch, irrespective=False):
    """Delete the branch 'rm_branch'

    - 'where' is where to run the command
    - 'rm_branch' is the name of the branch to delete
    -  if 'irrespective', delete it even if it is not merged (i.e., use -D
       rather than -d)
    """
    run_silently([ "git", "branch",
                   "-D" if irrespective else "-d",
                   rm_branch ], cwd=where)

def merge(where, to_branch, from_branch, msg, squashed = False):
    """
    Note that merge leaves you on the to_branch
    """
    switch_branch(where, to_branch)
    cmd = [ "git", "merge" ]
    if (squashed):
        cmd.append("--squash")
    #cmd.append("--no-ff") # To make sure we always get our commit
    # Sadly, there is no -F option
    cmd.extend([ "-m" , msg])
    cmd.append(from_branch)
    run_silently(cmd, cwd=where)

def ff_merge(where, branch_name, verbose=False):
    """Do a fast-forward merge of branch 'branch_name' to the current branch
    """
    run_silently(['git', 'merge', branch_name, '--ff-only'], cwd=where,
                 verbose=verbose)

def merge_to_current(where, branch_name, squash=False, verbose=False, commit = False):
    """Do a "normal" merge of branch 'branch_name' to the current branch.

    Do not commit unless commit is set to try.

    If 'squash' is true, then do a squash merge with --squash.
    """
    cmd = ['git', 'merge', branch_name]
    if squash:
        cmd.append('--squash')
    elif not commit:
        cmd.append('--no-commit')
    run_silently(cmd, cwd=where, verbose=verbose)

def merge_abort(where, verbose=False):
    """Abort a merge
    """
    run_silently(['git', 'merge', '--abort'], cwd=where, verbose=verbose)

def has_local_changes(where, verbose=False):
    rv, out = run_silently(["git", "status", "-s"], cwd=where, verbose=verbose)
    if verbose:
        print out
    if (len(out.strip()) == 0):
        return False
    else:
        return True

def list_changes(where, from_cid, to_cid, paths = None, kind = None, opts = None):
    """
    Return a list of commits in where from from_cid to to_cid, including
    to_cid but not from_cid, in the order in which they should be applied
    """
    cmd = ["git", "rev-list" ]
    if (opts is not None):
        cmd = cmd + opts
    if (kind is not None):
        cmd = cmd + [ kind ]
    if from_cid is None:
        cmd += [ '%s'%to_cid ]
    else:
        cmd = cmd + [ "%s...%s"%(from_cid, to_cid) ]
    if paths:
        cmd += ['--'] + paths
    rv, out = run_silently(cmd, cwd=where)
    lines = out.split('\n')
    rv = [ ]
    for l in lines:
        l = l.strip()
        if (len(l) > 0):
            rv.insert(0, l)
    return rv


def show(where, cid):
    """
    Returns a temporary file containing a binary patch representing cid
    """
    f = tempfile.NamedTemporaryFile(prefix="/tmp/weldcid%s"%cid)
    # @todo Could be very much more efficient (and prolly needs to be)
    rv, out = run_silently(["git", "show", "--binary", cid], cwd=where)
    f.file.write(out)
    return f

def show_diff(where, from_cid, to_cid):
    """
    Returns a temporary file containing the diffs from from to to.
    """
    f = tempfile.NamedTemporaryFile(prefix="/tmp/weldcid%s"%to_cid, delete=False)
    # @todo Could be very much more efficient (and prolly needs to be)
    rv, out = run_silently(["git", "diff", "--binary", "%s..%s"%(from_cid, to_cid)], cwd=where)
    f.file.write(out)
    return f

    
def apply_patch_file(where, patch_file):
    """
    Apply the given patch file to the given repo
    """
    run_silently(["git", "apply", "-v", patch_file], cwd=where)


def set_remote(where, name, origin):
    """
    Set a remote
    """
    run_silently(["git", "remote", "rm", name], allowFailure=True, cwd=where)
    run_silently(["git", "remote", "add", name, origin], cwd=where)

def list_files(where, verbose=False):
    """Return the files listed by "git ls-files" in 'where'

    Returns a list of paths, relative to 'where'
    """
    rv, text = run_silently(["git", "ls-files"], cwd=where, verbose=verbose)
    lines = text.splitlines()
    return lines

def rm(where, files, verbose=True, force = True):
    """Delete the named files

    'files' should be a list of file names
    """
    cmd = [ "git", "rm" ]
    if force:
        cmd.append('-f')
    run_silently(cmd + files, cwd=where, verbose=verbose)

def should_we_pull_or_push(remote_name='origin', branch_name='master', cwd=None, verbose=False):
    """Is there something to pull from/push to our remote?

    Returns one of:

    * None, None  - there is no remote
    * True,  None - we need to pull, don't push yet
    * False, True - we need to push
    * False, False - neither is necessary
    """

    # Get the HEAD of that branch on our remote
    rv, line = run_silently(['git', 'ls-remote', remote_name, branch_name],
                            cwd=cwd, verbose=verbose)
    if line == '':
        # There is no remote, so we can't see its HEAD(!)
        if verbose:
            print 'There is no remote, so we cannot pull or push'
        return None, None
    words = line.split()
    remote_head = words[0]
    if verbose:
        print 'The HEAD of %s/%s is %s'%(remote_name, branch_name, remote_head[:10])

    if verbose:
        print 'Should we "git pull"?'

    # Does that exist here? If not, we presumably need to pull...
    try:
        # Is the given SHA1 a known commit object?
        # Find out by asking what (local) branch it is on...
        # We don't allow "verbose" to be true because if it "goes wrong" it
        # output the appropriate error diagnostic followed by a help message
        # on how to use "git branch", which is a bit distracting...
        run_silently(['git', 'branch', '--contains', remote_head],
                     cwd=cwd, verbose=False)
        if verbose:
            # Repeat the command to show the branch name...
            run_to_stdout(['git', 'branch', '--contains', remote_head],
                          cwd=cwd, verbose=True)
            print 'No, because we already know that commit'
        should_pull = False
    except GiveUp as e:
        # Let's assume that there's only one reason for this...
        if verbose:
            print e.message.splitlines()[0]
            print 'Yes, because we do not know that commit'
        should_pull = True

    if verbose:
        print 'Should we "git push"?'

    should_push = None

    # Assuming that exists here (i.e., that we don't need to pull), does
    # it match our HEAD?
    rv, local_head = run_silently(['git', 'rev-parse', branch_name],
                                  cwd=cwd, verbose=verbose)
    local_head = local_head.strip()
    if remote_head == local_head:
        should_push = False
        if verbose:
            print local_head
            print 'No, because remote HEAD matches local HEAD'
    else:
        should_push = True
        # How far behind are we?
        try:
            rv, lines = run_silently(['git', 'rev-list', '%s..%s'%(remote_head, branch_name)],
                                     cwd=cwd, verbose=verbose)
        except GiveUp:
            # It presumably wasn't an ancestor commit - oh dear
            if verbose:
                print '%s does not appear to be an ancestor of HEAD of %s'%(remote_head[:10],
                        branch_name)
                print 'No, we should not push, because we probably need to pull'
            should_push = None         # see docstring above

        if should_push is not None and verbose:
            count = len(lines.splitlines())
            print 'Local %s is %d commit%s ahead of %s/%s'%(branch_name,
                    count, '' if count==1 else 's', remote_name, branch_name)
            print 'Yes'

    return should_pull, should_push

# End file.
