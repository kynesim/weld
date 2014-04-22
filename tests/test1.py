#! /usr/bin/env python2

"""Initial tests for weld
"""

import os
import subprocess
import sys
import traceback

# -----------------------------------------------------------------------------
# Test support

def get_this_dir(this_file=None):
    """Determine the path of our the directory containing 'this_file'.

    If 'this_file' is not given, then we'll return the directory
    of this file...
    """
    if this_file is None:
        this_file = __file__
    this_file = os.path.abspath(this_file)
    this_dir = os.path.split(this_file)[0]
    return this_dir

def get_parent_dir(this_file=None):
    """Determine the path of our parent directory.

    If 'this_file' is not given, then we'll return the parent directory
    of this file...
    """
    this_dir = get_this_dir(this_file)
    parent_dir = os.path.split(this_dir)[0]
    return parent_dir

THIS_DIR = get_this_dir()
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

def git(cmd, verbose=True):
    """Run 'git', with the given arguments

    E.g., git('add fred.c')
    """
    shell('git %s'%cmd)

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

def append(filename, content, verbose=True):
    """Append 'content' to the given file
    """
    if verbose:
        print '++ append to %s'%filename
    with open(filename, 'a') as fd:
        fd.write(content)
# -----------------------------------------------------------------------------

weld_xml_file = """\
<?xml version="1.0" ?>
<weld name="frank">
  <origin uri="file://{testdir}/fromble" />

  <!-- The original had a branch, a revision and a tag.
       My testing isn't working with branches yet, and the implementation
       of weld doesn't "clone" with a revision and tag yet (it's got a bug,
       specifically it tries to do "git clone -r <rev> -r <tag>" and there
       is no "-r" switch). Also, I'm doubtful that it makes sense to specify
       more than one of branch, revision and tag. Weld currently just chooses
       one (in some internally specified order), but it might be better if
       it refused the weld file in this case (although note that muddle also
       has something of this problem).

  <base name="project124" uri="file://{testdir}/project124" branch="b" rev=".." tag=".."/>
  -->

  <base name="project124" uri="file://{testdir}/project124"/>
    <seam base="project124" dest="124" />
  <base name="igniting_duck" uri="file://{testdir}/igniting_duck" />
    <seam base="igniting_duck" source="one" dest="one-duck" />
    <seam base="igniting_duck" source="two" dest="two-duck" />
</weld>
"""

gitignore_ducks = """\
# Ignore our executables
one-duck/one
two-duck/two
124/one/one
124/two/two
"""

def ensure_got_withdir():
    """Make sure we've got a local copy of 'withdir'
    """
    if not os.path.exists('withdir'):
        shell('git clone https://github.com/tibs/withdir.git withdir')
    sys.path.append(os.path.abspath('withdir'))

# Side effects! In a module!
ensure_got_withdir()
from withdir import Directory, NewDirectory, TransientDirectory, \
        NewCountedDirectory, normalise_dir

def build_repo_subdir(repo_name, name):
    """Build an example repository sub-directory.
    """
    c_file = '%s.c'%name
    touch('Makefile', '# An empty makefile\n')
    touch(c_file, '// An empty C file\n')
    git('add Makefile %s'%c_file)
    git('commit -m "Initial commit of %s"'%name)
    append('Makefile',
            '\nall: {name}\n\n{name}: {c_file}\n'.format(name=name,
                c_file=c_file))
    append(c_file, '#include "stdio.h"\n\nmain()\n{\n  printf("Hello world,'
           ' this is %s/%s\\n");\n  return 0;\n}\n'%(' '.join(repo_name.split('_')),
               name))
    git('add Makefile %s'%c_file)
    git('commit -m "Second commit of %s - maybe it does something"'%name)

def build_repo(repo, repo_name, subdir_names):
    """Build an example repository.
    """
    git('clone %s %s'%(repo, repo_name))
    with Directory(repo_name):
        for name in subdir_names:
            with NewDirectory(name):
                build_repo_subdir(repo_name, name)
        git('push origin master')

def make_and_run(name):
    shell('make')
    shell('./%s'%name)

def make_and_run_all(repo_name, subdir_names):
    with Directory(repo_name):
        for name in subdir_names:
            with Directory(name):
                make_and_run(name)

def muddle(cmd, verbose=True):
    """Run 'muddle', with the given arguments

    E.g., muddle('pull')
    """
    MUDDLE = normalise_dir('~tibs/sw/muddle/muddle')    # XXX NOT PORTABLE!!!
    shell('%s %s'%(MUDDLE, cmd))

def main(args):

    keep = False
    while args:
        word = args.pop(0)
        if word in ('-h', '-help', '--help'):
            print __doc__
            return                  # really? is this success
        elif word == '-keep':
            keep = True
        else:
            raise GiveUp('Unexpected command line argument %r'%word)

    with TransientDirectory(#'transient',
                            keep_on_error=True,
                            keep_anyway=keep) as transient:
        # Set up our (empty) repositories
        with NewDirectory('repos') as r:
            # Our normal "source" repositories are normal bare repositories
            with NewDirectory('project124') as project124_base:
                git('init --bare')
                r_project124 = project124_base.where
            with NewDirectory('igniting_duck') as igniting_duck_base:
                git('init --bare')
                r_igniting_duck = igniting_duck_base.where

            repo_base = r.where

        # Create some original content
        with NewDirectory('original'):

            # Source packages
            project124 = 'project124'
            project124_dirs = ['one', 'two']
            build_repo(r_project124, project124, project124_dirs)

            igniting_duck = 'igniting_duck'
            igniting_duck_dirs = ['one', 'two']
            build_repo(r_igniting_duck, igniting_duck, igniting_duck_dirs)

            # Check they build and run
            make_and_run_all(project124, project124_dirs)
            make_and_run_all(igniting_duck, igniting_duck_dirs)

        with Directory('repos') as r:
            touch('weld.xml', weld_xml_file.format(testdir=repo_base))

            # A weld is actually a source (not bare) repository
            with NewDirectory('fromble') as fromble_base:
                weld('init ../weld.xml')
                weld('pull _all')
                r_fromble = fromble_base.where

        # So, can we clone our weld?
        with NewCountedDirectory('test'):
            git('clone %s'%r_fromble)
            # That should give us:
            #
            # * fromble/124/one
            # * fromble/124/two
            # * fromble/one-duck/one
            # * fromble/two-duck/two
            with Directory('fromble'):
                make_and_run_all('124', ['one', 'two'])
                with Directory('one-duck'):
                    make_and_run('one')
                with Directory('two-duck'):
                    make_and_run('two')

                append('.gitignore', gitignore_ducks)
                git('add .gitignore')
                git('commit -m "Ignore executables"')

                weld('pull _all')
                # Whilst it's not really something one is meant to do...
                with Directory('.weld'):
                    with Directory('bases'):
                        make_and_run_all('project124', ['one', 'two'])
                        make_and_run_all('igniting_duck', ['one', 'two'])
                        # ...and since we weren't meant to do that, tidy up
                        shell('rm project124/one/one')
                        shell('rm project124/two/two')
                        shell('rm igniting_duck/one/one')
                        shell('rm igniting_duck/two/two')

        if keep:
            print 'By the way, the transient directory is', transient.where


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
