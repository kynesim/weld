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
import welded.push_utils as push_utils

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

    # Create a list of commits that we want to merge. This is a bit tricky,
    # but basically it is the list of commits that rebase would have used.
    state = { }
    changes = git.list_changes(weld_root, latest_sync, 'HEAD')
    state['changes'] =  changes
    state['current'] = None
    state['last_committed'] = None
    state['commit_list'] = [ ]
    state['latest_sync'] = latest_sync
    state['base_seams'] = spec.bases[base_name].get_seams()
    state['spec_from_base'] = spec
    state['weld_directories'] = [s.get_dest() for s in state['base_seams'] ]
    state['base_dir'] = base_dir
    state['current_commit'] = current_commit
#
    # Now let's create a branch on to which to port all the changes from
    # the weld
    working_branch = git.new_branch_name(base_dir,
                                         'weld-pushing',
                                         latest_base_sync)
    # Swing the base round .. 
    git.checkout(base_dir, commit_id = latest_base_sync,
                 new_branch_name = working_branch)

    # ... aand now start our merge in earnest.
    ops.write_state_data(spec, state)
    ops.make_verb_available(spec,
                            'step',
                            [ 'import push_step',
                              'push_step.step( spec, %r, %r, %r, edit_commit_file=%s)'%\
                              (base_name, working_branch, base_branch, edit_commit_file) ])
    ops.make_verb_available(spec, 'abort',
                            [ 'import push_step',
                              'push_step.abort(spec, %r, %r, %r, edit_commit_file=%s)'%\
                              (base_name, working_branch, base_branch, edit_commit_file) ])
    ops.next_verbs(spec)

    return ops.do(spec, 'step')


def step(spec, base_name, working_branch, base_branch, edit_commit_file, verbose = True):
    """
    Step a step-push; this means that we accumulate changes into the next change up
    """
    state = ops.read_state_data(spec)
    # Right oh. Move up a commit in the list .. 
    weld_root = spec.base_dir
    while True:
        prev_c = None
        next_c = None
        base_seams = state['base_seams']
        base_dir = state['base_dir']

        if state['current'] is None:
            next_c = state['changes'][0]
            print "Starting step-push with first step %s"%next_c
        else:
            print " current = %s"%state['current']
            for c in state['changes']:
                print "c=%s"%c
                if prev_c == state['current']:
                    next_c = c
                    break
                prev_c = c

        if next_c is None:
            print "No further commits to add - try 'weld do commit'"
            next_c = state['current']
            no_further_commits = True
        else:
            no_further_commits = False
            if (state['current'] is None):
                if (state['last_committed'] is not None):
                    merging_from = state['last_committed']
                else:
                    merging_from = state['latest_sync']
            else:
                merging_from = state['current']
                
            print "Stepping: changes merged to %s"%(state['last_committed'])
            print "          next commit is    %s"%(next_c)
            
            weld_directories = state['weld_directories']
            base_changes = git.what_changed(weld_root, merging_from, next_c,
                                            weld_directories)

            if base_changes:
                if verbose:
                    print '\n'.join(base_changes)
            else:
                if verbose:
                    print "Nothing changed (apparently)"
          
            # Check out the right version of the weld
            git.checkout(weld_root, next_c)

            # Work out what changed .. 
            for s in base_seams:
                from_dir = os.path.join(s.get_dest())
                if s.source is None:
                    to_dir = base_dir
                else:
                    to_dir = os.path.join(base_dir, s.source)
                push_utils.make_files_match(from_dir, to_dir, do_commits = False, verbose = verbose)

            if (not ('log' in state)):
                state['log'] = [ ]
            if base_changes: 
                base_changes.extend(state['log'])
                state['log'] = base_changes
        
        # Stash state.
        state['current'] = next_c
        state['commit_list'].append(next_c)
        ops.write_state_data(spec, state)
        
        # You can now either step, abort, or commit
        ops.make_verb_available(spec,
                                'step',
                                [ 'import push_step',
                                  'push_step.step( spec, %r, %r, %r, edit_commit_file=%s)'%\
                                  (base_name, working_branch, base_branch, edit_commit_file) ])
        ops.make_verb_available(spec, 'abort',
                                [ 'import push_step',
                                  'push_step.abort(spec, %r, %r, %r, edit_commit_file=%s)'%\
                                  (base_name, working_branch, base_branch, edit_commit_file) ])
        
        ops.make_verb_available(spec, 'commit',
                                [ 'import push_step',
                                  'push_step.commit(spec, %r, %r, %r, edit_commit_file=%s)'%\
                                  (base_name, working_branch, base_branch, edit_commit_file) ])

        ops.make_verb_available(spec, 'inspect',
                                [ 'import push_step',
                                  'push_step.inspect(spec, %r, %r, %r, edit_commit_file=%s)'%\
                                  (base_name, working_branch, base_branch, edit_commit_file) ])
        
        # Now work out if anything has changed.
        if (git.has_local_changes(base_dir) or no_further_commits):
            break
        else:
            ops.next_verbs(spec)

    print "Base stepped to %s - check changes and when you are happy, either step or commit."%next_c
    return True

def inspect(spec, base_name, working_branch, orig_branch, edit_commit_file, verbose = True):
    """
    Inspect the current set of changes 
    """
    state = ops.read_state_data(spec)
    print "Commit log: "
    if ('log' in state):
        print "\n".join(state['log'])
    print "\n Files affected: \n"
    run_to_stdout(['git', 'status'], cwd=state['base_dir'])
    ops.repeat_verbs(spec)


