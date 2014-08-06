"""
push.py - Push a weld to its remote
"""

import os
import subprocess
import tempfile
import shutil

import welded.git as git
import welded.layout as layout
import welded.ops as ops
import welded.query as query

from welded.headers import pickle_seams
from welded.status import get_status
from welded.utils import run_silently, run_to_stdout, GiveUp

class ApplyError(Exception):
    pass

def push_base(spec, base_name, edit_commit_file=False, verbose=False):
    """Push a single base.

    'spec' is the Weld that contains this base.

    'base_name' is the name of the base.

    We don't give any option to select individual seams, at least at the
    moment.
    """
    # XXX How much of the following check code is common with "pull"?
    if verbose:
        print 'WELD PUSH %s'%base_name

    weld_root = spec.base_dir

    # Make sure we have no unstaged changes.
    if git.has_local_changes(weld_root, verbose=verbose):
        raise GiveUp("'git status' reports that you have local changes;"
                     " please commit or stash them.")

    current_branch = git.current_branch(weld_root)

    # Make sure we aren't part way through something...
    #
    # TODO NB: we are defaulting our remote to 'origin' - but that seems to be
    # TODO an assumption being made anyway...
    in_weld_pull, in_weld_push, should_git_pull, should_git_push = \
            get_status(weld_root, branch_name=current_branch,
                              verbose=True)
    if in_weld_pull:
        raise GiveUp('Part way through an earlier "weld pull"\n'
                'Fix any problems and then "weld finish", or give up using "weld abort"')
    if in_weld_push:
        raise GiveUp('Part way through an earlier "weld push"\n'
                'Fix any problems and then "weld finish", or give up using "weld abort"')
    if should_git_pull:
        # This is the check we *really* care about a lot
        # Our weld is not up-to-date, so we don't want to push our bases
        # until we've sorted that out
        raise GiveUp('The weld is not up-to-date\n'
                'You should do "git pull" before doing a "weld push"')
    # We don't care if "git push" would update the weld's remote, since
    # it's the bases we're about to push to...

    if current_branch.startswith("weld-"):
        raise GiveUp("You are currently on a branch used by weld (%s) - please"
                " get off it before trying to use weld."%(current_branch))

    # At some point we need to make sure that our copy of the base is
    # up-to-date, so we can patch something that is reasonably safe to
    # push. Let's try doing it now
    print 'Updating base %s before our "weld push"'%base_name
    ops.update_base(spec, spec.query_base(base_name))

    # Here we go

    print
    print "Pushing %s .."%base_name
    print
    current_commit = git.query_current_commit_id(weld_root)

    orig_branch = git.current_branch(weld_root, verbose=verbose)

    if verbose:
        print 'Determining last push for %s:'%base_name
    (last_weld_merge, last_base_merge, last_weld_push, last_base_push,
            base_head, weld_init) = query.query_base_commits(spec, base_name)
    query.print_sha1_ids(base_name, last_weld_merge, last_base_merge,
            last_weld_push, last_base_push, base_head, weld_init)
    if verbose:
        print "So, with weld's"
        print '  last push ', last_weld_push
    latest_sync = last_weld_push
    if latest_sync is None:
        if verbose:
            print 'Which was None, so using Init'
        latest_sync = weld_init

    # Why do we use the last "weld push", and not the last "weld push *or*
    # pull"?
    #
    # Consider the following:
    #
    #   6   +   change B to a file in the seam for <project>
    #   5   o   the last Merged commit for <project>
    #   4   -   a change to some irrelevant file(s)
    #   3   +   change A to a file in the seam for <project>
    #   2   o   the last Pushed commit for <project>
    #   1   x   some common commit
    #
    # So we last "weld pulled" up to 5, and we the weld thus contains all the
    # changes from <project> up to that point.
    #
    # However, we last "weld pushed" at 2, which means that changes 3 and 6
    # have still to be applied to the base for <project>. But change 3 is
    # before our last "weld pull", so we definitely want the last "push".
    #
    #   Remember: "weld pull" updates the base from its remote, and then brings
    #   any changes therein into our weld. It does not propagate any changes
    #   in the weld back to the base.

    # What are our current seams? Knowing this tells us what directories in
    # our weld correspond to directories in our base
    #
    # Seams define:
    #
    #   * name   - the name of the seam
    #   * base   - the Base object the seam belongs to
    #   * source - the directory in the base itself (defaulting to '.')
    #   * dest   - the corresponding directory in the weld
    #
    base = spec.bases[base_name]
    base_seams = base.get_seams()

    if verbose:
        print
        print 'What changed for %s from %s to HEAD'%(base_name, latest_sync[:10])
    weld_directories = [s.get_dest() for s in base_seams]
    base_changes = git.log_between(weld_root, latest_sync, 'HEAD', weld_directories)
    if base_changes:
        if verbose:
            print '\n'.join(base_changes)
    else:
        if verbose:
            print '<Nothing>'
        print 'There were no changes to base %s, nothing to push'%base_name
        return 0

    if verbose:
        print
        print 'And trim out any X-Weld-State items'
    base_changes = trim_states(base_changes)
    if base_changes:
        if verbose:
            print '\n'.join(base_changes)
    else:
        if verbose:
            print '<Nothing>'
        print 'There were no changes to base %s, nothing to push'%base_name
        return 0

    # To make it obvious what we are doing:
    # We use --force so we can use the same tag again without complaint,
    # if we've been here before (or, presumably, if our 10-characters of
    # SHA1 id are not quite unique enough)
    git.tag(weld_root, 'weld-last-%s-sync-%s'%(base_name, latest_sync[:10]),
            latest_sync, force=True, verbose=verbose)

    base_dir = os.path.join(layout.weld_dir(weld_root), 'bases', base_name)
    base_branch = base.branch
    # If no base branch was specified, use master.
    if (base_branch is None):
        base_branch = "master"

    if verbose:
        print "So, with %s's"%base_name
        print '  last push ', last_base_push
    latest_base_sync = last_base_push
    if latest_base_sync is None:
        if verbose:
            print 'Which was None, so using HEAD'
        latest_base_sync = base_head

    # Deduce a new and unique (to this repository) branch name
    working_branch = git.new_branch_name(base_dir, 'weld-pushing', latest_base_sync)
    git.checkout(base_dir, commit_id=latest_base_sync, new_branch_name=working_branch)

    # Whilst we wanted the list of changes for our commit message, we're
    # actually going to "propagate" the changes from our weld to the base
    # by copying files...
    for s in base_seams:
        # Remember, we want our directories relative to weld_root
        from_dir = os.path.join(s.get_dest())
        if s.source is None:
            to_dir = base_dir
        else:
            to_dir = os.path.join(base_dir, s.source)
        make_files_match(from_dir, to_dir, verbose=verbose)

    # Prepare our (default) commit message

    os.makedirs(layout.pushing_dir(weld_root))
    commit_file = layout.push_commit_file(weld_root, base_name)
    with open(commit_file, 'w') as f:
        f.write('X-Weld-State: Pushed %s from weld %s\n'%(base_name, spec.name))
        f.write('\n')
        f.write('Changes were (in summary, topmost was applied last)\n')
        f.write('\n')
        # These lines are of the form "<short-sha1> <first-line>"
        # XXX Do we really want the SHA1 entry? Is it really of use?
        # XXX (I quite like having it)
        f.write('\n'.join(base_changes))

    # Write out the "continue.py" and "abort.py" files
    ops.write_finish_push(spec,
            " push.continue_push(spec, %r, %r, %r, edit_commit_file=%s)"%(base_name,
                working_branch, base_branch, edit_commit_file),
            " push.abort_push(spec, %r, %r, %r)"%(base_name, working_branch, base_branch))

    # And then use the "complete.py" script to do the rest
    return ops.do_finish(spec)

