"""
pull_step.py - Pull a base into a repo
"""

import os

import welded.git as git
import welded.ops as ops
import welded.layout as layout

from welded.headers import merge_marker
from welded.query import query_last_merge_or_push
from welded.status import get_status
from welded.utils import GiveUp, classify_seams

def pull_step(spec, base_name, opts):
    """
    Pull a base into the current branch.
    """
    
    verbose = opts.verbose

    if verbose:
        print "Weld pull-step %s"%base_name

    base_obj = spec.query_base(base_name)
    if (base_obj is None):
        raise GiveUp("No such base  '%s'"%base_name)

    # No unstaged changes, please
    if git.has_local_changes(weld_root, verbose = verbose):
        raise GiveUp("'git status' reports local changes; please commit or stash them.")
        
    root_branch = git.current_branch(weld_root)
    
    if (len(ops.list_verbse) > 0):
        raise GiveUp('We are part way through a weld operation; finish it (or abort it) and try again')
    
    (s_pull, s_push) = git.should_we_pull_or_push(None, root_branch, cwd = weld_root, verbose = verbose)
    if (s_pull):
        raise GiveUp('You should pull from your origin to make yourself up to date, or changed seams may cause pain.')
    
    if (root_branch.startswith('weld-')):
        raise GiveUp("You are currently on a branch ('%s') used by weld - please " 
                     "get iff it and try again"%(root_branch))

    root_head = git.query_current_commit_id(weld_root)
    (verb, last_weld_sync, last_base_sync, seams) = query_last_merge_or_push(weld_root, base_name)
    if ignore_history or (last_weld_sync is None):
        # No previous merge
        last_base_sync = git.query_init(weld_root)
        if verbose:
            print 'No last push - using weld init at %s'%last_weld_sync[:10]
    else:
        if verbose:
            print 'Last weld sync with this base was %s at %s'%(verb, last_weld_sync[:10])
    
    # So, what we do now is to branch the weld at the point where the last
    # sync was. We then modify seams on that branch to what they should be.
    # 
    # Then we work up from there on the base, merging in the changes one by one. By
    #  this point, of course, all seams are "modify".
    #
    # Then in finalise() we merge this new weld branch with the original.
    #
    print("Branching the weld at %s to get the last sync. "%last_base_sync)
    working_branch = git.new_branch_name(weld_root, 'weld-pulling', 
                                         last_weld_sync)
    git.checkout(weld_root, last_weld_sync, new_branch_name = working_branch)

    # Now let's do some housekeeping.
    
    
    
    
            
        
    
    
