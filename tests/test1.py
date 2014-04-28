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

def make_and_run(where, target=None, program=None):
    if target is None:
        target = where
    if program is None:
        program = target
    with Directory(where):
        shell('make %s'%target)
        shell('./%s'%program)

def make_and_run_all(repo_name, subdir_names):
    """In directory 'repo_name', make and run in each of 'subdir_names'

    (assumes each subdir therein has a program of the same name)
    """
    with Directory(repo_name):
        for name in subdir_names:
            make_and_run(name)

def muddle(cmd, verbose=True):
    """Run 'muddle', with the given arguments

    E.g., muddle('pull')
    """
    MUDDLE = normalise_dir('~tibs/sw/muddle/muddle')    # XXX NOT PORTABLE!!!
    shell('%s %s'%(MUDDLE, cmd))

def weld_query_base(base_name):
    """Run "weld query base 'base_name'" and dissect its results

    Returns <last merge id>, <base merge id>, <base HEAD id>

    All will be strings containing a SHA1 id, except that <base merge id> may
    be None (not a string, actual None)
    """
    text = weld_get_output('query base %s'%base_name)
    lines = text.splitlines()
    last_merge_line = lines[-5]
    base_merge_line = lines[-4]
    last_push_line  = lines[-3]
    base_push_line  = lines[-2]
    base_head_line  = lines[-1]

    last_merge = last_merge_line.split()[-1]
    base_merge = base_merge_line.split()[-1]
    last_push  = last_push_line.split()[-1]
    base_push  = base_push_line.split()[-1]
    base_head  = base_head_line.split()[-1]

    if base_merge == 'None':
        base_merge = None

    if base_push == 'None':
        base_push = None

    return last_merge, base_merge, last_push, base_push, base_head

def git_rev_parse(what):
    """Return the SHA1 id for 'what'
    """
    text = shell_get_output('git rev-parse %s'%what, verbose=False)
    return text.strip()

def compare_dir(where, content_list):
    """Compare the content of 'where' against 'content_list'.

    Folds .git and .weld
    """
    print 'Comparing directory tree', normalise_path(where)
    dt = DirTree(where, fold_dirs=['.git', '.weld'])
    dt.assert_same_as_list(content_list, 'expected', onedown=True)