def make_files_match(from_dir, to_dir, verbose=False):
    """Make the git handled files in 'to_dir' match those in 'from_dir'
    """

    # if to_dir doesn't exist, create it - we are probably pushing
    # for the first time - Issue #2
    if (not os.path.exists(to_dir)):
        try:
            os.makedirs(to_dir, 0755)
        except:
            pass

    # What files is git managing for us in each directory?
    from_files = git.list_files(from_dir)
    to_files = git.list_files(to_dir)

    from_files_set = set(from_files)
    to_files_set = set(to_files)

    # We need to remove "by hand" those files which are no longer meant to
    # be in the "to" directory, so work out which files that is
    deleted_files = to_files_set - from_files_set

    if verbose:
        print 'Making files the same'
        print '====================='
        print 'From', from_dir
        print 'To  ', to_dir
        max_len = max(len(n) for n in from_files)
        for name in sorted(from_files_set | to_files_set):
            if name in from_files_set and name in to_files_set:
                print '%-*s  %s'%(max_len, name, name)
            elif name in from_files_set:
                print '%-*s'%(max_len, name)
            else:
                print '%-*s  %s'%(max_len, ' ', name)
        print '====================='

    # If we copy over everything from the "from" directory to the "to"
    # directory, and "git add" them all, then that will cope with changes to
    # existing files, and also add in any new files. We then need to remember
    # to "git rm" any files that are meant to have gone away, at which point we
    # can commit all the changes.
    #
    # We use rsync for our copy because it will handle things like:
    #
    #   rsync -a --relative four/jim four/bob <weld_root>/.weld/bases/project124
    #
    # and put "jim" and "bob" into <weld_root>/.weld/bases/project124/four
    cmd = ['rsync', '-a', '--relative']
    cmd += from_files
    cmd += [to_dir]
    run_silently(cmd, cwd=from_dir, verbose=verbose)

    git.add(to_dir, from_files, verbose=verbose)
    git.commit_using_message(to_dir, "Add files from %s"%from_dir, verbose=verbose)

    if deleted_files:
        git.rm(to_dir, deleted_files)
        git.commit_using_message(to_dir, "Delete files no longer in %s"%from_dir)

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

