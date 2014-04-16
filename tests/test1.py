#! /usr/bin/env python2

"""Initial tests for weld
"""

import os
import subprocess
import sys
import traceback

# -----------------------------------------------------------------------------
# Test support

def get_parent_dir(this_file=None):
    """Determine the path of our parent directory.

    If 'this_file' is not given, then we'll return the parent directory
    of this file...
    """
    if this_file is None:
        this_file = __file__
    this_file = os.path.abspath(this_file)
    this_dir = os.path.split(this_file)[0]
    parent_dir = os.path.split(this_dir)[0]
    return parent_dir

PARENT_DIR = get_parent_dir()

class GiveUp(Exception):
    pass

class ShellError(GiveUp):
    def __init__(self, cmd, retcode, text=None):
        msg = "Shell command '%s' failed with retcode %d"%(cmd, retcode)
        if text:
            msg = '%s\n%s'%(msg, text)
        super(GiveUp, self).__init__(msg)
        self.retcode=retcode

def shell(cmd, verbose=True):
    """Run a command in the shell

    'cmd' is the comamnd to run, e.g., "weld init".

    Raises a ShellError if the return code is not zero.
    """
    if verbose:
        print '>> %s'%cmd
    retcode = subprocess.call(cmd, shell=True)
    if retcode:
        raise ShellError(cmd, retcode)

def weld(cmd, verbose=True):
    """Run our local 'weld', with the given arguments

    E.g., weld('init weld.xml')
    """
    shell('%s %s'%(os.path.join(PARENT_DIR, 'weld'), cmd))

def captured_cmd_seq(cmd_seq, verbose=True):
    """Grab the exit code and output from a command.

    'cmd_seq' is a command as an array of "words" - e.g., ['weld', 'init']

    Returns the exit code and text output from the given command.
    """
    if verbose:
        print ">> %s"%(' '.join(cmd_seq))   # ignoring quoting

    # Ask what we call not to use buffering on its outputs, so that we get
    # stdout and stderr folded together correctly, despite the fact that our
    # output is not to a console
    env = os.environ
    env['PYTHONUNBUFFERED'] = 'anything'
    try:
        output = subprocess.check_output(cmd_seq, env=env, stderr=subprocess.STDOUT)
        return 0, output
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output

def touch(filename, content=None, verbose=True):
    """Create a new file, and optionally give it content.
    """
    if verbose:
        print '++ touch %s'%filename
    with open(filename, 'w') as fd:
        if content:
            fd.write(content)
# -----------------------------------------------------------------------------

weld_xml_file = """\
<?xml version="1.0" ?>
<weld name="frank">
  <origin uri="ssh://git@home.example.com/ribbit/fromble" />

  <base name="project124" uri="ssh://git@foo.example.com/my/base" branch="b" rev=".." tag=".."/>
  <base name="igniting_duck" uri="ssh://git@bar.example.com/wobble" />

  <seam base="project124" dest="flibble" />
  <seam base="igniting_duck" src="foo" dest="bar" />

</weld>
"""

def ensure_got_withdir():
    if not os.path.exists('withdir'):
        shell('git clone https://github.com/tibs/withdir.git withdir')
    sys.path.append(os.path.abspath('withdir'))

def main(args):

    ensure_got_withdir()
    from withdir import NewDirectory, TransientDirectory

    with TransientDirectory('test', keep_on_error=True) as d:
        touch('weld.xml', weld_xml_file)
        weld('init weld.xml')


if __name__ == '__main__':
    args = sys.argv[1:]
    try:
        main(args)
        print '\nGREEN light\n'
    except Exception as e:
        print
        traceback.print_exc()
        print '\nRED light\n'
        sys.exit(1)

# vim: set tabstop=8 softtabstop=4 shiftwidth=4 expandtab:
