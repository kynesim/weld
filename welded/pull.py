"""
pull.py - Pull a repo from upstream
"""

import os

import welded.git as git
import welded.ops as ops
import welded.layout as layout

from welded.headers import merge_marker
from welded.query import query_last_merge_or_push
from welded.status import get_status
from welded.utils import GiveUp, classify_seams

def pull_base(spec, base_name, verbose=False):
    """Pull a single base.

    'spec' is the Weld that contains this base.
    """
    if verbose:
        print 'WELD PULL %s'%base_name

    weld_root = spec.base_dir

    # Make sure we have no unstaged changes.
    if git.has_local_changes(weld_root, verbose=verbose):
        raise GiveUp("'git status' reports that you have local changes;"
                     " please commit or stash them.")

    orig_branch = git.current_branch(weld_root)

    # Make sure we aren't part way through something...
    #
    # TODO NB: we are defaulting our remote to 'origin' - but that seems to be
    # TODO an assumption being made anyway...
    in_weld_pull, in_weld_push, should_git_pull, should_git_push = \
            get_status(weld_root, branch_name=orig_branch, verbose=True)
    if in_weld_pull:
        raise GiveUp('Part way through an earlier "weld pull"\n'
                     'Fix any problems and then "weld finish", or give up using "weld abort"')
    if in_weld_push:
        raise GiveUp('Part way through an earlier "weld push"\n'
                'Fix any problems and then "weld finish", or give up using "weld abort"')
    if should_git_pull:
        # Our weld is not up-to-date. This means that if we do a "weld pull"
        # and it updates our seams, life may get confusing. So for the moment,
        # we shall require the "git pull" first.
        #
        # TODO Consider if this really is a requirement, or just the user
        # TODO being a little reckless
        raise GiveUp('The weld is not up-to-date\n'
                     'You should do "git pull" before doing a "weld pull"')
    # We don't care if "git push" would update the weld's remote, since we
    # are about to change it locally anyway...

    if orig_branch.startswith("weld-"):
        raise GiveUp("You are currently on a branch used by weld (%s) - please"
                     " get off it before trying to use weld."%(orig_branch))

    print
    print "Pulling %s .."%base_name
    print
    weld_head = git.query_current_commit_id(weld_root)

    # Find the last merge or push (i.e., the last sync point with the base's
    # remote repository)
    (verb, last_weld_sync, last_base_sync,
            seams) = query_last_merge_or_push(weld_root, base_name)
    if last_weld_sync is None:
        # There was no previous merge - fall back to the Init state
        last_weld_sync = git.query_init(weld_root)
        if verbose:
            print 'No last Push or Merge - using weld Init at %s'%last_weld_sync[:10]
    else:
        if verbose:
            print 'Last weld sync was %s at %s'%(verb, last_weld_sync[:10])

    base_obj = spec.query_base(base_name)

    # Make sure the base has been updated from its remote
    ops.update_base(spec, base_obj)
    # From which we can deduce the latest commit, which should be its HEAD
    # XXX Note that this will update the base again(!) - although of course
    # XXX that won't actually do much, except require some network traffic.
    # XXX Maybe we should just explicitly ask for the HEAD using
    # XXX "git rev-parse HEAD".
    base_head = ops.query_head_of_base(spec, base_obj)

    if (base_obj is None):
        raise GiveUp("No such base '%s'"%base_name)

    # Classify seams.
    (deleted_in_new, changes, added_in_new) = classify_seams(seams, base_obj.get_seams())

    # Are they the same? If so, no work to do.
    if (base_head == last_base_sync and
        len(deleted_in_new) == 0 and
        len(added_in_new) == 0):
        print "  %s is up to date\n"%(base_name)
        return 0

    print("Pulling %s from %s -> %s on top of local branch %s\n"%(base_name,
                                                                  last_base_sync,
                                                                  base_head,
                                                                  orig_branch))


    # No! Create a branch with a suitable unique name
    working_branch = git.new_branch_name(weld_root, 'weld-merge-%s'%base_name,
                                         last_weld_sync)
    git.checkout(weld_root, last_weld_sync, new_branch_name=working_branch)

    # First, if there are any deleted seams, use a commit to get rid of them.
    ops.delete_seams(spec, base_obj, deleted_in_new, base_head)

    # Now, modified seams ..
    ops.modify_seams(spec, base_obj, changes, last_base_sync, base_head)

    # Now added seams
    ops.add_seams(spec, base_obj, added_in_new, base_head)

    # Write some stuff to the completion file.
    ops.write_finish_pull(spec,
                         " pull.finish_pull(spec, %r, %r, %r, %r, %r, %r)"%
                         (base_obj.name, orig_branch, weld_head, working_branch,
                          last_base_sync, base_head),
                         " pull.abort_pull(spec, %r, %r)"%(working_branch, orig_branch))

    # Now merge master into current-branch
    try:
        git.merge(weld_root, working_branch, orig_branch,
                  "Merging changes from %s"%orig_branch)
    except GiveUp as e:
        print str(e)
        print "Merge failed"
        print "Either fix your merges and then do 'weld finish',"
        print "or do 'weld abort' to give up."
        return 1

    print("Rebase succeeded. Committing .. \n")
    ops.do_finish(spec)
    return 0

def finish_pull(spec, base_name, orig_branch, weld_head, working_branch,
                base_commit, base_head):
    """
    Finish a merge.
    """
    base_obj = spec.query_base(base_name)
    hdr = merge_marker(base_obj, base_obj.get_seams(), base_head)

    # Make sure we are merging to the right place.
    git.switch_branch(spec.base_dir, orig_branch)

    # You can't merge a weld pull, because it will reverse the order of commits, which is
    #  quite bad, but also remove commits that didn't have any net effect - which will
    #  lose us our headers.
    #
    # So, what you need to do is to do a git diff and then apply that patch and commit.
    tmpfile = git.show_diff(spec.base_dir, orig_branch, working_branch)
    # Apply the patch.
    n = tmpfile.name
    tmpfile.file.close()
    #tmpfile.close()
    if (os.path.exists(n) and os.path.getsize(n) > 0):
        git.apply_patch_file(spec.base_dir, n)
    # Add everything.
    os.unlink(n)
    git.add_in_subdir(spec.base_dir, ".")
    # Spurious mod just in case ..
    ops.spurious_modification(spec)
    # .. and commit.
    git.commit(spec.base_dir, hdr, [ ])


def abort_pull(spec, working_branch, orig_branch):
    """
    Abort a merge
    """
    #git.abort_rebase(spec)
    git.switch_branch(spec, orig_branch)
    git.remove_branch(spec.base_dir, working_branch)

# end file.
