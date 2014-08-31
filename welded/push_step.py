"""
push_step.py - Push a weld to its remote stepwise
"""

import os
import subprocess
import tempfile
import shutil
import re

import welded.git as git
import welded.layout as layout
import welded.ops as ops
import welded.query as query

from welded.headers import pickle_seams
from welded.status import get_status
from welded.utils import run_silently, run_to_stdout, GiveUp

class ApplyError(Exception):
    pass

def push_step(spec, base_name, edit_commit_file = False, verbose = False,
                  long_commit = False, ignore_history = False):
    """
    Pushes a single base step-wise. This allows git bisect to work, but
    creates a lot of extra work for git.
    
    'spec' is the weld that contains this base
    'base_name' is the name of the base
    """
    if verbose:
        print "WELD PUSH_STEP %s"%base_name

    weld_root = spec.base_dir

    pd = layout.pushing_dir(weld_root)
    if os.path.exists(pd):
        raise GiveUp("Cannot run whilst a pushing dir exists - remove it and try again")

    # No unstaged changes please
    if git.has_local_changes(weld_root, verbose = verbose):
        raise GiveUp("'git status' reports local changes. Please commit or stash them.")
        
    # Where are we?
    current_branch = git.current_branch(weld_root, verbose = verbose)
    
    in_weld_pull, in_weld_push, should_git_pull, should_git_push =  \
            get_status(weld_root, branch_name = current_branch, verbose = True)
    
    if in_weld_pull:
        raise GiveUp("Half way through a pull - weld finish/weld abort and try again")
    if in_weld_push:
        raise GiveUp("Half way through a push - weld finish/weld abort and try again")
    if should_git_pull:
        raise GiveUp("Weld is not up to date - git pull and try again")
    if current_branch.startswith("weld-"):
        raise GiveUp("You are on a branch used by weld (%s) - get off and try again."%current_branch)
    
    # Update our base
    print 'Updating base %s before trying to pushstep.. '%base_name
    ops.update_base(spec, spec.query_base(base_name))

    print 
    print "Beginning a stepwise push for %s .. "%base_name
    print
    current_commit = git.query_current_commit_id(weld_root)

    if verbose:
        print "Determining last push for %s:"%base_name
    (last_weld_merge, last_base_merge, last_weld_push, last_base_push,
     base_head, weld_init) = query.query_base_commits(spec, base_name)
    
    if (ignore_history):
        last_weld_merge = None
        last_base_merge = None
        last_weld_push = None
        last_base_push = None

    query.print_sha1_ids(base_name, last_weld_merge, last_base_merge,
                         last_weld_push, last_base_push, base_head, 
                         weld_init)
    if verbose:
        print " last push %s"%last_weld_push
    latest_sync = last_weld_push
    if latest_sync is None:
        if verbose:
            print 'Which was none, so using init'
        latest_sync = weld_init
        
    # See push.py for why we use the last 'push' and not the last
    #  'push / pull'.
    base = spec.bases[base_name]
    base_seams = base.get_seams()
    
    # Tag the weld root so we know what is going on.
    git.tag(weld_root,
            'weld-last-%s-sync-%s'%(base_name, latest_sync[:10]),
            latest_sync, force = True, verbose = verbose)
    
    base_dir = layout.base_repo(weld_root, base_name)
    base_branch = base.branch
    if (base_branch is None):
        base_branch = "master"

    if verbose:
        print " Base name: %s, last push %s"%(base_name, last_base_push)
    latest_base_sync = last_base_push
    if latest_base_sync is None:
        if verbose:
            print "  No last sync, so using HEAD"
        latest_base_sync = base_head

    # Now let's create a branch on to which to port all the changes from
    # the weld
    working_branch = git.new_branch_name(base_dir,
                                         'weld-pushing',
                                         latest_base_sync)
    # Swing the base round .. 
    git.checkout(base_dir, commit_id = latest_base_sync,
                 new_branch_name = working_branch)

    # ... aand now start our merge in earnest.

    ops.write_finish_push(spec,
                          "push_step.continue_push( spec, %r, %r, %r, edit_commit_file=%s)"%
                          (base_name, working_branch, base_branch, edit_commit_file),
                          "push_step.abort_push(spec, %r, %r, %r)"%(base_name, working_branch,
                                                                    base_branch))
    return ops.do_finish(spec)


def continue_push(spec, base_name, working_branch, base_branch, edit_commit_file):
    """
    This is where the work actually happens. 

     - Are we merging? if so, finish merging.
     - If not, the X-Weld-Original-Commit: header in the commit message tells us
       what commit we were up to. Find the next one between it and HEAD and merge
       it over.
    """

    pass

def abort_push(spec, base_name, working_branch, orig_branch):
    """
    Abort a push-step; this is basically the same as aborting a weld.
    """
    weld_root = spec.base_dir
    base_dir = os.path.join(layout.weld_dir(weld_root), 'bases', base_name)
    try:
        git.merge_abort(base_DIR)
    except GiveUp:
        pass

    # Move back on to the branch we started the base on.
    git.switch_branch(base_dir, orig_branch)
    # Erase the working branch (we want to lose all work on it)
    git.remove_branch(base_dir, working_branch, irrespective = True)
    # Erase the file we use to hold temporary commit messages.
    commit_file = layout.push_commit_file(spec.base_dir, base_name)
    if os.path.exists(commit_file):
        os.remove(commit_file)
    # Erase the file we use to tell ourselves we are merging.
    merging_indicator = layout.push_merging_file(weld_root, base_name)
    os.remove(merging_indicator)
    # Now remove the metadata directory.
    os.rmdir(layout.pushing_dir(weld_root))



# End file.

    
    
    
                                                                
    
    