def commit(spec, base_name, working_branch, orig_branch, edit_commit_file, verbose = True):
    """
    Commit a compound.
    """
    state = ops.read_state_data(spec)
    if ('all_done' in state):
        return commit_finish(spec, base_name, working_branch, orig_branch, edit_commit_file)

    if (state['current'] == state['changes'][0]):
        print 'All commits added. Finishing .. '
        finishing = True
    else:
        finishing = False

    weld_root = spec.base_dir
    try:
        os.makedirs(layout.pushing_dir(weld_root))
    except:
        pass
    commit_file = layout.push_commit_file(weld_root, base_name)
    with open(commit_file, 'w') as f:
        f.write('\n')
        changes = state['commit_list']
        f.write('Pushing base, original commits: %s .. %s'%(changes[0], changes[-1]))
        f.write('\n')
        f.write('\n'.join(state['log']))
    
    # Now just commit.
    if edit_commit_file:
        push_utils.edit_file(commit_file)
    if verbose:
        run_to_stdout(['git', 'status'], cwd = base_dir)
    git.commit_using_file(base_dir, commit_file, all= True, verbose = verbose)
    if verbose:
        print "Removing temporary commit file", commit_file
    os.remove(commit_file)
    if finished: 
        state['all_done'] = True
    state['log'] = [ ]
    state['commit_list'] = [ ]
    state['last_committed'] = state['current']
    ops.write_state_data(spec, state)

    # From here, you can step, or abort.
    if not finished:
        ops.make_verb_available(spec,
                                'step',
                                [ 'import push_step',
                                'push_step.continue_commit(spec, %r, %r, %r, edit_commit_file=%s'%(base_name,
                                                                                                   working_branch,
                                                                                                   base_branch,
                                                                                                   edit_commit_file) ])
    else:
        commit_finish(spec, base_name, working_branch, orig_branch, edit_commit_file)
        ops.make_verb_available(spec, 'commit',
                                [ 'import push_step',
                                  'push_step.commit(spec, %r, %r, %r, edit_commit_file=%s)'%\
                                (base_name, working_branch, base_branch, edit_commit_file) ])

    ops.make_verb_available(spec,
                            'abort',
                            [ 'import push_step',
                              'push_step.abort(spec, %r, %r, %r)'%(base_name, working_branch, base_branch) ])
    ops.next_verbs(spec)

def commit_finish(spec, base_name, working_branch, orig_branch,
                    edit_commit_file = False, verbose = True):
    """
    Finish off this pushed commit.
    """
    state = ops.read_state_data(spec)
    if verbose:
        print "Merge back and commit this part of the push_step"
    
    weld_root = spec.base_dir
    base_dir = state["base_dir"]
    mi = layout.push_merging_file(weld_root, base_name)
    if not os.path.exists(mi):
        # We weren't merging, so do ..
        try:
            run_silently(['touch', mi ])
            git.merge_to_current(base_dir, orig_branch, verbose = verbose)
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
                         'and do "weld commit", or abort using "weld abort"'%(
                             base_name, '\n'.join(lines), base_dir))

    # And then merge *that* back into the original branch
    if verbose:
        print 'Merge back into original branch (%s -> %s)'%(working_branch, orig_branch)
    git.checkout(base_dir, orig_branch, verbose=verbose)
    git.merge_to_current(base_dir, working_branch, squash=True, verbose=verbose)

    commit_file = layout.push_commit_file(weld_root, base_name)
    if os.path.exists(commit_file):
        if verbose:
            print 'Commit using file %s'%commit_file
        # We've still to do the commit
        # This seems like an appropriate time to let the user edit the commit
        # file, if they've asked to do so
        if edit_commit_file:
            push_utils.edit_file(commit_file)

        if verbose:
            print 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
            print 'In', base_dir
            run_to_stdout(['git', 'status'], cwd=base_dir)
            print 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

        git.commit_using_file(base_dir, commit_file, all=True, verbose=verbose)
        if verbose:
            print 'Deleting', commit_file
        os.remove(commit_file)
    else:
        if verbose:
            print 'There is no commit file %s'%commit_file

    head_base_commit = git.query_current_commit_id(base_dir)

    # And finally push the lot to our remote
    git.push(base_dir, verbose=verbose)
    # And now mark the weld with where/when the push happened
    base = spec.bases[base_name]
    base_seams = base.get_seams()
    seam_str = pickle_seams(base_seams)
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write('X-Weld-State: Pushed %s/%s %s\n\n'%(base_name,
        head_base_commit, seam_str))
    f.close()

    # Spurious mod just in case ..
    ops.spurious_modification(spec)

    # Allow an empty commit, so we still end up with a place marker
    # for our action
    git.commit_using_file(spec.base_dir, f.name, all=True, verbose=verbose)
    os.remove(f.name)

    # And we've finished merging!
    os.rmdir(layout.state_dir(weld_root))


def abort(spec, base_name, working_branch, orig_branch, edit_commit_file = False):
    """
    Abort a push-step; this is a little bit horrid.
    """
    state = ops.read_state_data(spec)
    
    weld_root = spec.base_dir
    base_dir = os.path.join(layout.weld_dir(weld_root), 'bases', base_name)
    
    try:
        git.merge_abort(base_dir)
    except GiveUp:
        pass
        
    # Move back on the weld.
    git.switch_branch(weld_root, state['current_commit'])
    # Move back on to the branch we started the base on.
    git.switch_branch(base_dir, orig_branch)
    # git reset
    git.hard_reset(base_dir)
    # Erase the working branch (we want to lose all work on it)
    git.remove_branch(base_dir, working_branch, irrespective = True)
    # Erase all state.
    if (os.path.exists(layout.state_dir(weld_root))):
        shutil.rmtree(layout.state_dir(weld_root))



# End file.

    
    
    
                                                                
    
    
