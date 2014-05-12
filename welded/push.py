"""
push.py - Push a weld to its remote
"""

import math
import os
import sys
import tempfile

import db
import git
import headers
import layout
import ops
import query
import shutil
import status
import subprocess

from utils import run_silently, run_to_stdout, GiveUp

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
        print 'WELD PULL %s'%base_name

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
            status.get_status(weld_root, branch_name=current_branch,
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

    # XXX Here we go

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

    base = spec.bases[base_name]
    seams = base.get_seams()

    if verbose:
        print
        print 'What changed for %s from %s to HEAD'%(base_name, latest_sync[:10])
    # Whilst seam.source may be None, seam.dest should always be a string
    directories = [s.dest for s in seams]
    base_changes = git.log_between(weld_root, latest_sync, 'HEAD', directories)
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

    # We want the changes in the opposite order, so that we apply the oldest
    # change first. For simplicity, then, sort that out now
    base_changes.reverse()

    # So, what are the differences for our seams?
    # (Remember that this may include changes to other seams or the
    # main weld itself, as well - we'll deal with that later on)
    # Use --relative to make the changes relative to the named directory,
    # so that we don't end up with the seam directory name embedded in
    # the difference header.
    diff_dict = {}      # seam.source -> list of patches
    for s in seams:
        for change in base_changes:
            words = change.split()
            sha1 = words[0]
            # "<commit-id>^!" is a really useful notation, as I found out at
            # http://stackoverflow.com/questions/436362. It is (very briefly)
            # documented in "git help gitrevisions" (near the end)
            diff = git.diff_this(weld_root, relative_to=s.dest, commit_id=sha1,
                                 verbose=verbose)
            if diff:
                if s.source in diff_dict:
                    diff_dict[s.source].append((change, diff))
                else:
                    diff_dict[s.source] = [(change, diff)]

    for seam_dir, diff_list in diff_dict.items():
        write_patchfiles(weld_root, base_name, seam_dir, diff_list, verbose=verbose)

    # Some of those differences are things we've to push, but some are
    # probably things we already pulled

    base_dir = os.path.join(layout.weld_dir(weld_root), 'bases', base_name)

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

    # Prepare our (default) commit message
    commit_file = layout.push_commit_file(weld_root, base_name)
    with open(commit_file, 'w') as f:
        f.write('X-Weld-State: Pushed %s from weld %s\n'%(base_name, spec.name))
        f.write('\n')
        f.write('Changes were (in summary, topmost was applied last)\n')
        f.write('\n')
        # These lines are of the form "<short-sha1> <first-line>"
        # XXX Do we really want the SHA1 entry? Is it really of use?
        # XXX (I quite like having it)
        f.write('\n'.join(reversed(base_changes)))

    # Write out the "continue.py" and "abort.py" files
    ops.write_finish_push(spec,
            " push.continue_push(spec, %r, %r, %r, edit_commit_file=%s)"%(base_name,
                working_branch, orig_branch, edit_commit_file),
            " push.abort_push(spec, %r, %r, %r)"%(base_name, working_branch, orig_branch))

    # And then use the "complete.py" script to do the rest
    return ops.do_finish(spec)

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

def write_patchfiles(weld_root, base_name, seam_dir, diffs, verbose=False):
    """Write out patchfiles for later use

    'base_name' is the name of our base

    'seam_dir' is the name of the relevant subdirectory in the base, in
    which the patches should be applied. This may be None, in which case
    we shall convert it to the reserved name '__None'.

    'diffs' is the sequence of patches to apply therein, in the order they
    must be applied.
    """
    if seam_dir == None:
        # We reserve the name '__None' to mean '.'
        seam_dir = '__None'
    width = int(math.log10(len(diffs)))+1
    seam_pushing_dir = os.path.join(weld_root, '.weld', 'pushing', base_name, seam_dir)
    os.makedirs(seam_pushing_dir)
    count = 0
    for change, diff in diffs:
        filename = 'patch_%*d.diff'%(width, count)
        filepath = os.path.join(seam_pushing_dir, filename)
        if verbose:
            print 'WRITING patch file',filename
        with open(filepath, 'w') as fd:
            fd.write('# Seam %s/%d: %s\n'%(seam_dir, count, change))
            fd.write(diff)
        count += 1


def continue_patching(spec, base_name, working_branch, orig_branch,
                      edit_commit_file=False, verbose=True):
    """Continue doing the work of a "weld push".

    Finds any outstanding patches to be done in the "pushing" directory,
    and does them. If it returns, it has finished all the patches.

    If something goes wrong (i.e., a patch fails and the user needs to
    attend to it), then it raises an exception containing some sort of
    explanation of the problem.

    The idea is that you can keep calling this until all the patches have
    been successfully dealt with.
    """

    if verbose:
        print 'Continue patching %s'%base_name

    weld_root = spec.base_dir
    dot_weld_dir = layout.weld_dir(weld_root)

    pushing_dir = os.path.join(dot_weld_dir, 'pushing')
    if not os.path.exists(pushing_dir):
        print 'There is nothing to "weld push"'
        return

    # We should have one directory per base, named as the base
    bases_to_push = os.listdir(pushing_dir)
    # We'll deal with them in a predictable order
    for filename in sorted(bases_to_push):
        filepath = os.path.join(pushing_dir, filename)
        if not os.path.isdir(filepath):
            continue        # presumably a commit file
        base_name = filename
        pushing_base_dir = filepath
        base_dir = os.path.join(dot_weld_dir, 'bases', base_name)
        print 'weld_push: base %s'%base_name
        # We should have one directory per seam, named as the seam's directory
        # in the base (i.e., where we want to apply the patch). We reserve the
        # name __None to mean "at the top level of the base"
        seams_to_push = os.listdir(pushing_base_dir)
        # We'll deal with them in a predictable order
        for seam_name in sorted(seams_to_push):
            print 'weld_push: base %s seam %s'%(base_name, seam_name)
            pushing_seam_dir = os.path.join(pushing_base_dir, seam_name)
            # All the files here should be patch files
            patch_files = os.listdir(pushing_seam_dir)
            # We deal with the files in the obvious order, because
            # they were carefully named that way...
            for patch_file in sorted(patch_files):
                name, ext = os.path.splitext(patch_file)
                if ext != '.diff':
                    # It's a patch file we've already "used"
                    continue
                print 'weld_push: base %s seam %s patch %s'%(base_name, seam_name, patch_file)
                patch_path = os.path.join(pushing_seam_dir, patch_file)
                with open(patch_path) as fd:
                    commit_line = fd.readline().strip()
                    commit_text = commit_line[2:]       # lost the starting "# "
                try:
                    if seam_name == '__None':
                        git.apply_patch(base_dir, patch_path, verbose=verbose)
                    else:
                        git.apply_patch(base_dir, patch_path, verbose=verbose,
                                        directory=seam_name)
                    os.rename(patch_path, '%s.applied'%patch_path)
                except GiveUp as e:
                    os.rename(patch_path, '%s.failed'%patch_path)
                    raise ApplyError(str(e))

                # Our commit message doesn't need to be very sophisticated,
                # as it is only used on this branch, and will get squash
                # merged away
                git.commit_using_message(base_dir, commit_text, verbose=verbose)

                ## Once a patch has been applied successfully, we can
                ## delete the patch file
                #if verbose:
                #    print 'weld_push: base %s seam %s DELETE patch %s'%(base_name,
                #            seam_name, patch_file)
                #os.remove(patch_path)

            # Once we've finished a seam, we can delete the directory
            if verbose:
                print 'weld_push: base %s DELETE seam %s'%(base_name, seam_name)
            shutil.rmtree(pushing_seam_dir)
            ##os.rmdir(pushing_seam_dir)

        # That appears to be all...
        finish_push(spec, base_name, working_branch, orig_branch,
                    edit_commit_file=edit_commit_file, verbose=verbose)

        # Once we're done with a base, we can delete the directory
        if verbose:
            print 'weld_push: DELETE base %s'%base_name
        os.rmdir(pushing_base_dir)

    # And guess what we can do when we've finished pushing everything...
    if verbose:
        print 'weld_push: DELETE'
    shutil.rmtree(pushing_dir)
    ##os.rmdir(pushing_dir)

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
        os.rename(f.name, filename)
    else:
        print 'Text was not changed'

def finish_push(spec, base_name, working_branch, orig_branch,
                edit_commit_file=False, verbose=True):
    """Do everything necessary to finish off our "weld push".

    Assumes we have been doing "weld push" for the given 'base_name'.
    """
    weld_root = spec.base_dir
    base_dir = os.path.join(layout.weld_dir(weld_root), 'bases', base_name)

    pushing_dir = layout.pushing_dir(weld_root)
    merging_indicator = os.path.join(pushing_dir, '_merging_%s'%base_name)

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
    git.checkout(base_dir, orig_branch, verbose=verbose)
    git.merge_to_current(base_dir, working_branch, squash=True, verbose=verbose)

    commit_file = layout.push_commit_file(weld_root, base_name)
    if os.path.exists(commit_file):
        # We've still to do the commit
        # This seems like an appropriate time to let the user edit the commit
        # file, if they've asked to do so
        if edit_commit_file:
            edit_file(commit_file)

        print 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        print 'In', base_dir
        run_to_stdout(['git', 'status'], cwd=base_dir)
        print 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

        git.commit_using_file(base_dir, commit_file, all=True, verbose=verbose)
        if verbose:
            print 'Deleting', commit_file
        os.remove(commit_file)

    head_base_commit = git.query_current_commit_id(base_dir)

    # And finally push the lot to our remote
    git.push(base_dir, verbose=verbose)

    # And now mark the weld with where/when the push happened
    base = spec.bases[base_name]
    seams = base.get_seams()
    seam_str = headers.pickle_seams(seams)
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write('X-Weld-State: Pushed %s/%s %s\n\n'%(base_name,
        head_base_commit, seam_str))
    f.close()

    # XXX Maybe, for consistency with "weld pull"
    # Spurious mod just in case ..
    ops.spurious_modification(spec)
    # XXX

    # Allow an empty commit, so we still end up with a place marker
    # for our action
    git.commit_using_file(spec.base_dir, f.name, all=True, verbose=verbose)
    os.remove(f.name)

    return 0

def continue_push(spec, base_name, working_branch, orig_branch,
                  edit_commit_file=False, verbose=True):
    try:
        continue_patching(spec, base_name, working_branch, orig_branch,
                          edit_commit_file=edit_commit_file)
        return 0
    except ApplyError as e:
        print str(e)
        print "Push of base %s failed"%base_name
        print "Either fix the errors and then do 'weld finish',"
        print "or do 'weld abort' to give up."
        return 1

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
    shutil.rmtree(layout.pushing_dir(spec.base_dir))

def report_status(spec):
    """Report on our pushing status
    """
    weld_root = spec.base_dir
    pushing_dir = layout.pushing_dir(weld_root)

    bases_to_push = os.listdir(pushing_dir)
    for filename in sorted(bases_to_push):
        filepath = os.path.join(pushing_dir, filename)

        if os.path.isdir(filepath):
            base_name = filename
            base_dir = os.path.join(layout.weld_dir(weld_root), 'bases', base_name)
            seams_to_push = os.listdir(filepath)
            # We'll deal with them in a predictable order
            for seam_name in sorted(seams_to_push):
                print 'Base %s seam %s'%(filename,
                        'None' if seam_name == '__None' else seam_name)
                seam_dir = os.path.join(filepath, seam_name)
                diff_files = os.listdir(seam_dir)
                applied = 0
                failed = 0
                outstanding = 0
                for name in diff_files:
                    head, ext = os.path.splitext(name)
                    if ext == '.diff':
                        outstanding += 1
                    elif ext == '.failed':
                        failed += 1
                    elif ext == '.applied':
                        applied += 1
                print'  applied %d, failed %d, still to do %d'%(applied, failed,
                        outstanding)
        elif filename.startswith('_merging_'):
            base_name = filename[len('_merging_'):]
            print 'Base %s has been merged, but the merge did not complete'%base_name
            base_dir = os.path.join(layout.weld_dir(weld_root), 'bases', base_name)
            print "The source code that needs fixing is in\n    %s"%base_dir
        elif filename.startswith('_push_commit_'):
            head, ext = os.path.splitext(filename)
            base_name = head[len('_push_commit_'):]
            print 'Base %s is still to be committed, using message' \
                    ' in %s'%(base_name, filepath)
