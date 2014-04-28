"""
pull.py - Pull a repo from upstream
"""

import git
import utils
import db
import headers
import ops
import layout
import os
import os.path
import sys

def sync_and_rebase(spec, base):
    """
    Rebase a single base.

    Find the current branch. Stash the name.

    Now find the last commit-id for the base, by looking for 
    """
    # Make sure we have no unstaged changes.less 
    if (git.has_local_changes(spec.base_dir)):
        raise utils.GiveUp("You have local changes; please commit or stash them.")

    print("Pulling %s .. \n"%(base))
    current_branch = git.current_branch(spec.base_dir)
    current_commit = git.query_current_commit_id(spec.base_dir)

    if (current_branch[:5] == "weld-"):
        print("You are currently on a branch used by weld (%s) - please get off it before"
              " trying to use weld."%(current_branch))
        return 1

    # Find the last merge
    (commit_id, base_commit_id, seams) = headers.query_last_merge(spec.base_dir, base)
    b = spec.query_base(base)
    # Update the base.
    ops.update_base(spec, b)
    # Now query the latest commit on that base
    current_base_commit_id = ops.query_head_of_base(spec, b)

    # Get a base object.
    b = spec.query_base(base)

    if (b is None):
        raise utils.GiveUp("No such base '%s'"%base)

    # Classify seams.
    ( deleted_in_new, changes, added_in_new ) = utils.classify_seams(seams, b.get_seams())


    # Are they the same? If so, no work to do.
    if (current_base_commit_id == base_commit_id and len(deleted_in_new) == 0 and
        len(added_in_new) == 0):
        print "  %s is up to date\n"%(base)
        return 0
    
    print("Pulling %s from %s -> %s on top of local branch %s\n"%(base, 
                                                                  base_commit_id,
                                                                  current_base_commit_id,
                                                                  current_branch))


    # No! Create a branch (and increment the counter until we 
    #   get one that is not in use)
    i = 0
    while True:
        branch_name = "weld-merge-%s-%d"%(base,i)
        if (not git.has_branch(spec.base_dir, branch_name)):
            break
        i = i + 1

    git.create_and_switch(spec.base_dir, branch_name, commit_id)

    # First, if there are any deleted seams, use a commit to get rid of them.
    ops.delete_seams(spec, b, deleted_in_new, current_base_commit_id)

    # Now, modified seams ..
    ops.modify_seams(spec, b, changes, base_commit_id, current_base_commit_id)

    # Now added seams
    ops.add_seams(spec, b, added_in_new, current_base_commit_id)
    
    # Write some stuff to the completion file.
    ops.write_completion(spec, 
                         " pull.finish(spec, '%s', '%s', '%s', '%s', '%s', '%s')"%
                         (b.name, current_branch, current_commit, branch_name, 
                          base_commit_id, current_base_commit_id),
                         " pull.abort(spec, '%s', '%s')"%(branch_name, current_branch))
    
    # Now merge master into current-branch
    try:
        git.merge(spec, branch_name, current_branch, "Merging changes from %s"%current_branch)
    except utils.GiveUp as e:
        print str(e)
        print "Merge failed"
        print "Either fix your merges and then do 'weld finish',"
        print "or do 'weld abort' to give up."
        return 1

    print("Rebase succeeded. Committing .. \n")
    ops.do_completion(spec)
    return 0

def spurious_modification(w):
    """
    Spuriously modify a weld and git add it so that your
    commit is never empty
    """
    a_file = layout.count_file(w.base_dir)
    utils.count(a_file)
    git.add(w.base_dir, [ a_file ] )

def finish(spec, base_name, current_branch, current_commit, branch_name, base_commit, 
           current_base_commit_id):
    """
    Finish a merge.
    """
    b = spec.query_base(base_name)
    hdr = headers.merge_marker(b, b.get_seams(), current_base_commit_id)

    # Make sure we are merging to the right place.
    git.switch_branch(spec, current_branch)

    # You can't merge a weld pull, because it will reverse the order of commits, which is
    #  quite bad, but also remove commits that didn't have any net effect - which will
    #  lose us our headers.
    #
    # So, what you need to do is to do a git diff and then apply that patch and commit.
    tmpfile = git.show_diff(spec.base_dir, current_branch, branch_name)
    # Apply the patch.
    n = tmpfile.name
    tmpfile.file.close()
    #tmpfile.close()
    if (os.path.exists(n) and os.path.getsize(n) > 0):
        git.apply(spec.base_dir, n)
    # Add everything.
    os.unlink(n)
    git.add_in_subdir(spec.base_dir, ".")
    # Spurious mod just in case ..
    spurious_modification(spec)
    # .. and commit.
    git.commit(spec.base_dir, hdr, [ ])


def abort(spec, branch_name, current_branch):
    """
    Abort a merge
    """
    git.abort_rebase(spec)
    git.switch_branch(spec, current_branch)
    git.remove_branch(spec, branch_name)

# end file.
    

    
