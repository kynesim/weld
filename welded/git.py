"""
Git utilities
"""

import utils
import tempfile
import os
import layout

def init(where):
    utils.run(["git", "init"], 
              utils.with_env([ ("GIT_DIR", where) ]))

def add(where, files):
    utils.run(["git", "add"] + files,
              utils.with_env([ ("GIT_DIR", where) ]))

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
    (rv, out, err) = utils.run(["git", "branch", "-v"])
    lines = out.splitlines()
    for l in lines:
        l = l.strip()
        f = l.split(' ')
        if (f[0] == '*'):
            return f[1]
    return "master"

def query_merge(where, repo):
    (rv, out, err) = utils.run(["git", "log", "--grep=%s"%(layout.header_grep_merge(repo)), 
                                "-E", "--oneline", "--no-abbrev-commit"])
    lines = out.splitlines()
    if (len(lines) > 0):
        f = lines[0].split(' ')
        return f[0]
    return query_init(where)

def query_init(where):
    (rv, out, err) = utils.run(["git", "log", "--grep=%s"%(layout.header_grep_init()),
                                "-E", "--oneline", "--no-abbrev-commit"])
    lines = out.splitlines()
    if (len(lines) > 0):
        f = lines[0].split(' ')
        return f[0]
    raise utils.GiveUp("Cannot find a weld init line in history")

        
    


# End file.
