"""
Git utilities
"""

import utils
import tempfile
import os
import layout

def run_with(where, cmd):
    return utils.run(cmd, utils.with_env([ ("GIT_DIR", where) ]))

def init(where):
    utils.run(["git", "init"], 
              utils.with_env([ ("GIT_DIR", where) ]))

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
    utils.run(["git", "commit", "-F", n], 
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
    (rv, out, err) = utils.run(["git", "log", "--grep=%s"%(layout.header_grep_merge(base)), 
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
    (rv, out, err) = utils.run(["git", "log", "--grep=%s"%(layout.header_grep_init()),
                                "-E", "--oneline", "--no-abbrev-commit"])
    lines = out.splitlines()
    if (len(lines) > 0):
        f = lines[0].split(' ')
        return f[0]
    raise utils.GiveUp("Cannot find a weld init line in history")

        
    


# End file.