def edit_file(filename):
    """Allow the user to edit the given file.
    """
    with open(filename) as fd:
        text = fd.read()
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write(text)
    f.close()
    if 'GIT_EDITOR' in os.environ:
        editor = os.environ['GIT_EDITOR']
    elif 'VISUAL' in os.environ:
        editor = os.environ['VISUAL']
    elif 'EDITOR' in os.environ:
        editor = os.environ['EDITOR']
    else:
        editor = 'vi'

    print 'Editing file %s (copy of %s)'%(f.name, filename)
    rv = subprocess.call([editor, f.name])
    if rv != 0:
        raise GiveUp('Editor returned %d, giving up'%rv)

    with open(f.name) as fd:
        text2 = fd.read()

    if text != text2:
        print 'Text changed - updating %s'%filename
        shutil.move(f.name, filename)
    else:
        print 'Text was not changed'

def continue_push(spec, base_name, working_branch, orig_branch,
                edit_commit_file=False, verbose=True):
    """Do everything necessary to finish off our "weld push".

    Assumes we have been doing "weld push" for the given 'base_name'.
    """
    if verbose:
        print 'Continue pushing %s'%base_name

    weld_root = spec.base_dir
    base_dir = os.path.join(layout.weld_dir(weld_root), 'bases', base_name)

    merging_indicator = layout.push_merging_file(weld_root, base_name)

    # If the merging indicator exists, then we've at least started a merge
    # before, so we don't need to do so again
    if not os.path.exists(merging_indicator):
        # Merge the original branch onto this branch - we hope that in general
        # this should be trivial, but if there's a problem we want the user to
        # fix it on this branch, rather than on the original branch (!)
        try:
            run_silently(['touch', merging_indicator])
            git.merge_to_current(base_dir, orig_branch, verbose=verbose)
        except GiveUp as e:
            lines = e.message.splitlines()
            lines = ['  %s'%line for line in lines]
            raise GiveUp('Error merging patches to base %s\n'
                         '%s\n'
                         'Fix the problems:\n'
                         '  pushd %s\n'
                         '  git status\n'
                         '  edit <the appropriate files>\n'
                         '  git commit -a\n'
                         '  popd\n'
                         'and do "weld finish", or abort using "weld abort"'%(
                             base_name, '\n'.join(lines), base_dir))

    # And then merge *that* back into the original branch
    if verbose:
        print 'Merge back into original branch (%s -> %s)'%(working_branch, orig_branch)
    git.checkout(base_dir, orig_branch, verbose=verbose)
    git.merge_to_current(base_dir, working_branch, squash=True, verbose=verbose)

    commit_file = layout.push_commit_file(weld_root, base_name)
    if os.path.exists(commit_file):
        if verbose:
            print 'Commit using file %s'%commit_file
        # We've still to do the commit
        # This seems like an appropriate time to let the user edit the commit
        # file, if they've asked to do so
        if edit_commit_file:
            edit_file(commit_file)

        if verbose:
            print 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
            print 'In', base_dir
            run_to_stdout(['git', 'status'], cwd=base_dir)
            print 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

        git.commit_using_file(base_dir, commit_file, all=True, verbose=verbose)
        if verbose:
            print 'Deleting', commit_file
        os.remove(commit_file)
    else:
        if verbose:
            print 'There is no commit file %s'%commit_file

    head_base_commit = git.query_current_commit_id(base_dir)

    # And finally push the lot to our remote
    git.push(base_dir, verbose=verbose)

    # And now mark the weld with where/when the push happened
    base = spec.bases[base_name]
    base_seams = base.get_seams()
    seam_str = pickle_seams(base_seams)
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write('X-Weld-State: Pushed %s/%s %s\n\n'%(base_name,
        head_base_commit, seam_str))
    f.close()

    # Spurious mod just in case ..
    ops.spurious_modification(spec)

    # Allow an empty commit, so we still end up with a place marker
    # for our action
    git.commit_using_file(spec.base_dir, f.name, all=True, verbose=verbose)
    os.remove(f.name)

    # And we've finished merging!
    os.remove(merging_indicator)
    os.rmdir(layout.pushing_dir(weld_root))

