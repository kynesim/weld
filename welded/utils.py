"""
Weld utilities
"""

import os
import sys
import subprocess
import hashlib
import imp
import traceback

class GiveUp(Exception):
    """Something has gone wrong - tell the user
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


def run_to_stdout(cmd, allowFailure=False, verbose=True, cwd=None):
    """Runs a command with its output going to stdout/stderr as normal.

    cmd is an array in the usual way.

    If allowFailure is false, and the command has a non-zero returncode, then
    it raises GiveUp, with much explanation in the exception text.

    Otherwise, it just returns.
    """
    if (verbose):
        print "> %s"%(" ".join(cmd))
    try:
        subprocess.check_call(cmd,
                              stderr=subprocess.STDOUT,
                              cwd=cwd)
        return
    except subprocess.CalledProcessError as e:
        if allowFailure:
            return
        else:
            raise GiveUp(str(e))


def run_silently(cmd, allowFailure=False, verbose=True, cwd=None):
    """Runs a command and captures its output.

    cmd is an array in the usual way.

    If allowFailure is true, then it returns (returncode, output) where
    'output' is stdout and stderr together.

    If allowFailure is false, then if the command has a returncode of 0 it
    returns (0, output), and otherwise it raises GiveUp, with much explanation
    in the exception text.
    """
    if (verbose):
        print "> %s"%(" ".join(cmd))
    try:
        out = subprocess.check_output(cmd,
                                      stderr=subprocess.STDOUT,
                                      cwd=cwd)
        return 0, out
    except subprocess.CalledProcessError as e:
        if allowFailure:
            return e.returncode, e.output
        else:
            parts = []
            parts.append(str(e))
            errortext = e.output.splitlines()
            parts.extend(['  {}'.format(x) for x in errortext])
            raise GiveUp('\n'.join(parts))

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
        if w or g:
            break

        # Rats. up a level ..
        up1, tail = os.path.split(d)
        if up1 == d or d == '/':
            raise GiveUp("Not inside a weld\n"
                         "  Cannot find a .weld file in %s or its parents"%orig_d)

        d = up1

    if not w:
        raise GiveUp('Not a valid weld\n'
                     '  Looking at %s\n'
                     '  Found .git in %s, but no corresponding .weld'%(orig_d, d))
    elif not g:
        raise GiveUp('Not a valid weld\n'
                     '  Looking at %s\n'
                     '  Found .weld in %s, but no corresponding .git'%(orig_d, d))
    else:
        return d

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



# End file.

        
