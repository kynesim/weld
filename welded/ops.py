"""
Generic operations
"""

import git
import utils
import layout
import os

def update_base(spec, base):
    """
    Update the local base checkout
    """
    b = layout.base_repo(spec.base_dir, base.name)
    if (not os.path.exists(b)):
        os.makedirs(b)
    g = os.path.join(b, ".git")
    if (not os.path.exists(g)):
        git.clone(b, base.uri, base.branch, base.tag, base.rev)
    # Now update ..
    git.pull(b, base.uri, base.branch, base.tag, base.rev)
    
def query_head_of_base(spec, base_obj):
    """
    Query the head of this base
    """
    return git.query_current_commit_id(layout.base_repo(spec.base_dir, base_obj.name))


# End file.