def abort_push(spec, base_name, working_branch, orig_branch):
    """
    Abort a "weld push"
    """
    weld_root = spec.base_dir
    base_dir = os.path.join(layout.weld_dir(weld_root), 'bases', base_name)

    try:
        # We might need to abort a merge before we can change branch
        # Or we might not...
        git.merge_abort(base_dir)
    except GiveUp:
        pass            # Really, ignore it

    git.switch_branch(base_dir, orig_branch)
    git.remove_branch(base_dir, working_branch, irrespective=True)

    commit_file = layout.push_commit_file(spec.base_dir, base_name)
    if os.path.exists(commit_file):
        os.remove(commit_file)
    merging_indicator = layout.push_merging_file(weld_root, base_name)
    os.remove(merging_indicator)
    os.rmdir(layout.pushing_dir(weld_root))

def report_status(spec):
    """Report on our pushing status
    """
    weld_root = spec.base_dir
    pushing_dir = layout.pushing_dir(weld_root)

    pushing_files = os.listdir(pushing_dir)
    for filename in sorted(pushing_files):
        if filename.startswith('_merging_'):
            base_name = filename[len('_merging_'):]
            print 'Base %s has been merged, but the merge did not complete'%base_name
            base_dir = os.path.join(layout.weld_dir(weld_root), 'bases', base_name)
            print "  The source code that needs fixing is in\n    %s"%base_dir
        elif filename.startswith('_push_commit_'):
            head, ext = os.path.splitext(filename)
            base_name = head[len('_commit_'):]
            print 'Base %s is still to be committed'%base_name
            print '  Using the message in %s'%os.path.join(pushing_dir, filename)
