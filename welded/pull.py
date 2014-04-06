"""
pull.py - Pull a repo from upstream
"""

import git
import utils
import db
import headers
import ops

def sync_and_rebase(spec, base):
    """
    Rebase a single base.

    Find the current branch. Stash the name.

    Now find the last commit-id for the base, by looking for 
    """
    print("Pulling %s .. \n"%(base))
    current_branch = git.current_branch(spec.base_dir)
    # Find the last merge
    (commit_id, base_commit_id, seams) = headers.query_last_merge(spec.base_dir, base)
    b = spec.query_base(base)
    # Update the base.
    ops.update_base(spec, b)
    # Now query the latest commit on that base
    current_base_commit_id = ops.query_head_of_base(spec, b)

    print("last commit_id = %s , current = %s\n", base_commit_id, current_base_commit_id)
    #b = spec.query_base(base)
    #( deleted_in_new, changes, created_in_new ) = utils.classify_seams(seams, b.seams)
    

    
