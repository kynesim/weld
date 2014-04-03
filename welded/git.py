"""
Git utilities
"""

import utils
import tempfile
import os

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


# End file.
