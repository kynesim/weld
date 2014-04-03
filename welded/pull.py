"""
pull.py - Pull a repo from upstream
"""

import git
import utils
import db

def sync_and_rebase(current, spec, repo):
    """
    Rebase a single repo.

    Find the current branch, current-branch

    Find the last merged branch - this will have an X-Weld-State: Merged <Repo>/<commit-id> header and its
     commit id will be <branch-merged-id>

    Find the commit-id in the upstream to merge with: <merge-with-commit-id>

    git checkout -b weld-merge-<repo>-<merge-with-commit-id> <commit-id>

    Now remove the repo's subdirectory and replace it with the source repo's <merge-with-commit-id>. Commit this
     with X-Weld-State: Merged <Repo>/<merge-with-commit-id>

    Leave .welded/pending as 'git merge weld-merge-<repo>-<merge-with-commit-id>'

    Now we want to apply <commit-id> .. <current-branch> .

    git checkout <current-branch>
    git rebase --onto weld-merge-<repo>-<merge-with-commit-id> <commit-id> 
    
    if the rebase completed ok, we can finalise. Otherwise, let the user do 'weld finish' at the end.
    """
    print("Pulling %s .. \n"%(repo))
    current_branch = git.current_branch(spec.base_dir)
    # Find the last commit id for a repo.
    last_commit_id = git.query_merge(spec.base_dir, repo)
    # Now find the latest upstream revision
    
        

    