def test():
    """Our main test script
    """
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
            compare_dir(fromble_base.where,
                       ['  .git/...',
                        '  .gitignore',
                        '  .weld/...',
                       ])
            weld('pull _all')
            compare_dir(fromble_base.where,
                       ['  .git/...',
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
                        ])

    # So, can we clone our weld?
    # This is how we are meant to get a copy of the weld to work on
    banner('Cloning source weld')
    with NewCountedDirectory('test') as test1:
        # Because we're using git to clone it, we *could* change the
        # name of the directory we extract into, but we're not going to
        #
        # git 1.7.10 introduces the --single-branch switch, which does what
        # it suggests. If we use this, then we won't get the "weld-"
        # branches from the original weld repository copied over, which
        # leads to a neater appearance in gitk (!)
        git('clone --single-branch %s'%fromble_base.where)
        # Remember that our weld.xml does redirect some of the "internal"
        # directories (in particular, of igniting_duck) so they get put
        # somewhere else in our source tree.

        compare_dir('fromble',
                    ['  .git/...',
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
                     ])

        with Directory('fromble') as fromble_test:

            fromble_test_clone_id = git_rev_parse('HEAD')

            # And from that we should be able to build/run
            #
            # * fromble/124/one
            # * fromble/124/two
            # * fromble/one-duck/one
            # * fromble/two-duck/two
            make_and_run_all('124', ['one', 'two'])
            make_and_run('one-duck', 'one')
            make_and_run('two-duck', 'two')

            # Various weld commands don't like having uncommitted files
            # around (notably because "git status" gets upset), so let's
            # ensure we ignore the executables we just built
            append('.gitignore', gitignore_ducks)
            git('add .gitignore')
            git('commit -m "Fromble: Ignore executables"')

            # And we can then update the "internal" copies of the source
            # repositories we are using, via:
            weld('pull _all')
            # This is the same sort of downloading that "weld query base"
            # would have to do on an individual base-at-a-time basis -
            # we're doing it all at once

            # Whilst it's not really something one is meant to do, we can
            # then demonstrate that those *are* the source repositories
            # that we have downloaded
            compare_dir(os.path.join('.weld', 'bases'),
                        ['  igniting_duck/',
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
                         ])

            with Directory('.weld'):
                with Directory('bases'):
                    make_and_run_all('project124', ['one', 'two'])
                    make_and_run_all('igniting_duck', ['one', 'two'])
                    # ...and since we weren't meant to do that, tidy up
                    os.unlink(os.path.join('project124', 'one', 'one'))
                    os.unlink(os.path.join('project124', 'two', 'two'))
                    os.unlink(os.path.join('igniting_duck', 'one', 'one'))
                    os.unlink(os.path.join('igniting_duck', 'two', 'two'))

            fromble_test_first_pull_id = git_rev_parse('HEAD')

    # Alter (update) project124 in its repository
    banner('Alter original and repository for project124')
    with Directory(project124_orig):
        with NewDirectory('three'):
            build_repo_subdir('project124', 'three')
        git('push')

    # And check we can pull that using weld
    banner('Pull into cloned weld')
    with Directory(fromble_test.where):
        weld('pull project124')

        compare_dir('.',
                    ['  .git/...',
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
                     ])

        # And our .weld directory should also have been updated
        compare_dir(os.path.join('.weld', 'bases'),
                    ['  igniting_duck/',
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
                     ])

    # *However* this does not update the "intermediate" weld repository
    # that we first cloned
    banner('Pull into source weld')
    with Directory(fromble_base.where):
        compare_dir('.',
                    ['  .git/...',
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
                     ])

        # So we need to do:
        weld('pull _all')
        # here as well, and then:
        compare_dir('.',
                    ['  .git/...',
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
                     ])

    banner('Amend the checked out sources')
    with Directory(fromble_test.where):
        fromble_test_id_before_three_plus = git_rev_parse('HEAD')
        with Directory('124'):
            with Directory('three'):
                touch('three-and-a-bit.c',
                      '#include "stdio.h"\n\nmain()\n{\n  printf("Hello world,'
                      ' this is 123/3-and-a-bit\\n");\n  return 0;\n}\n')
                append('Makefile',
                       '\nthree-and-a-bit: three-and-a-bit.c\n\n')
                git('add three-and-a-bit.c Makefile')
                git('commit -m "124: Add three-and-a-bit"')
        with Directory('two-duck'):
            append('Makefile', '\n# Look, this comment does nothing')
            git('add Makefile')
            git('commit -m "Two-duck: Add a comment to the end of the Makefile"')
            append('Makefile', '\ntwo-duck: two.c\n\t$(CC) -o two-duck two.c\n')
            git('add Makefile')
            git('commit -m "Two-duck: Also build two-duck, same as two"')

        fromble_test_id_after_three_plus = git_rev_parse('HEAD')

        make_and_run_all('124', ['one', 'two', 'three'])
        make_and_run(os.path.join('124', 'three'), 'three-and-a-bit')
        make_and_run('one-duck', 'one')
        make_and_run('two-duck', 'two')
        make_and_run('two-duck', 'two-duck')

        compare_dir('.',
                    ['  .git/...',
                     '  .gitignore',
                     '  .weld/...',
                     '  124/',
                     '    one/',
                     '      Makefile',
                     '      one*',
                     '      one.c',
                     '    three/',
                     '      Makefile',
                     '      three*',
                     '      three-and-a-bit*',
                     '      three-and-a-bit.c',
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
                     '    two-duck*',
                     '    two.c',
                     ])

    # Alter (update) project124 in its repository again
    banner('Alter repository for project124 (again)')
    with Directory(project124_orig):
        project124_id_before_four = git_rev_parse('HEAD')
        with NewDirectory('four'):
            build_repo_subdir('project124', 'four')
        git('push')
        project124_id_after_four = git_rev_parse('HEAD')

    # Summary:
    #
    # Locally, we have made alterations to both 124 and to two-duck
    # Remotely, "someone else" has made alterations to project124
    #
    # So, "pushing" two-duck is relatively simple - we need to fold its
    # changes back into our base igniting_duck, and push that.
    #
    # It's a bit less certain what to do for project124, as there are
    # changes (since the last Merge event) both far and near.
    # Of course, so far as "this end" is concerned, we don't "know" about
    # the far changes yet - they've not been "pulled" into our local 124
    # directory. Maybe that's just an argument for doing "weld pull" before
    # doing "weld push" - much as one should with git itself. If we go
    # with that, then we should perform all the merging on the "visible"
    # side (i.e., in our main directories, not in our .weld/bases),
    # and applying the patch to the .weld/bases/<base> should then Just
    # Work, since any conflicts have already been resolved...
    #
    # Given the above, should we note that a "weld pull" is needed, and
    # tell the user they *must* sort it out before we can allow "weld push"?
    # Can we tell?
    #
    # XXX And don't forget the other thing I've not looked at yet, which
    # XXX is editing the weld.xml file (.weld/welded.xml, I suppose) and
    # XXX wanting to push *that*.
    # XXX
    # XXX For both pulling and pushing, we need to consider (the
    # XXX appropriate end):
    # XXX
    # XXX a) adding a new base or seam to the XML file
    # XXX b) removing a base or seam from the XML file
    # XXX c) changing a seam in the XML file (ick)
    #
    # (Does "weld pull" check that the XML file hasn't changed? Does it
    # try pulling it? It is under git control, as is the top-level
    # .gitignore)

    def print_sha1_ids(last_merge, base_merge, last_push, base_push, base_head):
        print 'last merge ', last_merge[:10]
        if base_merge is None:
            print 'base merge  None'
        else:
            print 'base merge ', base_merge[:10]
        print 'last push  ', last_push[:10]
        if base_push is None:
            print 'base push   None'
        else:
            print 'base push  ', base_push[:10]
        print 'base HEAD  ', base_head[:10]

    # But this time, delibarately don't alter anything else
    with Directory(fromble_test.where):
        # Querying base project124 will update .weld/bases/project124
        # and thus reflect the difference between its HEAD and the
        # last commit we merged from it. It won't, of course, update
        # our checked out 124 directory.
        (last_124_merge1, base_124_merge1, last_124_push1, base_124_push1,
                base_124_head1) = weld_query_base('project124')
        print_sha1_ids(last_124_merge1, base_124_merge1, last_124_push1,
                       base_124_push1, base_124_head1)

        # Similarly for igniting_duck
        (last_ign_merge1, base_ign_merge1, last_ign_push1, base_ign_push1,
                base_ign_head1) = weld_query_base('igniting_duck')
        print_sha1_ids(last_ign_merge1, base_ign_merge1, last_ign_push1,
                       base_ign_push1, base_ign_head1)

        with Directory(os.path.join('.weld', 'bases', 'project124')):
            assert base_124_head1 == git_rev_parse('HEAD')

        with Directory(os.path.join('.weld', 'bases', 'igniting_duck')):
            assert base_ign_head1 == git_rev_parse('HEAD')

        fromble_test_head1 = git_rev_parse('HEAD')

        print
        print 'fromble test:'
        print '    HEAD                  ', fromble_test_head1[:10]
        print '    before three-and-a-bit', fromble_test_id_before_three_plus[:10], '(last merge)'
        print '    after  three-and-a-bit', fromble_test_id_after_three_plus[:10], '(local head)'
        print 'project124'
        print '    HEAD                  ', base_124_head1[:10]
        print '    before four           ', project124_id_before_four[:10], '(base merge)'
        print '    after  four           ', project124_id_after_four[:10], '(base head)'
        print 'igniting_duck'
        print '    HEAD                  ', base_ign_head1[:10]

        assert fromble_test_id_before_three_plus == last_124_merge1
        assert project124_id_before_four         == base_124_merge1
        assert project124_id_after_four          == base_124_head1

        print
        print 'fromble test: What changed from last merge with project124 to HEAD'
        shell('git --no-pager log --oneline %s..HEAD 124'%last_124_merge1)
        print

        with Directory(os.path.join('.weld', 'bases', 'project124')):
            print
            print 'base project124: What changed from last merge to its HEAD'
            shell('git --no-pager log --oneline %s..HEAD'%base_124_merge1)
            print

        print
        print 'fromble test: What changed from last merge with igniting_duck to HEAD'
        shell('git --no-pager log --oneline %s..HEAD one-duck two-duck'%last_ign_merge1)
        print

        with Directory(os.path.join('.weld', 'bases', 'igniting_duck')):
            print
            print 'base igniting_duck: What changed from last merge to its HEAD'
            shell('git --no-pager log --oneline %s..HEAD'%base_ign_merge1)
            print


        # Remove the executables that we built (which are not tracked by git,
        # and so will prevent us doing "weld pull")
        os.unlink(os.path.join('124', 'three', 'three'))
        os.unlink(os.path.join('124', 'three', 'three-and-a-bit'))
        os.unlink(os.path.join('two-duck', 'two-duck'))

        # At which point we can do a "weld pull _all" to update our world...
        weld('pull _all')

        # And redo our various queries
        (last_124_merge2, base_124_merge2, last_124_push2, base_124_push2,
                base_124_head2) = weld_query_base('project124')
        print_sha1_ids(last_124_merge2, base_124_merge2, last_124_push2,
                       base_124_push2, base_124_head2)

        # Similarly for igniting_duck
        (last_ign_merge2, base_ign_merge2, last_ign_push2, base_ign_push2,
                base_ign_head2) = weld_query_base('igniting_duck')
        print_sha1_ids(last_ign_merge2, base_ign_merge2, last_ign_push2,
                       base_ign_push2, base_ign_head2)

        with Directory(os.path.join('.weld', 'bases', 'project124')):
            assert base_124_head2 == git_rev_parse('HEAD')

        with Directory(os.path.join('.weld', 'bases', 'igniting_duck')):
            assert base_ign_head2 == git_rev_parse('HEAD')

        fromble_test_head2 = git_rev_parse('HEAD')

        print
        print 'fromble test:'
        print '    HEAD                  ', fromble_test_head2[:10]
        print '    before three-and-a-bit', fromble_test_id_before_three_plus[:10], '(last merge)'
        print '    after  three-and-a-bit', fromble_test_id_after_three_plus[:10], '(local head)'
        print 'project124'
        print '    HEAD                  ', base_124_head2[:10]
        print '    before four           ', project124_id_before_four[:10], '(base merge)'
        print '    after  four           ', project124_id_after_four[:10], '(base head)'
        print 'igniting_duck'
        print '    HEAD                  ', base_ign_head2[:10]

        assert fromble_test_head2         == last_124_merge2
        assert project124_id_after_four   == base_124_merge2 # it moved
        assert project124_id_after_four   == base_124_head2

        print
        print 'fromble test: What changed from last merge with project124 to HEAD'
        shell('git --no-pager log --oneline %s..HEAD 124'%last_124_merge2)
        print

        with Directory(os.path.join('.weld', 'bases', 'project124')):
            print
            print 'base project124: What changed from last merge to its HEAD'
            shell('git --no-pager log --oneline %s..HEAD'%base_124_merge2)
            print

        print
        print 'fromble test: What changed from last merge with igniting_duck to HEAD'
        shell('git --no-pager log --oneline %s..HEAD one-duck two-duck'%last_ign_merge2)
        print

        with Directory(os.path.join('.weld', 'bases', 'igniting_duck')):
            print
            print 'base igniting_duck: What changed from last merge to its HEAD'
            shell('git --no-pager log --oneline %s..HEAD'%base_ign_merge2)
            print

        # So after the "weld pull", we've successfully merged in the far
        # changes, but we've still got stuff we want to push that occurs
        # *before* the "last Merge with project124" (which is now the HEAD
        # checkin).

        fromble_test_remote_master_id = git_rev_parse('remotes/origin/master')

        print 'Fromble test after clone     ', fromble_test_clone_id[:10]
        print 'Fromble test after first pull', fromble_test_first_pull_id[:10]
        print 'Fromble test remote master   ', fromble_test_remote_master_id[:10]

        print
        print 'fromble test: What changed for project124 from remote master to HEAD'
        shell('git --no-pager log --oneline %s..HEAD 124'%fromble_test_remote_master_id)
        print

        print
        print 'fromble test: What changed for project124 from remote master to last merge'
        shell('git --no-pager log --oneline %s..%s 124'%(fromble_test_remote_master_id,
                                                         last_124_merge2))
        print

        print
        print 'fromble test: What changed for igniting_duck from remote master to HEAD'
        shell('git --no-pager log --oneline %s..HEAD one-duck two-duck'%fromble_test_remote_master_id)
        print

    # And then start investigating what "weld push" should do...

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
        test()

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
