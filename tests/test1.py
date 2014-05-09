#! /usr/bin/env python2

"""Initial tests for weld
"""

import os
import subprocess
import sys
import traceback

from support_for_tests import *

class GiveUp(Exception):
    """Our own version of the commonly named exception...
    """
    pass

weld_xml_file = """\
<?xml version="1.0" ?>
<weld name="frank">
  <origin uri="file://{repo_base}/fromble" />

  <!-- The original had a branch, a revision and a tag.
       My testing isn't working with branches yet, and the implementation
       of weld doesn't "clone" with a revision and tag yet (it's got a bug,
       specifically it tries to do "git clone -r <rev> -r <tag>" and there
       is no "-r" switch). Also, I'm doubtful that it makes sense to specify
       more than one of branch, revision and tag. Weld currently just chooses
       one (in some internally specified order), but it might be better if
       it refused the weld file in this case (although note that muddle also
       has something of this problem).

  <base name="project124" uri="file://{repo_base}/project124" branch="b" rev=".." tag=".."/>
  -->

  <base name="project124" uri="file://{repo_base}/project124"/>
    <seam base="project124" dest="124" />
  <base name="igniting_duck" uri="file://{repo_base}/igniting_duck" />
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

def weld_query_base(weld_root, base_name):
    """Run "weld query base 'base_name'" and dissect its results

    Returns a six-tuple, containing:

        <last_merge_weld>, <last_merge_base>, <last_push_weld>,
        <last_push_base>, <base_head>, <weld_init>

    All will be strings containing a SHA1 id, except that the first four
    be None (not a string, actual None) indicating that there was no last
    merge or push (respectively) - we expect both the merge and/or both the
    push values to be None if either is.
    """
    text = weld_get_output('query base %s'%base_name, cwd=weld_root)
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

    if last_merge_weld == 'None':
        last_merge_weld = None

    if last_push_base == 'None':
        last_push_base = None

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

def git_log_for(where, from_id, to_id, paths=None):
    """Do a git log for "<from_id>..<to_id> -- <paths>"

    Returns a sequence of lines.
    """
    if paths:
        cmd = 'git --no-pager log --oneline %s..%s -- %s'%(from_id, to_id,
                ' '.join(repr(x) for x in paths))
    else:
        cmd = 'git --no-pager log --oneline %s..%s'%(from_id, to_id)
    changes = shell_get_output(cmd, cwd=where)
    return changes.splitlines()

def compare_dir(where, content_list, fold_dirs=['.git', '.weld']):
    """Compare the content of 'where' against 'content_list'.

    Folds .git and .weld
    """
    print 'Comparing directory tree', normalise_path(where)
    dt = DirTree(where, fold_dirs=fold_dirs)
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

# If we have a Merge and a Push, we can use "git merge-base" to
# determine which is the earlier (i.e., the first common ancestor,
# which in our case should be one of the two), and we can then use the
# other.
def later_of_two_commits(a, b):
    """Return the later of two commits on the same "path".

    * If 'a' and 'b' are the same, return 'a' immediately (even if
      both are None).
    * If exactly one of 'a' and 'b' is None, return the other
    * If 'a' is an ancestor of 'b', return 'b'.
    * If 'b' is an ancestor of 'a', return 'a'.
    * Otherwise, we don't know, so we raise a GiveUp exception.
    """
    if a == b:
        return a
    elif a is None:
        return b
    elif b is None:
        return a
    else:
        result = shell_get_output('git merge-base %s %s'%(a, b))
        if result == a:
            return b
        elif result == b:
            return a
        else:
            raise GiveUp('Commits %s and %s do not appear to share a'
                         ' common ancestor, unable to find out which'
                         ' is later'%(a[:10], b[:10]))

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


def trim_states(lines):
    """Return only those lines that do not say "X-Weld-State:"

    (that is, remove any weld state lines)
    """
    new = []
    for line in lines:
        words = line.split()
        if words[1] != 'X-Weld-State:':
            new.append(line)
    return new

from filecmp import dircmp

def diff_matches(d):
    """If the difference matches, return True, else report and return False
    """
    if d.left_only or d.right_only or d.diff_files or d.funny_files:
        print 'Mismatch for %s and %s'%(d.left, d.right)
        if d.left_only:   print 'Left only:', d.left_only
        if d.right_only:  print 'Right only:', d.right_only
        if d.diff_files:  print 'Different:', d.diff_files
        if d.funny_files: print 'Funny:', d.funny_files
        return False
    else:
        return True

def same_files(this_dir, that_dir):
    """Check that the same files are present, with some standard exclusions

    We ignore .git directories (and their contents).

    We ignore .weld/bases directories (and ditto).

    Because of that last, it turns out to be difficult to use GNU diff, since
    it doesn't support ignoring other than a base directory name (possibly
    wildcarded). However, Python to the rescue.
    """
    # Note that this defaults to a "shallow" comparison - two files of the
    # same name with the same os.stat data will be considered identical,
    # without *actually* checking their content. For our purposes this is
    # sufficient, as non-identical files should have different sizes.

    same = True

    # Compare the top-level directory
    d = dircmp(this_dir, that_dir)
    if not diff_matches(d):
        same = False

    # And similarly, compare the top-level of the .weld directory
    this_subdir = os.path.join(this_dir, '.weld')
    that_subdir = os.path.join(that_dir, '.weld')
    d = dircmp(this_subdir, that_subdir)
    if not diff_matches(d):
        same = False

    # Compare other directories
    this_files = os.listdir(this_dir)
    that_files = os.listdir(that_dir)

    this_dirs = set(f for f in this_files if os.path.isdir(os.path.join(this_dir, f)))
    that_dirs = set(f for f in that_files if os.path.isdir(os.path.join(that_dir, f)))
    dirs = this_dirs | that_dirs

    def recursive_same(d):
        same = True
        if not diff_matches(d):
            same = False
        for dirname in d.common_dirs:
            if not recursive_same(d.subdirs[dirname]):
                same = False
        return same

    for dirname in sorted(dirs):
        if dirname in ('.weld', '.git'):
            continue
        this_subdir = os.path.join(this_dir, dirname)
        if not os.path.exists(this_subdir):
            print 'Directory %s does not exist'%this_subdir
            same = False
            continue
        that_subdir = os.path.join(that_dir, dirname)
        if not os.path.exists(that_subdir):
            print 'Directory %s does not exist'%that_subdir
            mismatch = True
            continue
        # Compare the two recursively
        d = dircmp(this_subdir, that_subdir, ignore=[])
        if not recursive_same(d):
            same = False

    return same

def weld_status(verbose=True):
    """Run "weld status" and report on its results.

    We return:

      * True,  None             - need to pull, don't push yet(!)
      * False, True             - need to push
      * False, False            - neither is necessary

    """
    output = shell_get_output('%s status %s --tuple'%(WELD_CMD,
                                           '--verbose' if verbose else ''))
    if verbose:
        print output
    lines = output.splitlines()
    words = lines[-1].split()
    values = [True  if w=='True'  else
              False if w=='False' else
              None  if w=='None'  else '???' for w in words]
    return values[-2:]


def test():
    """Our main test script
    """
    # Set up our (empty) repositories
    banner('Setting up empty repositories')
    with NewDirectory('repos') as repo_base:
        # Note that where we create our weld repository MUST match what
        # it says in the weld XML file - this feels a bit awkward and
        # self-referential...
        # XXX Check how this actually works within weld
        with NewDirectory('fromble') as fromble_repo:
            git('init --bare')
        with NewDirectory('project124') as project124_repo:
            git('init --bare')
        with NewDirectory('igniting_duck') as igniting_duck_repo:
            git('init --bare')

    # Create some original content, and push it to those repositories
    banner('Creating content for those repositories')
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
        touch('weld.xml', weld_xml_file.format(repo_base=repo_base.where))

        with NewDirectory('fromble') as fromble_orig:
            weld('init ../weld.xml')
            compare_dir(fromble_orig.where,
                       ['  .git/...',
                        '  .gitignore',
                        '  .weld/...',
                       ])
            weld('pull _all')
            compare_dir(fromble_orig.where,
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
            git('push origin master')

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
        git('clone %s'%fromble_repo.where)
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

            # At which point:
            need_to_pull, need_to_push = weld_status()
            assert need_to_pull == False
            assert need_to_push == True

            # If we wish our "weld pull _all" to give us a weld that is
            # compatible with the rest of the world and their idea of this
            # weld, then we need to tell that rest of the world about our
            # change to the weld now, before we do the "weld pull"
            git('push origin master')

            # And we can then update our bases
            # This should be a no-op as far as the "main" weld directories
            # are concerned (because we only just cloned them, apart from
            # the .gitignore file which we've push) - so it should just be
            # altering the content of .weld/bases
            compare_dir('.weld', ['  counter',
                                  '  welded.xml',
                                  ], fold_dirs=[])  # don't fold .weld!

            weld('pull _all')
            # This is the same sort of downloading that "weld query base"
            # would have to do on an individual base-at-a-time basis -
            # we're doing it all at once

            # The weld itself hasn't changed...
            compare_dir('.',
                        ['  .git/...',
                         '  .gitignore',
                         '  .weld/...',
                         '  124/',
                         '    one/',
                         '      Makefile',
                         '      one*',
                         '      one.c',
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
                    os.remove(os.path.join('project124', 'one', 'one'))
                    os.remove(os.path.join('project124', 'two', 'two'))
                    os.remove(os.path.join('igniting_duck', 'one', 'one'))
                    os.remove(os.path.join('igniting_duck', 'two', 'two'))

            fromble_test_first_pull_id = git_rev_parse('HEAD')

            # At which point we don't need to pull (with "git pull"),
            # nor do we have anything to push
            need_to_pull, need_to_push = weld_status()
            assert need_to_pull == False
            assert need_to_push == False

    # Alter (update) project124 in its repository
    banner('Alter original and repository for project124')
    with Directory(project124_orig):
        with NewDirectory('three'):
            build_repo_subdir('project124', 'three')
        git('push')

    # And check we can pull that using weld
    banner('Pull into cloned weld')
    with Directory(fromble_test.where):
        weld('pull -v project124')

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

        # Since we've altered our weld, it's ahead of the far weld repo
        need_to_pull, need_to_push = weld_status()
        assert need_to_pull == False
        assert need_to_push == True

        git('push origin master')


    # *However* this does not update the source weld repository, the one
    # that we first created. So we'll need to pull into that by hand.
    banner('Pull into source weld')
    with Directory(fromble_orig.where):
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

        # Just to review where we are
        with Directory(fromble_test.where) as x:
            print
            print 'TEST', x.where
            git('--no-pager log --oneline')

        with Directory(fromble_repo.where) as x:
            print
            print 'REPO', x.where
            git('--no-pager log --oneline')

        with Directory(fromble_orig.where) as x:
            print
            print 'ORIG', x.where
            git('--no-pager log --oneline')

        print

        need_to_pull, need_to_push = weld_status()
        assert need_to_pull == True
        assert need_to_push == None

        # So let's pull
        git('pull origin master')

        # If we do a "weld pull" now, that should only affect the .weld/bases
        weld('pull -v _all')
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

        need_to_pull, need_to_push = weld_status()
        assert need_to_pull == False
        assert need_to_push == False

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

    # But this time, delibarately don't alter anything else
    with Directory(fromble_test.where):
        # Querying base project124 will update .weld/bases/project124
        # and thus reflect the difference between its HEAD and the
        # last commit we merged from it. It won't, of course, update
        # our checked out 124 directory.
        (last_124_merge1, base_124_merge1, last_124_push1, base_124_push1,
                base_124_head1, weld_init) = weld_query_base('.', 'project124')
        print_sha1_ids(last_124_merge1, base_124_merge1, last_124_push1,
                       base_124_push1, base_124_head1, weld_init)

        # Similarly for igniting_duck
        (last_ign_merge1, base_ign_merge1, last_ign_push1, base_ign_push1,
                base_ign_head1, weld_init) = weld_query_base('.', 'igniting_duck')
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
        lines = git_log_for('.', last_124_merge1, 'HEAD', ['124'])
        print '\n'.join(lines)
        print

        with Directory(os.path.join('.weld', 'bases', 'project124')):
            print
            print 'base project124: What changed from last merge to its HEAD'
            lines = git_log_for('.', base_124_merge1, 'HEAD')
            print '\n'.join(lines)
            print

        print
        print 'fromble test: What changed from last merge with igniting_duck to HEAD'
        lines = git_log_for('.', last_ign_merge1, 'HEAD', ['one-duck', 'two-duck'])
        print '\n'.join(lines)
        print

        with Directory(os.path.join('.weld', 'bases', 'igniting_duck')):
            print
            print 'base igniting_duck: What changed from last merge to its HEAD'
            lines = git_log_for('.', base_ign_merge1, 'HEAD')
            print '\n'.join(lines)
            print


        # Remove the executables that we built (which are not tracked by git,
        # and so will prevent us doing "weld pull")
        os.remove(os.path.join('124', 'three', 'three'))
        os.remove(os.path.join('124', 'three', 'three-and-a-bit'))
        os.remove(os.path.join('two-duck', 'two-duck'))

        # So, what is our state with respect to our weld's remote repository?
        need_to_pull, need_to_push = weld_status()
        assert need_to_pull == False
        assert need_to_push == True

        # At which point we can do a "weld pull _all" to update our world...
        weld('pull _all')

        # And redo our various queries
        (last_124_merge2, base_124_merge2, last_124_push2, base_124_push2,
                base_124_head2, weld_init) = weld_query_base('.', 'project124')
        print_sha1_ids(last_124_merge2, base_124_merge2, last_124_push2,
                       base_124_push2, base_124_head2, weld_init)

        # Similarly for igniting_duck
        (last_ign_merge2, base_ign_merge2, last_ign_push2, base_ign_push2,
                base_ign_head2, weld_init) = weld_query_base('.', 'igniting_duck')
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
        lines = git_log_for('.', last_124_merge2, 'HEAD', ['124'])
        print '\n'.join(lines)
        print

        with Directory(os.path.join('.weld', 'bases', 'project124')):
            print
            print 'base project124: What changed from last merge to its HEAD'
            lines = git_log_for('.', base_124_merge2, 'HEAD')
            print '\n'.join(lines)
            print

        print
        print 'fromble test: What changed from last merge with igniting_duck to HEAD'
        lines = git_log_for('.', last_ign_merge2, 'HEAD', ['one-duck', 'two-duck'])
        print '\n'.join(lines)
        print

        with Directory(os.path.join('.weld', 'bases', 'igniting_duck')):
            print
            print 'base igniting_duck: What changed from last merge to its HEAD'
            lines = git_log_for('.', base_ign_merge2, 'HEAD')
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

        print
        print 'fromble test: What changed for everyone from Init to HEAD'
        all_changes = git_log_for('.', weld_init, 'HEAD')
        print '\n'.join(trim_states(all_changes))

        print
        print 'fromble test: What changed for project124 from Init to HEAD'
        p124_changes = git_log_for('.', weld_init, 'HEAD', ['124'])
        print '\n'.join(trim_states(p124_changes))

        print
        print 'fromble test: What changed for igniting_duck from Init to HEAD'
        pign_changes = git_log_for('.', weld_init, 'HEAD', ['one-duck', 'two-duck'])
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

    # Let's push for the first time
    banner('WELD PUSH for the first time')
    banner('weld push -v igniting_duck')
    weld('push -v igniting_duck', cwd=fromble_test.where)
    banner('weld push -v project124')
    weld('push -v project124', cwd=fromble_test.where)

    banner('Amend the checked out sources AGAIN')
    with Directory(fromble_test.where):
        with Directory('124'):
            with Directory('four'):
                touch('four-and-a-bit.c',
                      '#include "stdio.h"\n\nmain()\n{\n  printf("Hello world,'
                      ' this is 123/4-and-a-bit\\n");\n  return 0;\n}\n')
                append('Makefile',
                       '\nfour-and-a-bit: four-and-a-bit.c\n\n')
                git('add four-and-a-bit.c Makefile')
                git('commit -m "124: Add four-and-a-bit"')
        with Directory('one-duck'):
            append('Makefile', '\n# Look, this comment does nothing')
            git('add Makefile')
            git('commit -m "One-duck: Add a comment to the end of the Makefile"')
            append('Makefile', '\none-duck: one.c\n\t$(CC) -o one-duck one.c\n')
            git('add Makefile')
            git('commit -m "One-duck: Also build one-duck, same as one"')

        # Let's also make a (trivial) change to the welded.xml file
        # - we shall be careful not to change anything significant
        with Directory('.weld'):
            append('welded.xml', '<!-- A second insignificant comment -->\n')
            git('commit welded.xml -m "Fromble: Add a second insignificant coment"')

        # And, to be cruel, a change across everything...
        append('.gitignore', '# a trailing comment\n')
        append(os.path.join('124', 'three', 'Makefile'), '# another trailing comment\n')
        append(os.path.join('two-duck', 'Makefile'), '# a trailing comment\n')
        git('commit -a -m "Add more trailing comments across the bases and to the weld"')

        # And finally, an order-dependent change
        # - this should enable us to tell that we're re-applying changes
        # in the correct order
        with Directory('two-duck'):
            with open('Makefile') as fd:
                lines = fd.readlines()
            with open('Makefile', 'w') as fd:
                fd.writelines(lines[:-1])
            git('commit Makefile -m "Remove the earlier trailing comment"')

        # And try a second set of pushing
        banner('WELD PUSH for the second time')
        banner('weld push -v igniting_duck')
        weld('push -v igniting_duck', cwd=fromble_test.where)
        banner('weld push -v project124')
        weld('push -v project124', cwd=fromble_test.where)

        # And we can also push our weld...
        need_to_pull, need_to_push = weld_status()
        assert need_to_pull == False
        assert need_to_push == True

        # So let's do so
        git('push')

    # If we then pull it into the original, we should get the same answer...
    banner('Pull into original should match')
    with Directory(fromble_orig.where):
        need_to_pull, need_to_push = weld_status()
        assert need_to_pull == True
        assert need_to_push == None

        git('pull origin master')

    print 'Checking fromble test and fromble original match'
    # Before comparing directories, remove the executables we built
    with Directory(fromble_test.where):
        os.remove(os.path.join('124', 'one', 'one'))
        os.remove(os.path.join('124', 'two', 'two'))
        os.remove(os.path.join('one-duck', 'one'))
        os.remove(os.path.join('two-duck', 'two'))

    if not same_files(fromble_test.where, fromble_orig.where):
        raise GiveUp('Test directory doesn not match source directory')

    # If there aren't any changes, we shouldn't do anything(!)
    banner('A push of nothing should do nothing')
    banner('weld push igniting_duck')
    weld('push -v igniting_duck', cwd=fromble_test.where)
    banner('weld push project124')
    weld('push project124', cwd=fromble_test.where)

    # Make inconsistent changes at each end...
    def make_inconsistent_changes(n):
        banner('Making inconsistent changes (%d)'%n)
        with Directory(project124_orig):
            with Directory('four'):
                # Make sure it is up-to-date
                git('pull')
                # And make our change
                append('Makefile', '#This is comment 1+%d\n'%n)
                git('commit -a -m "Commit comment 1+%d"'%n)
                git('push')

        with Directory(fromble_test.where):
            with Directory('124'):
                with Directory('four'):
                    # Make a different change
                    append('Makefile', '#This is comment 2+%d\n'%n)
                    git('commit -a -m "Commit comment 2+%d"'%n)

        banner('WELD PUSH inconsistent change (%d)'%n)
        banner('weld push -v project124')
        try:
            out = weld_get_output('push -v project124', cwd=fromble_test.where)
            print out
            raise GiveUp('weld did not fail, returned:\n%s'%out)
        except ShellError as e:
            lines = e.text.splitlines()
            if "CONFLICT (content): Merge conflict in four/Makefile" not in e.text:
                raise GiveUp('weld failed in an unexpected manner:\n%s'%e)
            if not e.text.strip().endswith('and do "weld finish", or abort using "weld abort"'):
                raise GiveUp('weld failed in an unexpected manner:\n%s'%e)

    make_inconsistent_changes(1)
    # So we failed successfully (!)
    # Let's check we can abort
    with Directory(fromble_test.where):
        compare_dir('.weld',
                    ['  abort.py',
                     '  bases/...',
                     '  complete.py',
                     '  counter',
                     '  pushing/',
                     '    _merging_project124',
                     '    _push_commit_project124.txt',
                     '    project124/',             # should this be here?
                     '  welded.xml',
                     ], fold_dirs=['bases'])
        weld("abort -v")
        compare_dir('.weld',
                    ['  bases/...',
                     '  counter',
                     '  welded.xml',
                     ], fold_dirs=['bases'])

    make_inconsistent_changes(2)

    # So we failed successfully (!)
    # Let's see if we can fix it
    with Directory(fromble_test.where):
        compare_dir('.weld',
                    ['  abort.py',
                     '  bases/...',
                     '  complete.py',
                     '  counter',
                     '  pushing/',
                     '    _merging_project124',
                     '    _push_commit_project124.txt',
                     '    project124/',             # should this be here?
                     '  welded.xml',
                     ], fold_dirs=['bases'])

        new_makefile = ('# An empty makefile\n\n'
                        'all: four\n\n'
                        'four: four.c\n\n'
                        'four-and-a-bit: four-and-a-bit.c\n\n'
                        '#This is comment 1 and 2, folded together\n')

        with Directory(os.path.join('.weld', 'bases', 'project124', 'four')):
            touch('Makefile', new_makefile)
            shell('git commit -a -m "Fixed the problem"')

        weld("finish -v")

        compare_dir('.weld',
                    ['  bases/...',
                     '  counter',
                     '  welded.xml',
                     ], fold_dirs=['bases'])

        with Directory(os.path.join('.weld', 'bases', 'project124', 'four')):
            with open('Makefile') as fd:
                content = fd.read()
            if content != new_makefile:
                raise GiveUp('"weld finish" was not resolved as expected')

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
