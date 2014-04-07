"""
Git utilities
"""

import utils
import tempfile
import os
import headers
import layout

def run_with(where, cmd):
    return utils.run(cmd, utils.with_env([ ("GIT_DIR", where) ]))

def init(where):
    utils.run(["git", "init"], 
              utils.with_env([ ("GIT_DIR", where) ]))

def add_in_subdir(where, dirname):
    utils.run(["git", "add", dirname], cwd = where)

def add(where, files):
    utils.run(["git", "add"] + files,
              utils.with_env([ ("GIT_DIR", where) ]))

def clone(dir_into, from_repo, from_branch, from_tag, from_rev):
    cmd = [ "git", "clone" ]
    if (from_branch is not None):
        cmd.extend([ "-b", from_branch ])
    if (from_tag is not None):
        cmd.extend(["-r", from_tag])
    if (from_rev is not None):
        cmd.extend([ "-r", from_rev ])
    cmd.append(from_repo)
    cmd.append(dir_into)
    utils.run(cmd)

def pull(dir_into, remote, from_branch, from_tag, from_rev):
    cmd = [ "git", "pull", remote ]
    if (from_branch is not None):
        cmd.append(from_branch)
    elif (from_tag is not None):
        cmd.append(from_tag)
    elif (from_rev is not None):
        cmd.append(from_rev)
    else:
        cmd.append("master")
    utils.run(cmd, cwd = dir_into)

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
    utils.run(["git", "commit", "--allow-empty", "-F", n], 
              utils.with_env([ ("GIT_DIR", where) ]))
    os.unlink(n)

def current_branch(where):
    (rv, out, err) = run_with(where, ["git", "branch", "-v"])
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
    (rv, out, err) = run_with(where, ["git", "log", "-n", "1", "--format=format:%B", commit_id])
    return out

def query_current_commit_id(where):
    """
    Retrieve the commit id for the current point in where
    """
    (rv, out, err) = run_with(where, ["git", "log", "-n", "1", "--format=format:%H"] )
    return out.strip()

def query_merge(where, base):
    """
    Query the last commit which contained a merge
    """
    (rv, out, err) = utils.run(["git", "log", "--grep=%s"%(headers.header_grep_merge(base)), 
                                "-E", "--oneline", "--no-abbrev-commit"])
    lines = out.splitlines()
    if (len(lines) > 0):
        f = lines[0].split(' ')
        return f[0]
    return query_init(where)

def query_init(where):
    """
    Query the weld init commit
    """
    (rv, out, err) = utils.run(["git", "log", "--grep=%s"%(headers.header_grep_init()),
                                "-E", "--oneline", "--no-abbrev-commit"])
    lines = out.splitlines()
    if (len(lines) > 0):
        f = lines[0].split(' ')
        return f[0]
    raise utils.GiveUp("Cannot find a weld init line in history")


def create_and_switch(where, branch_name, from_commit):
    """
    Checkout where at from_commit, create branch_name at that point
    and switch to it
    """
    (rv,out, err) = run_with(where, ["git", "checkout", "-b", branch_name, from_commit])

def has_branch(where, branch_name):
    (rv, out, err) = run_with(where, ["git", "branch", "-v"])
    lines = out.split('\n')
    for l in lines:
        f = l.split(' ')
        if (len(f) > 1 and f[1]== branch_name):
            return True
    return False

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
    (rv,out,err) = run_with(spec.base_dir, cmd)
    return rv
  
def switch_branch(spec, to_branch):
    (rv, out,err) = run_with(spec.base_dir, 
                             [ "git", "checkout", to_branch ])

def remove_branch(spec, rm_branch):
    (rv,out,err) = run_with(spec.base_dir, 
                            [ "git", "branch", "-d", rm_branch ])

def merge(spec, to_branch, from_branch, msg, squashed = False):
    """
    Note that merge leaves you on the to_branch
    """
    switch_branch(spec.base_dir, to_branch)
    cmd = [ "git", "merge" ]
    if (squashed):
        cmd.append("--squash")
    cmd.append("--no-ff") # To make sure we always get our commit
    # Sadly, there is no -F option
    cmd.extend([ "-m" , "'%s'", msg])
    cmd.append(from_branch)
    (rv,out,err) = run_with(spec.base_dir, cmd)
    
        
# End file.
