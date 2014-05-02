"""
Git utilities

@todo We rely on porcelain quite heavily here - we should stop doing that.
"""

import tempfile
import os

import headers
import layout

from utils import run_silently, run_to_stdout, GiveUp

def init(where):
    run_silently(["git", "init"], cwd=where)

def add_in_subdir(where, dirname):
    run_silently(["git", "add", "-A", "%s/**"%dirname], cwd=where)

def add(where, files):
    run_silently(["git", "add"] + files, cwd=where)

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

def commit(where, comment, headers):
    """
    Do a git commit with a given set of headers - headers is a list of pairs in the
    usual way
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
    run_silently(["git", "commit", "--allow-empty", "-F", n], cwd=where)
    os.unlink(n)

def current_branch(where, verbose=True):
    rv, out = run_silently(["git", "branch", "-v"], cwd=where, verbose=verbose)
    lines = out.splitlines()
    for l in lines:
        l = l.strip()
        f = l.split(' ')
        if (f[0] == '*'):
            return f[1]
    return "master"

def log(where, commit_id):
    """
    Get the log entry for a commit
    """
    rv, out = run_silently(["git", "log", "-n", "1", "--format=format:%B", commit_id],
                       cwd=where)
    return out

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
    rv, out = run_silently(["git", "log", "--grep=%s"%(headers.header_grep_merge(base)),
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
    rv, out = run_silently(["git", "log", "--grep=%s"%(headers.header_grep_push(base)),
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
    rv, out = run_silently(["git", "log", "--grep=%s"%(headers.header_grep_init()),
                            "-E", "--oneline", "--no-abbrev-commit"], cwd=where)
    lines = out.splitlines()
    if (len(lines) > 0):
        f = lines[0].split(' ')
        return f[0]
    raise GiveUp("Cannot find a weld init line in history")


def create_and_switch(where, branch_name, from_commit):
    """
    Checkout where at from_commit, create branch_name at that point
    and switch to it
    """
    rv, out = run_silently(["git", "checkout", "-b", branch_name, from_commit], cwd=where)

def has_branch(where, branch_name):
    rv, out = run_silently(["git", "branch", "-v"], cwd=where)
    lines = out.split('\n')
    for l in lines:
        l = l[1:].strip()
        f = l.split(' ')
        if (len(f) > 1 and f[0]== branch_name):
            return True
    return False

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
  
def switch_branch(spec, to_branch):
    run_silently([ "git", "checkout", to_branch ], cwd=spec.base_dir)

def remove_branch(spec, rm_branch):
    run_silently([ "git", "branch", "-d", rm_branch ], cwd=spec.base_dir)

def merge(spec, to_branch, from_branch, msg, squashed = False):
    """
    Note that merge leaves you on the to_branch
    """
    switch_branch(spec, to_branch)
    cmd = [ "git", "merge" ]
    if (squashed):
        cmd.append("--squash")
    #cmd.append("--no-ff") # To make sure we always get our commit
    # Sadly, there is no -F option
    cmd.extend([ "-m" , msg])
    cmd.append(from_branch)
    run_silently(cmd, cwd=spec.base_dir)

def has_local_changes(where):
    rv, out = run_silently(["git", "status", "-s"], cwd=where)
    if (len(out.strip()) == 0):
        return False
    else:
        return True

def list_changes(where, from_cid, to_cid):
    """
    Return a list of commits in where from from_cid to to_cid, including
    to_cid but not from_cid, in the order in which they should be applied
    """
    rv, out = run_silently(["git", "rev-list", "%s...%s"%(from_cid, to_cid)], cwd=where)
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

    
def apply(where, patch_file):
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
        print 'Should we pull?'

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
        print 'Should we push?'

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
