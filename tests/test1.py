#! /usr/bin/env python2

"""Initial tests for weld
"""

import os
import subprocess
import sys
import traceback

from support_for_tests import *

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

    Return its path.
    """
    git('clone %s %s'%(repo, repo_name))
    with Directory(repo_name) as repo_dir:
        for name in subdir_names:
            with NewDirectory(name):
                build_repo_subdir(repo_name, name)
        git('push origin master')
    return repo_dir.where

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
        banner('Setting up empty repositories')
        with NewDirectory('repos') as repo_base:
            # Our normal "source" repositories are normal bare repositories
            with NewDirectory('project124') as project124_repo:
                git('init --bare')
            with NewDirectory('igniting_duck') as igniting_duck_repo:
                git('init --bare')

        # Create some original content
        banner('Creating content')
        with NewDirectory('original') as orig_dir:

            # Source packages
            project124 = 'project124'
            project124_dirs = ['one', 'two']
            project124_orig = build_repo(project124_repo.where, project124, project124_dirs)

            igniting_duck = 'igniting_duck'
            igniting_duck_dirs = ['one', 'two']
            igniting_duck_orig = build_repo(igniting_duck_repo.where, igniting_duck, igniting_duck_dirs)

            # Check they build and run
            make_and_run_all(project124, project124_dirs)
            make_and_run_all(igniting_duck, igniting_duck_dirs)

        banner('Creating "source" weld')
        with Directory(repo_base.where):
            touch('weld.xml', weld_xml_file.format(testdir=repo_base.where))

            # A weld is actually a source (not bare) repository
            with NewDirectory('fromble') as fromble_base:
                weld('init ../weld.xml')
                print 'Comparing tree', fromble_base.where
                dt = DirTree('.', fold_dirs=['.git', '.weld'])
                dt.assert_same_as_list(['./',
                                        '  .git/...',
                                        '  .gitignore',
                                        '  .weld/...',
                                        ], 'expected')

                weld('pull _all')
                print 'Comparing tree', fromble_base.where
                dt = DirTree(fromble_base.where, fold_dirs=['.git', '.weld'])
                dt.assert_same_as_list(['  .git/...',
                                        '  .gitignore',
                                        '  .weld/...',
                                        '  124/',
                                        '    one/',
                                        '      Makefile',
                                        '      one.c',
                                        '    two/',
                                        '      Makefile',
                                        '      two.c',
                                        '  one-duck/',
                                        '    Makefile',
                                        '    one.c',
                                        '  two-duck/',
                                        '    Makefile',
                                        '    two.c',
                                        ], 'expected', onedown=True)

        # So, can we clone our weld?
        # This is how we are meant to get a copy of the weld to work on
        banner('Cloning source weld')
        with NewCountedDirectory('test') as test1:
            # Because we're using git to clone it, we *could* change the
            # name of the directory we extract into, but we're not going to
            git('clone %s'%fromble_base.where)
            # Remember that our weld.xml does redirect some of the "internal"
            # directories (in particular, of igniting_duck) so they get put
            # somewhere else in our source tree.

            dt = DirTree('fromble', fold_dirs=['.git', '.weld'])
            dt.assert_same_as_list(['fromble/',
                                    '  .git/...',
                                    '  .gitignore',
                                    '  .weld/...',
                                    '  124/',
                                    '    one/',
                                    '      Makefile',
                                    '      one.c',
                                    '    two/',
                                    '      Makefile',
                                    '      two.c',
                                    '  one-duck/',
                                    '    Makefile',
                                    '    one.c',
                                    '  two-duck/',
                                    '    Makefile',
                                    '    two.c',
                                    ], 'expected')

            with Directory('fromble'):
                # And from that we should be able to build/run
                #
                # * fromble/124/one
                # * fromble/124/two
                # * fromble/one-duck/one
                # * fromble/two-duck/two
                make_and_run_all('124', ['one', 'two'])
                with Directory('one-duck'):
                    make_and_run('one')
                with Directory('two-duck'):
                    make_and_run('two')

                # Various weld commands don't like having uncommitted files
                # around (notably because "git status" gets upset), so let's
                # ensure we ignore the executables we just built
                append('.gitignore', gitignore_ducks)
                git('add .gitignore')
                git('commit -m "Ignore executables"')

                # And we can then update the "internal" copies of the source
                # repositories we are using, via:
                weld('pull _all')
                # This is the same sort of downloading that "weld query base"
                # would have to do on an individual base-at-a-time basis -
                # we're doing it all at once

                # Whilst it's not really something one is meant to do, we can
                # then demonstrate that those *are* the source repositories
                # that we have downloaded
                with Directory('.weld'):
                    dt = DirTree('bases', fold_dirs=['.git', '.weld'])
                    dt.assert_same_as_list(['bases/',
                                            '  igniting_duck/',
                                            '    .git/...',
                                            '    one/',
                                            '      Makefile',
                                            '      one.c',
                                            '    two/',
                                            '      Makefile',
                                            '      two.c',
                                            '  project124/',
                                            '    .git/...',
                                            '    one/',
                                            '      Makefile',
                                            '      one.c',
                                            '    two/',
                                            '      Makefile',
                                            '      two.c',
                                            ], 'expected')
                    with Directory('bases'):
                        make_and_run_all('project124', ['one', 'two'])
                        make_and_run_all('igniting_duck', ['one', 'two'])
                        # ...and since we weren't meant to do that, tidy up
                        shell('rm project124/one/one')
                        shell('rm project124/two/two')
                        shell('rm igniting_duck/one/one')
                        shell('rm igniting_duck/two/two')

        # Alter (update) project124 in its repository
        banner('Alter repository for project124')
        with Directory(project124_orig):
            with NewDirectory('three'):
                build_repo_subdir('project124', 'three')
            git('push')

        # And check we can pull that using weld
        banner('Pull into cloned weld')
        with Directory(test1.where):
            with Directory('fromble'):
                weld('pull project124')

                dt = DirTree('.', fold_dirs=['.git', '.weld'])
                dt.assert_same_as_list(['./',
                                        '  .git/...',
                                        '  .gitignore',
                                        '  .weld/...',
                                        '  124/',
                                        '    one/',
                                        '      Makefile',
                                        '      one*',
                                        '      one.c',
                                        '    three/',
                                        '      Makefile',
                                        '      three.c',
                                        '    two/',
                                        '      Makefile',
                                        '      two*',
                                        '      two.c',
                                        '  one-duck/',
                                        '    Makefile',
                                        '    one*',
                                        '    one.c',
                                        '  two-duck/',
                                        '    Makefile',
                                        '    two*',
                                        '    two.c',
                                        ], 'expected')

                # And our .weld directory should also have been updated
                with Directory('.weld'):
                    dt = DirTree('bases', fold_dirs=['.git', '.weld'])
                    dt.assert_same_as_list(['bases/',
                                            '  igniting_duck/',
                                            '    .git/...',
                                            '    one/',
                                            '      Makefile',
                                            '      one.c',
                                            '    two/',
                                            '      Makefile',
                                            '      two.c',
                                            '  project124/',
                                            '    .git/...',
                                            '    one/',
                                            '      Makefile',
                                            '      one.c',
                                            '    three/',
                                            '      Makefile',
                                            '      three.c',
                                            '    two/',
                                            '      Makefile',
                                            '      two.c',
                                            ], 'expected')

        # *However* this does not update the "intermediate" weld repository
        # that we first cloned
        banner('Pull into source weld')
        with Directory(fromble_base.where):
            dt = DirTree('.', fold_dirs=['.git', '.weld'])
            dt.assert_same_as_list(['./',
                                    '  .git/...',
                                    '  .gitignore',
                                    '  .weld/...',
                                    '  124/',
                                    '    one/',
                                    '      Makefile',
                                    '      one.c',
                                    '    two/',
                                    '      Makefile',
                                    '      two.c',
                                    '  one-duck/',
                                    '    Makefile',
                                    '    one.c',
                                    '  two-duck/',
                                    '    Makefile',
                                    '    two.c',
                                    ], 'expected')

            # So we need to do:
            weld('pull _all')
            # here as well, and then:
            dt = DirTree('.', fold_dirs=['.git', '.weld'])
            dt.assert_same_as_list(['./',
                                    '  .git/...',
                                    '  .gitignore',
                                    '  .weld/...',
                                    '  124/',
                                    '    one/',
                                    '      Makefile',
                                    '      one.c',
                                    '    three/',
                                    '      Makefile',
                                    '      three.c',
                                    '    two/',
                                    '      Makefile',
                                    '      two.c',
                                    '  one-duck/',
                                    '    Makefile',
                                    '    one.c',
                                    '  two-duck/',
                                    '    Makefile',
                                    '    two.c',
                                    ], 'expected')

        if keep:
            print
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
