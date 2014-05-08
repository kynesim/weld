"""Determine the current status of the weld.
"""

import os

import layout
import git

def get_status(where, remote_name=None, branch_name=None, verbose=False):
    """Report on the weld status.

    - 'where' is the directory to do this all in.
    - 'remote_name' defaults to "origin".
    - 'branch_name' defaults to the current branch.

    Returns a triple of the form:

        <in-weld-pull>, <in-weld-push>, <should-git-pull>, <should-git-push>

    where each term is either True or False, or None (undecidable) - if an
    early term is True, later terms may be None because we either haven't
    checked, or because (in the case of "git push") it can actually be
    undecidable until a "git pull" has been done.

    For instance, if we are in a "weld push", then this returns:

        False, True, None, None

    (we're not in a "weld pull", and we don't check the "git" statuses).

    If "verbose" is True then we also print out "extra" text, which should
    be helpful in explaining why we came to those decisions.
    """
    if remote_name is None:
        remote_name = 'origin'

    if branch_name is None:
        branch_name = git.current_branch(where, verbose=verbose)

    if os.path.exists(layout.pushing_dir(where)):
        return False, True, None, None

    if os.path.exists(layout.complete_file(where)):
        return True, None, None, None

    should_pull, should_push = git.should_we_pull_or_push(remote_name,
            branch_name, cwd=where, verbose=verbose)

    return False, False, should_pull, should_push
