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
import status
import subprocess

from utils import run_silently, GiveUp

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
                'Fix any problems and then "weld continue", or give up using "weld abort"')
    if should_git_pull:
        # This is the check we *really* care about a lot
        # Our weld is not up-to-date, so we don't want to push our bases
        # until we've sorted that out
        raise GiveUp('The weld is not up-to-date\n'
                'You should do "git pull" before doing a "weld push"')
    # We don't care if "git push" would update the weld's remote, since
    # it's the bases we're about to push to...

    # XXX Here we go

    print("Pushing %s .. \n"%(base_name))
    current_commit = git.query_current_commit_id(weld_root)

    if current_branch.startswith("weld-"):
        raise GiveUp("You are currently on a branch used by weld (%s) - please"
                " get off it before trying to use weld."%(current_branch))

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
                    diff_dict[s.source].append(diff)
                else:
                    diff_dict[s.source] = [diff]

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
        f.write('Changes were (in summary, earliest first)\n')
        f.write('\n')
        # Theses lines are of the form "<short-sha1> <first-line>" - do we
        # want the SHA1 entry? Is it really of use?
        f.write('\n'.join(base_changes))

    # Write out the "continue.py" and "abort.py" files
    ops.write_finish_push(spec,
            " push.continue_push(spec, %r, %r, %r, edit_commit_file=%s)"%(base_name,
                working_branch, orig_branch, edit_commit_file),
            " push.abort_push(spec, %r, %r, %r)"%(base_name, working_branch, orig_branch))

    # And then use the "continue.py" script to do the rest
    return ops.do_continue_push(spec)

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
    for diff in diffs:
        filename = 'patch_%*d.diff'%(width, count)
        filepath = os.path.join(seam_pushing_dir, filename)
        if verbose:
            print 'WRITING patch file',filename
        with open(filepath, 'w') as fd:
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
                print 'weld_push: base %s seam %s patch %s'%(base_name, seam_name, patch_file)
                patch_path = os.path.join(pushing_seam_dir, patch_file)
                try:
                    if seam_name == '__None':
                        git.apply_patch(pushing_base_dir, patch_path,
                                        verbose=verbose)
                    else:
                        git.apply_patch(pushing_base_dir, patch_path,
                                        verbose=verbose, directory=seam_name)
                except GiveUp as e:
                    raise ApplyError(str(e))

                # Once a patch has been applied successfully, we can
                # delete the patch file
                if verbose:
                    print 'weld_push: base %s seam %s DELETE patch %s'%(base_name,
                            seam_name, patch_file)
                os.remove(patch_path)

            # Once a seam directory is empty, we can delete it
            if verbose:
                print 'weld_push: base %s DELETE seam %s'%(base_name, seam_name)
            os.rmdir(pushing_seam_dir)

        # Once a base directory is empty, we can delete it
        if verbose:
            print 'weld_push: DELETE base %s'%base_name
        os.rmdir(pushing_base_dir)

    # That appears to be all...
    finish_push(spec, base_name, working_branch, orig_branch,
                edit_commit_file=edit_commit_file, verbose=verbose)

    # And guess what we can do when we've finished pushing everything...
    if verbose:
        print 'weld_push: DELETE'
    os.rmdir(pushing_dir)

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
    # Allow an empty commit, so we still end up with a place marker
    # for our action
    # Maybe give the user the option to edit the commit message before
    # we actually use it - we'd use the "--template <file>" switch
    # instead of "--file <file>"
    commit_file = layout.push_commit_file(weld_root, base_name)

    if edit_commit_file:
        edit_file(commit_file)

    git.commit_using_file(base_dir, commit_file, all=True,
                          verbose=verbose)
    if verbose:
        print 'Deleting', commit_file
    os.remove(commit_file)

    head_base_commit = git.query_current_commit_id(base_dir)

    # Merge our original branch onto this branch - this should be trivial
    git.ff_merge(base_dir, orig_branch, verbose=verbose)

    # And then merge *that* back into the original branch
    git.checkout(base_dir, orig_branch, verbose=verbose)
    git.ff_merge(base_dir, working_branch, verbose=verbose)

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
        print "Either fix the errors and then do 'weld continue',"
        print "or do 'weld abort' to give up."
        return 1

def abort_push(spec, base_name, working_branch, orig_branch):
    """
    Abort a "weld push"
    """
    git.switch_branch(spec, orig_branch)
    git.remove_branch(spec, working_branch)
    commit_file = layout.push_commit_file(spec.base_dir, base_name)
    os.remove(commit_file)
    shutil.rmtree(layout.pushing_dir(spec.base_dir))

