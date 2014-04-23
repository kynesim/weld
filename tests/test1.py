#! /usr/bin/env python2

"""Initial tests for weld
"""

import os
import subprocess
import sys
import traceback

# -----------------------------------------------------------------------------
# Test support

import stat
from difflib import unified_diff, ndiff
from fnmatch import fnmatchcase

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

class DirTree(object):
    """A tool for representing a directory tree in ASCII.

    Useful for testing that we have the correct files, as it can compare
    its representation against another equivalent instance, and produce
    error reports if they don't match.

    Really, a hack for a single solution...
    """

    def __init__(self, path, fold_dirs=None, indent='  '):
        """Create a DirTree for 'path'.

        'path' is the path to the directory we want to represent.

        'fold_dirs' may be a list of directory names that should
        be reported but not traversed - typically VCS directories. So,
        for instance "fold_dirs=['.git']". The names must be just a
        filename, no extra path elements. Also, it is only directories
        that get checked against this list.

        'indent' is how much to indent each "internal" line respective
        to its container. Two spaces normally makes a good default.
        """
        self.path = path
        if fold_dirs:
            self.fold_dirs = fold_dirs[:]
        else:
            self.fold_dirs = []
        self.indent = indent

    def _filestr(self, path, filename):
        """Return a useful representation of a file.

        'path' is the full path of the file, sufficient to "find" it with
        os.stat() (so it may be relative to the current directory).

        'filename' is just its filename, the last element of its path,
        which is what we're going to use in our representation.

        We could work the latter out from the former, but our caller already
        knew both, so this is hopefully slightly faster.
        """
        s = os.stat(path)
        m = s.st_mode
        flags = []
        if stat.S_ISLNK(m):
            # This is *not* going to show the identical linked path as
            # (for instance) 'ls' or 'tree', but it should be simply
            # comparable to another DirTree link
            flags.append('@')
            far = os.path.realpath(path)
            head, tail = os.path.split(path)
            rel = os.path.relpath(far, head)
            flags.append(' -> %s'%rel)
            if os.path.isdir(far):
                flags.append('/')
                # We don't try to cope with a "far" executable, or if it's
                # another link (does it work like that?)
        elif stat.S_ISDIR(m):
            flags.append('/')
            if filename in self.fold_dirs:
                flags.append('...')
        elif (m & stat.S_IXUSR) or (m & stat.S_IXGRP) or (m & stat.S_IXOTH):
            flags.append('*')
        return '%s%s'%(filename, ''.join(flags))

    def path_is_wanted(self, path, unwanted_files):
        for expr in unwanted_files:
            if fnmatchcase(path, expr):
                return False
        return True

    def _tree(self, path, head, tail, unwanted_files, lines, level, report_this=True):
        """Add the next components of the tree to 'lines'

        First adds the element specified by 'path' (or 'head'/'tail'),
        and then recurses down inside it if that is a directory that
        we are reporting on (depending on self.fold_dirs).

        'lines' is our accumulator of results. 'level' indicates how
        much indentation we're currently using, at this level.

        'path' is the same as 'head' joined to 'tail' - they're passed
        down separately just because we already had to calculate 'head'
        and 'tail' higher up, but we need all three.

        See the description of 'same_as' for how 'unwanted_files' is
        interpreted.
        """
        if report_this:
            lines.append('%s%s'%(level*self.indent, self._filestr(path, tail)))
        if os.path.isdir(path) and tail not in self.fold_dirs:
            files = os.listdir(path)
            files.sort()
            for name in files:
                this_path = os.path.join(path, name)
                if self.path_is_wanted(this_path, unwanted_files):
                    self._tree(this_path, path, name, unwanted_files, lines, level+1)

    def as_lines(self, onedown=False, unwanted_files=None):
        """Return our representation as a list of text lines.

        If 'onedown' is true, then we don't list the toplevel directory
        we're given (i.e., 'path' itself).

        See the description of 'same_as' for how 'unwanted_files' is
        interpreted.

        Our "str()" output is this list joined with newlines.
        """
        lines = []
        if not os.path.exists(self.path):
            return lines

        if unwanted_files is None:
            unwanted_files = []
        else:
            # Turn our unwanted path fragments into fnmatch expressions
            # - we do this one here because we expect to do lots of comparisons
            actual_unwanted_files = []
            for expr in unwanted_files:
                actual_unwanted_files.append('*/%s'%expr)
            unwanted_files = actual_unwanted_files

        # Start with 'self.path' itself
        head, tail = os.path.split(self.path)
        if self.path_is_wanted(self.path, unwanted_files):
            self._tree(self.path, head, tail, unwanted_files, lines, 0,
                       report_this=not onedown)
        return lines

    def __str__(self):
        lines = self.as_lines()
        return '\n'.join(lines)

    def __repr__(self):
        return 'DirTree(%r)'%self.path

    def __eq__(self, other):
        """Test for identical representations.
        """
        return str(self) == str(other)

    def assert_same(self, other_path, onedown=False, unwanted_files=None,
                    unwanted_extensions=None):
        """Compare this DirTree and the DirTree() for 'other_path'.

        Thus 'other_path' should be a path. A temporary DirTree will
        be created for 'other_path', using the same values for 'onedown',
        'fold_dirs' and 'indent' as for this DirTree.

        If 'onedown' is true, then we don't list the toplevel directory
        we're given (i.e., 'path' itself).

        If 'unwanted_files' is specified, then is should be a list of terminal
        partial paths. For each term <p> in the list, files are compared with
        the expressions '*/<p>' using fnmatch.fnmatchcase(). This means that
        "shell style" pattern macthing is used, where::

            *       matches everything
            ?       matches any single character
            [seq]   matches any character in seq
            [!seq]  matches any char not in seq

        Files whose path matches will not be reported in the output of this
        DirTree, because we expect them to be absent in the 'other_path'.

        For instance::

            muddle.utils.copy_without('source/src', 'target/src', ['.git'])
            s = DirTree('source/src', fold_dirs=['.git'])
            copy_succeeded = s.assert_same('target/src',
                                            unwanted_files=['.git',
                                                            'builds/01.pyc',
                                                            '*.c',
                                                           ])

        means that we are NOT expecting to see any of the following in
        'target/src':

            * a file or directory called '.git'
            * a file with a path that is of the form '<any-path>/builds/01.pyc'
            * a file with extension '.c'

        Raises a GiveUp exception if they do not match, with an explanation
        inside it of why.

        This is really the method for which I wrote this class. It allows
        convenient comparison of two directories, a source and a target.
        """
        other = DirTree(other_path, self.fold_dirs, self.indent)
        this_lines = self.as_lines(onedown, unwanted_files)
        that_lines = other.as_lines(onedown)

        self._same_as(this_lines, that_lines, other.path,
                      unwanted_files=None, unwanted_extensions=None)


    def _same_as(self, this_lines, that_lines, that_path,
                 unwanted_files=None, unwanted_extensions=None):
        """ The internals of our comparison. See 'same_as()' for details.
        """
        if unwanted_files:
            unwanted_text = 'Unwanted files:\n  %s\n'%('\n  '.join(unwanted_files))
        else:
            unwanted_text = ''

        for index, (this, that) in enumerate(zip(this_lines, that_lines)):
            if this != that:
                context_lines = []
                for n in range(index):
                    context_lines.append(' %s'%(this_lines[n]))
                if context_lines:
                    context = '%s\n'%('\n'.join(context_lines))
                else:
                    context = ''
                raise GiveUp('Directory tree mismatch\n'
                             '{unwanted}'
                             '--- {us}\n'
                             '+++ {them}\n'
                             '@@@ line {index}\n'
                             '{context}'
                             '-{this}\n'
                             '+{that}'.format(us=self.path, them=that_path,
                                     unwanted=unwanted_text, context=context,
                                     index=index, this=this, that=that))

        if len(this_lines) != len(that_lines):
            len_this = len(this_lines)
            len_that = len(that_lines)
            same = min(len_this, len_that)
            context_lines = []
            for n in range(same):
                context_lines.append(' %s'%(this_lines[n]))

            if len_this > len_that:
                difference = len_this - len_that
                context_lines.append('...and then %d more line%s in %s'%(difference,
                    '' if difference==1 else 's', self.path))
                for count in range(min(3, difference)):
                    context_lines.append('-%s'%(this_lines[len_that+count]))
                if difference > 4:
                    context_lines.append('...etc.')
                elif difference == 4:
                    context_lines.append('-%s'%(this_lines[len_that+3]))
            else:
                difference = len_that - len_this
                context_lines.append('...and then %d more line%s in %s'%(difference,
                    '' if difference==1 else 's', that_path))
                for count in range(min(3, difference)):
                    context_lines.append('-%s'%(that_lines[len_this+count]))
                if difference > 4:
                    context_lines.append('...etc.')
                elif difference == 4:
                    context_lines.append('-%s'%(that_lines[len_this+3]))

            context = '\n'.join(context_lines)

            raise GiveUp('Directory tree mismatch\n'
                         '{unwanted}'
                         '--- {us}\n'
                         '+++ {them}\n'
                         'Different number of lines ({uslen} versus {themlen})\n'
                         '{context}'.format(us=self.path, them=that_path,
                             unwanted=unwanted_text,
                             uslen=len(this_lines), themlen=len(that_lines),
                             context=context))

    def assert_same_as_list(self, path_list, other_path, onedown=False,
                            unwanted_files=None, unwanted_extensions=None):
        """Compare this DirTree and the list of paths in 'path_list'.

        Thus 'path_list' should be what the 'as_lines()' method for a DirTree
        for such a directory would return.

        'other_path' is the string to report as the path of the "other" lines.
        """

        this_lines = self.as_lines(onedown, unwanted_files)

        self._same_as(this_lines, path_list, other_path,
                      unwanted_files=None, unwanted_extensions=None)
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
        with NewDirectory('repos') as repo_base:
            # Our normal "source" repositories are normal bare repositories
            with NewDirectory('project124') as project124_repo:
                git('init --bare')
            with NewDirectory('igniting_duck') as igniting_duck_repo:
                git('init --bare')

        # Create some original content
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
        with NewCountedDirectory('test') as test1:
            # Because we're using git to clone it, we *could* change the
            # name of the directory we extract into, but we're not going to
            git('clone %s'%fromble_base.where)
            # Remember that our weld.xml does redirect some of the "internal"
            # directories (in particular, of igniting_duck) so they get put
            # somewhere else in our source tree.

            dt = DirTree('fromble', fold_dirs=['.git'])
            dt.assert_same_as_list(['fromble/',
                                    '  .gitignore',
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
                                    ], 'expected',
                                    unwanted_files=['.weld', '.git'])

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
                    dt = DirTree('bases', fold_dirs=['.git'])
                    dt.assert_same_as_list(['bases/',
                                            '  igniting_duck/',
                                            '    one/',
                                            '      Makefile',
                                            '      one.c',
                                            '    two/',
                                            '      Makefile',
                                            '      two.c',
                                            '  project124/',
                                            '    one/',
                                            '      Makefile',
                                            '      one.c',
                                            '    two/',
                                            '      Makefile',
                                            '      two.c',
                                            ], 'expected',
                                            unwanted_files=['.git'])
                    with Directory('bases'):
                        make_and_run_all('project124', ['one', 'two'])
                        make_and_run_all('igniting_duck', ['one', 'two'])
                        # ...and since we weren't meant to do that, tidy up
                        shell('rm project124/one/one')
                        shell('rm project124/two/two')
                        shell('rm igniting_duck/one/one')
                        shell('rm igniting_duck/two/two')

        # Alter (update) project124 in its repository
        with Directory(project124_orig):
            with NewDirectory('three'):
                build_repo_subdir('project124', 'three')
            git('push')

        # And check we can pull that using weld
        with Directory(test1.where):
            with Directory('fromble'):
                weld('pull project124')

                dt = DirTree('.', fold_dirs=['.git'])
                dt.assert_same_as_list(['./',
                                        '  .gitignore',
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
                                        ], 'expected',
                                        unwanted_files=['.weld', '.git'])

                # And our .weld directory should also have been updated
                with Directory('.weld'):
                    dt = DirTree('bases', fold_dirs=['.git'])
                    dt.assert_same_as_list(['bases/',
                                            '  igniting_duck/',
                                            '    one/',
                                            '      Makefile',
                                            '      one.c',
                                            '    two/',
                                            '      Makefile',
                                            '      two.c',
                                            '  project124/',
                                            '    one/',
                                            '      Makefile',
                                            '      one.c',
                                            '    three/',
                                            '      Makefile',
                                            '      three.c',
                                            '    two/',
                                            '      Makefile',
                                            '      two.c',
                                            ], 'expected',
                                            unwanted_files=['.git'])

        # *However* this does not update the "intermediate" weld repository
        # that we first cloned
        with Directory(fromble_base.where):
            dt = DirTree('.', fold_dirs=['.git'])
            dt.assert_same_as_list(['./',
                                    '  .gitignore',
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
                                    ], 'expected',
                                    unwanted_files=['.weld', '.git'])

            # So we need to do:
            weld('pull _all')
            # here as well, and then:
            dt = DirTree('.', fold_dirs=['.git'])
            dt.assert_same_as_list(['./',
                                    '  .gitignore',
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
                                    ], 'expected',
                                    unwanted_files=['.weld', '.git'])

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
