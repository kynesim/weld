"""
Weld utilities
"""

import os
import sys
import subprocess
import tempfile

def run(cmd, env = None, useShell = False, allowFailure = False, isSystem = False, verbose = True):
    """
    Runs a command via the shell

    cmd is an array in the usual way. 

    @return (rv, out, err) .
    """
    if env is None:
        env = os.environ
    a_process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr = subprocess.PIPE,
                                 shell = useShell)
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

        
