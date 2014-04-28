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

    Returns a six-tuple, containing:

        <last_merge_weld>, <last_merge_base>, <last_push_weld>,
        <last_push_base>, <base_head>, <weld_init>

    All will be strings containing a SHA1 id, except that the first four
    be None (not a string, actual None) indicating that there was no last
    merge or push (respectively) - we expect both the merge and/or both the
    push values to be None if either is.
    """
    text = weld_get_output('query base %s'%base_name)
    lines = text.splitlines()
    last_merge_weld_line = lines[-6]
    last_merge_base_line = lines[-5]
    last_push_weld_line  = lines[-4]
    last_push_base_line  = lines[-3]
    base_head_line  = lines[-2]
    weld_init_line  = lines[-1]

    last_merge_weld = last_merge_weld_line.split()[-1]
    last_merge_base = last_merge_base_line.split()[-1]
    last_push_weld  = last_push_weld_line.split()[-1]
    last_push_base  = last_push_base_line.split()[-1]
    base_head  = base_head_line.split()[-1]
    weld_init  = weld_init_line.split()[-1]

    if last_merge_base == 'None':
        last_merge_base = None

    if last_push_weld == 'None':
        last_push_weld = None

    if last_merge_base == 'None':
        last_merge_base = None

    if last_push_weld == 'None':
        last_push_weld = None

    return (last_merge_weld, last_merge_base,
            last_push_weld, last_push_base,
            base_head, weld_init)

def git_rev_parse(what):
    """Return the SHA1 id for 'what'
    """
    text = shell_get_output('git rev-parse %s'%what, verbose=False)
    return text.strip()

def git_log_for(from_id, to_id, paths=None):
    """Do a git log for "<from_id>..<to_id> -- <paths>"

    Returns a sequence of lines.
    """
    if paths:
        cmd = 'git --no-pager log --oneline %s..%s -- %s'%(from_id, to_id,
                ' '.join(repr(x) for x in paths))
    else:
        cmd = 'git --no-pager log --oneline %s..%s'%(from_id, to_id)
    changes = shell_get_output(cmd)
    return changes.splitlines()

def compare_dir(where, content_list):
    """Compare the content of 'where' against 'content_list'.

    Folds .git and .weld
    """
    print 'Comparing directory tree', normalise_path(where)
    dt = DirTree(where, fold_dirs=['.git', '.weld'])
    dt.assert_same_as_list(content_list, 'expected', onedown=True)

def first_path_item(path):
    """Return the first element from a path

    This is somewhat icky, and surely slow...

    >>> first_path_item('')
    ''
    >>> first_path_item('/')
    ''
    >>> first_path_item('//')
    ''
    >>> first_path_item('a')
    'a'
    >>> first_path_item('a/b')
    'a'
    >>> first_path_item('a/b/c')
    'a'
    """
    rest = ''
    while path and path[0] == '/':
        path = path[1:]
    while path:
        path, rest = os.path.split(path)
    return rest

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

        # Let's also make a (trivial) change to the welded.xml file
        # - we shall be careful not to change anything significant
        with Directory('.weld'):
            append('welded.xml', '<!-- An insignificant comment -->\n')
            git('commit welded.xml -m "Fromble: Add an insignificant coment"')

        # And, to be cruel, a change across everything...
        append('.gitignore', '# a trailing comment\n')
        append(os.path.join('124', 'three', 'Makefile'), '# a trailing comment\n')
        append(os.path.join('one-duck', 'Makefile'), '# a trailing comment\n')
        git('commit -a -m "Add trailing comments across the bases and to the weld"')

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

    def print_sha1_ids(last_merge, base_merge, last_push, base_push, base_head, weld_init):
        if last_merge is None:
            print 'last merge, weld  None'
        else:
            print 'last merge, weld ', last_merge[:10]
        if base_merge is None:
            print '            base  None'
        else:
            print '            base ', base_merge[:10]
        if last_push is None:
            print 'last push,  weld  None'
        else:
            print 'last push,  weld ', last_push[:10]
        if base_push is None:
            print '            base  None'
        else:
            print '            base ', base_push[:10]
        print 'base HEAD  ', base_head[:10]
        print 'weld Init  ', weld_init[:10]

    # But this time, delibarately don't alter anything else
    with Directory(fromble_test.where):
        # Querying base project124 will update .weld/bases/project124
        # and thus reflect the difference between its HEAD and the
        # last commit we merged from it. It won't, of course, update
        # our checked out 124 directory.
        (last_124_merge1, base_124_merge1, last_124_push1, base_124_push1,
                base_124_head1, weld_init) = weld_query_base('project124')
        print_sha1_ids(last_124_merge1, base_124_merge1, last_124_push1,
                       base_124_push1, base_124_head1, weld_init)

        # Similarly for igniting_duck
        (last_ign_merge1, base_ign_merge1, last_ign_push1, base_ign_push1,
                base_ign_head1, weld_init) = weld_query_base('igniting_duck')
        print_sha1_ids(last_ign_merge1, base_ign_merge1, last_ign_push1,
                       base_ign_push1, base_ign_head1, weld_init)

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
        lines = git_log_for(last_124_merge1, 'HEAD', ['124'])
        print '\n'.join(lines)
        print

        with Directory(os.path.join('.weld', 'bases', 'project124')):
            print
            print 'base project124: What changed from last merge to its HEAD'
            lines = git_log_for(base_124_merge1, 'HEAD')
            print '\n'.join(lines)
            print

        print
        print 'fromble test: What changed from last merge with igniting_duck to HEAD'
        lines = git_log_for(last_ign_merge1, 'HEAD', ['one-duck', 'two-duck'])
        print '\n'.join(lines)
        print

        with Directory(os.path.join('.weld', 'bases', 'igniting_duck')):
            print
            print 'base igniting_duck: What changed from last merge to its HEAD'
            lines = git_log_for(base_ign_merge1, 'HEAD')
            print '\n'.join(lines)
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
                base_124_head2, weld_init) = weld_query_base('project124')
        print_sha1_ids(last_124_merge2, base_124_merge2, last_124_push2,
                       base_124_push2, base_124_head2, weld_init)

        # Similarly for igniting_duck
        (last_ign_merge2, base_ign_merge2, last_ign_push2, base_ign_push2,
                base_ign_head2, weld_init) = weld_query_base('igniting_duck')
        print_sha1_ids(last_ign_merge2, base_ign_merge2, last_ign_push2,
                       base_ign_push2, base_ign_head2, weld_init)

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
        lines = git_log_for(last_124_merge2, 'HEAD', ['124'])
        print '\n'.join(lines)
        print

        with Directory(os.path.join('.weld', 'bases', 'project124')):
            print
            print 'base project124: What changed from last merge to its HEAD'
            lines = git_log_for(base_124_merge2, 'HEAD')
            print '\n'.join(lines)
            print

        print
        print 'fromble test: What changed from last merge with igniting_duck to HEAD'
        lines = git_log_for(last_ign_merge2, 'HEAD', ['one-duck', 'two-duck'])
        print '\n'.join(lines)
        print

        with Directory(os.path.join('.weld', 'bases', 'igniting_duck')):
            print
            print 'base igniting_duck: What changed from last merge to its HEAD'
            lines = git_log_for(base_ign_merge2, 'HEAD')
            print '\n'.join(lines)
            print

        # So after the "weld pull", we've successfully merged in the far
        # changes, but we've still got stuff we want to push that occurs
        # *before* the "last Merge with project124" (which is now the HEAD
        # checkin).

        fromble_test_remote_master_id = git_rev_parse('remotes/origin/master')

        print 'Fromble test after clone     ', fromble_test_clone_id[:10]
        print 'Fromble test after first pull', fromble_test_first_pull_id[:10]
        print 'Fromble test remote master   ', fromble_test_remote_master_id[:10]

        # We know we didn't have any Push events in our past, so we will be
        # falling back to the Init event, which is the same for everyone

        def trim_states(lines):
            new = []
            for line in lines:
                words = line.split()
                if words[1] != 'X-Weld-State:':
                    new.append(line)
            return new

        print
        print 'fromble test: What changed for everyone from Init to HEAD'
        all_changes = git_log_for(weld_init, 'HEAD')
        print '\n'.join(trim_states(all_changes))

        print
        print 'fromble test: What changed for project124 from Init to HEAD'
        p124_changes = git_log_for(weld_init, 'HEAD', ['124'])
        print '\n'.join(trim_states(p124_changes))

        print
        print 'fromble test: What changed for igniting_duck from Init to HEAD'
        pign_changes = git_log_for(weld_init, 'HEAD', ['one-duck', 'two-duck'])
        print '\n'.join(trim_states(pign_changes))

        print
        print 'Looking at all_changes to see which (if any) bases they are in'
        # Surely we can do this with porcelain? And perhaps more efficiently...
        base_dirs = ['124', 'one-duck', 'two-duck']
        all_changes = trim_states(all_changes)
        weld_changes = []
        for line in all_changes:
            sha1 = line.split()[0]
            print sha1
            changed_files = shell_get_output('git diff --name-only %s^!'%sha1, verbose=False)
            changed_files = changed_files.splitlines()
            weld_files = []
            other_also = []
            for t in changed_files:
                first = first_path_item(t)
                if first in base_dirs:
                    print '  %s in %s'%(t, first)
                    other_also.append(t)
                else:
                    print '  %s only in weld'%t
                    weld_files.append(t)
            if weld_files:
                weld_changes.append( (sha1, weld_files, other_also) )
        print
        print 'The following are changes in the weld:'
        for sha1, files, other_also in weld_changes:
            print '  %s: %s%s'%(sha1, files, ' and also %s'%other_also if other_also else '')
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
