"""
Weld utilities
"""

import os
import sys
import subprocess
import tempfile
import hashlib
import imp
import traceback

def run_to_stdout(cmd, env = None, useShell = False, allowFailure = False, isSystem = False, verbose = True,
        cwd = None):
    """
    Runs a command via the shell

    cmd is an array in the usual way. 

    @return (rv, out, err) .
    """
    if (verbose):
        print "> %s"%(" ".join(cmd))
    if env is None:
        env = os.environ
    a_process = subprocess.Popen(cmd, 
                                 shell = useShell,
                                 cwd = cwd)
    (out, err) = a_process.communicate()
    rv = a_process.wait()
    if (rv and (not allowFailure)):
        raise GiveUp("Command '%s' failed - %d\n%s"%(" ".join(cmd), rv, err))
    return (a_process.wait(), None, None)


def run(cmd, env = None, useShell = False, allowFailure = False, isSystem = False, verbose = True,
        cwd = None):
    """
    Runs a command via the shell

    cmd is an array in the usual way. 

    @return (rv, out, err) .
    """
    if (verbose):
        print "> %s"%(" ".join(cmd))
    if env is None:
        env = os.environ
    a_process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr = subprocess.PIPE,
                                 shell = useShell,
                                 cwd = cwd)
    (out, err) = a_process.communicate()
    rv = a_process.wait()
    if (rv and (not allowFailure)):
        raise GiveUp("Command '%s' failed - %d\n%s"%(" ".join(cmd), rv, err))
    return (a_process.wait(), out, err)

def with_env(lst):
    """
    Return a copy of the current environment augmented with the bindings in lst - which
    is an array of pairs
    """
    ret = os.environ.copy()
    for l in lst:
        (n,v) = l
        ret[n] = v
    return ret


def find_weld_dir(d):
    """
    Goes up d until it finds a weld. Fails if it finds .git without .weld or vice versa.
    """
    orig_d = d
    while True:
        w = os.path.exists(os.path.join(d, ".weld"))
        g = os.path.exists(os.path.join(d, ".git"))
        if ((not w) and (not g)):
            # Rats. up a level ..
            p = os.path.split(d)
            if (len(p[0]) > 0): 
                d = p[0]
            else:
                raise GiveUp("Cannot find a weld in '%s'"%orig_d)
        elif (w and g):
            # Found it!
            return d
        else:
            raise GiveUp("There is something in %s (up from %s) , but it is not a valid weld - \n" + 
                         " it does not have both .git and .weld"%(d, orig_d))



def classify_seams(old_seams, new_seams):
    """
    Returns (seams_deleted_in_new, seams_changed_in_new, seams_created_in_new)
    All the seams are db.Seam objects.
    """
    deleted_in_new = [ ]
    changed = [ ]
    created_in_new = [ ]
    # Build a hash representation
    old_h = { }
    new_h = { }
    for x in old_seams:
        old_h[ x.srcdest() ] = x
    for y in new_seams:
        new_h[ y.srcdest() ] = y
    # Everything in old but not new is deleted
    for x in old_seams:
        r = x.srcdest()
        if (r in new_h):
            # Changed
            changed.append(x)
        else:
            # Deleted
            deleted_in_new.append(x)
    for y in new_seams:
        r = y.srcdest()
        if (not (r in old_h)):
            # Added
            created_in_new.append(y)
    return (deleted_in_new, changed, created_in_new)
    

def dynamic_load(filename, no_pyc=False):
    try:
        try:
            with open(filename, 'rb') as fin:
                contents = fin.read()
        except IOError, e:
            raise Bug("Cannot open %s"%filename)
        hasher = hashlib.md5()
        hasher.update(contents)
        digest = hasher.hexdigest()
        old_dont_write_bytecode = sys.dont_write_bytecode
        try:
            if no_pyc:
                # Request that loading the source file doesn't create a .pyc file
                sys.dont_write_bytecode = True
            return imp.load_source(digest, filename)
        finally:
            sys.dont_write_bytecode = old_dont_write_bytecode
    except GiveUp:
        raise
    except Exception:
        raise GiveUp("Cannot load %s - %s"%(filename, traceback.format_exc()))

def run_file(name, spec):
    execfile(name, globals(), locals())

class GiveUp(Exception):
    """
    Something has gone wrong - tell the user
    """
    # What to return to the user when something goes wrong.
    retval = 1

    def __init__(self, message = None, retval = 1):
        self.message = message
        self.retval = retval
    def __str__(self):
        if self.message is None:
            return ''
        else:
            return self.message

    def __repr__(self):
        parts = []
        if self.message is not None:
            parts.append(repr(self.message))
        if self.retcode != 1:
            parts.append('%d'%self.retcode)
        return 'GiveUp(%s)'%(', '.join(parts))



class Bug(GiveUp):
    """
    Use this to indicate that something has gone wrong with muddle itself.

    We thus expect that a traceback will be produced.
    """
    pass



# End file.

        
