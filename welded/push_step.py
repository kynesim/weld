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
from welded.status import get_status_2
from welded.utils import run_silently, run_to_stdout, GiveUp, get_default_commit_style, \
    get_login, get_hostname, canonicalise
import welded.push_utils as push_utils

class ApplyError(Exception):
    pass

#edit_commit_file = False, verbose = False,
#                  long_commit = False, ignore_history = False):

def push_step(spec, base_name, opts):
    """
    Pushes a single base step-wise. This allows git bisect to work, but
    creates a lot of extra work for git.
    
    'spec' is the weld that contains this base
    'base_name' is the name of the base
    """
    if opts.verbose:
        print "WELD PUSH_STEP %s"%base_name

    weld_root = spec.base_dir

    pd = layout.pushing_dir(weld_root)
    if os.path.exists(pd):
        raise GiveUp("Cannot run whilst a pushing dir exists - remove it and try again")

    # No unstaged changes please
    if git.has_local_changes(weld_root, verbose = opts.verbose):
        raise GiveUp("'git status' reports local changes. Please commit or stash them.")
        
    # Where are we?
    current_branch = git.current_branch(weld_root, verbose = opts.verbose)
    
    in_cmd, should_git_pull, should_git_push =  \
            get_status_2(weld_root, branch_name = current_branch, verbose = True)
    
    if in_cmd:
        raise GiveUp("Half way through a pull - weld finish/weld abort and try again")
    if current_branch.startswith("weld-"):
        raise GiveUp("You are on a branch used by weld (%s) - get off and try again."%current_branch)
    
    # Update our base
    print 'Updating base %s before trying to pushstep.. '%base_name
    ops.update_base(spec, spec.query_base(base_name))

    print 
    print "Beginning a stepwise push for %s .. "%base_name
    print
    current_commit = git.query_current_commit_id(weld_root)

    if opts.verbose:
        print "Determining last push for %s:"%base_name
    (last_weld_merge, last_base_merge, last_weld_push, last_base_push,
     base_head, weld_init) = query.query_base_commits(spec, base_name)
    
    if (opts.ignore_history):
        last_weld_merge = None
        last_base_merge = None
        last_weld_push = None
        last_base_push = None

    query.print_sha1_ids(base_name, last_weld_merge, last_base_merge,
                         last_weld_push, last_base_push, base_head, 
                         weld_init)
    if opts.verbose:
        print " last push %s"%last_weld_push
    latest_sync = last_weld_push
    if latest_sync is None:
        if opts.verbose:
            print 'Which was none, so using init'
        latest_sync = weld_init

    if (opts.force_latest_sync is not None):
        print ("DANGER! WHIRLING BLADES OF DEATH AHEAD!\n"
               "You have supplied --force-latest-sync: latest_sync manually set to %s"%opts.force_latest_sync)
        latest_sync = opts.force_latest_sync
        
    # See push.py for why we use the last 'push' and not the last
    #  'push / pull'.
    base = spec.bases[base_name]
    base_seams = base.get_seams()
    
    # Tag the weld root so we know what is going on.
    git.tag(weld_root,
            'weld-last-%s-sync-%s'%(base_name, latest_sync[:10]),
            latest_sync, force = True, verbose = opts.verbose)
    
    base_dir = layout.base_repo(weld_root, base_name)
    base_branch = base.branch
    if (base_branch is None):
        base_branch = "master"

    if opts.verbose:
        print " Base name: %s, last push %s"%(base_name, last_base_push)
    latest_base_sync = last_base_push
    if latest_base_sync is None:
        if opts.verbose:
            print "  No last sync, so using HEAD"
        latest_base_sync = base_head

    # Create a list of commits that we want to merge. This is a bit tricky,
    # but basically it is the list of commits that rebase would have used.
    state = { }
    
    # @todo There is some controversy over how we should do this, but
    #  I think ancestry-path is the least confusing - rrw 2014-09-02.
    changes = ops.list_changes(weld_root, latest_sync, 'HEAD')
    state['sanitise_script'] = canonicalise(opts, opts.sanitise_script)
    state['cmd'] = 'push_step'
    state['edit_commit_file'] = opts.edit_commit_file
    state['verbose'] = opts.verbose
    state['changes'] =  changes
    state['current_idx'] = 0
    state['last_committed_idx'] = -1
    state['last_merged_idx'] = -1
    state['commit_list'] = [ ]
    state['latest_sync'] = latest_sync
    state['base_seams'] = spec.bases[base_name].get_seams()
    state['spec_from_base'] = spec
    state['weld_directories'] = [s.get_dest() for s in state['base_seams'] ]
    state['base_dir'] = base_dir
    state['current_commit'] = current_commit
    state['base_name'] = base_name
    state['base_branch'] = base_branch
    state['current_branch'] = current_branch
    state['legend'] = '%s (%s@%s)'%(spec.name, get_login(), get_hostname())
    if (opts.commit_style is None):
        state['commit_style'] = get_default_commit_style()
    else:
        state['commit_style'] = opts.commit_style
        

        #
    # Now let's create a branch on to which to port all the changes from
    # the weld
    working_branch = git.new_branch_name(base_dir,
                                         'weld-pushing',
                                         latest_base_sync)
    state['working_branch'] = working_branch
    # Swing the base round .. 
    git.checkout(base_dir, commit_id = latest_base_sync,
                 new_branch_name = working_branch)

    # ... aand now start our merge in earnest.
    ops.write_state_data(spec, state)
    ops.verb_me(spec, 'push_step', 'step')
    ops.verb_me(spec, 'push_step', 'abort')
    ops.next_verbs(spec)

    return ops.do(spec, 'step', opts, True)


def step(spec, opts):
    """
    Step a step-push; this means that we accumulate changes into the next change up
    """
    state = ops.read_state_data(spec)
    verbose = opts.verbose or state['verbose']
    if opts.commit_style is not None:
        commit_style = opts.commit_style
    else:
        commit_style = state['commit_style']

    edit_commit_file = opts.edit_commit_file or state['edit_commit_file']

    # Right oh. Move up a commit in the list .. 
    weld_root = spec.base_dir
    while True:
        base_seams = state['base_seams']
        base_dir = state['base_dir']
        changes = state['changes']

        current_idx = state['current_idx']
        last_merged_idx = state['last_merged_idx']
        last_committed_idx = state['last_committed_idx']

        if (last_merged_idx >= 0):
            last_merged_cid = changes[last_merged_idx]
        else:
            last_merged_cid = state['latest_sync']

        if (last_committed_idx >= 0):
            last_committed_cid = changes[last_committed_idx]
        else:
            last_committed_cid = state['latest_sync']

        if (current_idx >= len(changes)):
            print "No further commits to add - try committing."
            cid = None
            no_further_commits = True
            changed = False
            base_changes = [ ]
        else:
            no_further_commits = False
            cid = changes[current_idx]
        
            print "Stepping: changes committed to %s"%(last_committed_cid)
            print "          merging from      %s"%(last_merged_cid)
            print "          next commit is    %s"%(cid)
            
            weld_directories = state['weld_directories']

            base_changes = ops.log_changes(weld_root, last_merged_cid, cid,
                                           weld_directories, 
                                           commit_style)
            base_changes = push_utils.escape_states(base_changes)

            if base_changes:
                changed = True
                if verbose:
                    print '\n'.join(base_changes)
            else:
                changed = False
                if verbose:
                    print "Nothing changed (apparently)"
          
            # Check out the right version of the weld
            git.checkout(weld_root, cid)

        # If nothing ostensibly changed, don't bother with a commit - 
        #  this will have been a merge from another branch and 
        #  there is no profit in spuriously building a base commit
        #  which causes files to appear and disappear at random.
        #
        # (but if it is the last commit, we don't have a choice)
        if changed or no_further_commits:
            # Work out what changed .. 
            for s in base_seams:
                from_dir = os.path.join(weld_root, s.get_dest())
                if s.source is None:
                    to_dir = base_dir
                else:
                    to_dir = os.path.join(base_dir, s.source)
                push_utils.make_files_match(from_dir, to_dir, do_commits = False, verbose = state['verbose'])
                    
            if (not ('log' in state)):
                state['log'] = [ ]
            if base_changes: 
                base_changes.extend(state['log'])
                state['log'] = base_changes

        
        # Stash state.
        state['last_merged_idx'] = current_idx
        state['current_idx'] = current_idx + 1
        state['commit_list'].append(cid)
        ops.write_state_data(spec, state)
        
        has_local_changes = git.has_local_changes(base_dir)

        # You can now either step, abort, or commit
        ops.verb_me(spec, 'push_step', 'step')
        ops.verb_me(spec, 'push_step', 'abort')
        ops.verb_me(spec, 'push_step', 'sanitise')

        if has_local_changes or not no_further_commits:
            ops.verb_me(spec, 'push_step', 'commit')
        else:
            ops.verb_me(spec, 'push_step', 'finish')
            
        ops.verb_me(spec, 'push_step', 'inspect')


        # Now work out if anything has changed.
        if has_local_changes:
            if opts.single_commit_stepping:
                # Sanitising ..
                ops.sanitise(base_dir, state, opts, verbose  = verbose)
                ops.write_state_data(spec, state)
                # Commit and continue.
                commit(spec, opts, allow_edit = False)
                # .. and remember to resync our state.
                state = ops.read_state_data(spec)
            elif (not opts.finish_stepping) and ((not opts.step_until_git_change) or (changed or no_further_commits)):
                # Sanitising ..
                ops.sanitise(base_dir, state, opts, verbose  = verbose)
                ops.write_state_data(spec, state)
                break
        elif no_further_commits:
            # there are no local changes, and there never will be.
            # All the commits in the list are non-change commits, so
            # don't bother recording them.
            state['all_done'] = True
            ops.write_state_data(spec, state)
            

        if no_further_commits:
            # Sanitising ..
            ops.sanitise(base_dir, state, opts, verbose  = verbose)
            ops.write_state_data(spec, state)
            break

        ops.next_verbs(spec)

    if no_further_commits:
        print "Stepping is all done. Commit when you are ready and we will finish up."
    else:
        print "Base stepped to %s - check changes and when you are happy, either step or commit."%cid
    return True

def sanitise(spec, opts):
    """
    Sanitise the current set of changes
    """
    state = ops.read_state_data(spec)
    verbose = opts.verbose or state['verbose']
    ops.sanitise(state['base_dir'], state, opts, verbose = verbose)
    ops.write_state_data(spec, state)
    ops.repeat_verbs(spec)

def inspect(spec, opts):
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


def commit(spec, opts, allow_edit = True):
    """
    Commit a compound.
    """
    state = ops.read_state_data(spec)
    edit_commit_file = opts.edit_commit_file or state['edit_commit_file']
    verbose = opts.verbose or state['verbose']
    if ('all_done' in state):
        return finish(spec, opts)

    if (state['last_merged_idx'] >= len(state['changes'])-1):
        print 'All commits added. Finishing .. '
        finishing = True
    else:
        finishing = False

    weld_root = spec.base_dir
    base_dir = state['base_dir']
    base_name = state['base_name']
    try:
        os.makedirs(layout.pushing_dir(weld_root))
    except:
        pass
    if (len(state['commit_list']) > 0):
        commit_file = layout.push_commit_file(weld_root, base_name)
        with open(commit_file, 'w') as f:
            changes = state['commit_list']
            f.write('X-Weld-Stepwise-Push: %s %s..%s'%(state['legend'], changes[0], changes[-1]))
            f.write('\n')
            if (len(state['log']) > 0):
                f.write('\n'.join(state['log']))
            else:
                f.write('(* This commit was likely from another branch; a merge will reintroduce code higher up *)')
                    
        # Now just commit.
        if (allow_edit and edit_commit_file):
            push_utils.edit_file(commit_file)
        if verbose:
            run_to_stdout(['git', 'status'], cwd = base_dir)
        git.commit_using_file(base_dir, commit_file, all= True, verbose = state['verbose'])
        if verbose:
            print "Removing temporary commit file", commit_file
        os.remove(commit_file)
    else:
        print "No changes to commit, skipping commit stage."

    if finishing: 
        state['all_done'] = True
    state['log'] = [ ]
    state['commit_list'] = [ ]
    state['last_committed_idx'] = state['last_merged_idx']
    ops.write_state_data(spec, state)

    # From here, you can step, or abort.
    if not finishing:
        print "Committed. You can now continue to step."
        ops.verb_me(spec, 'push_step', 'step')
    else:
        print "All done. Do weld finish to finish."
        ops.verb_me(spec, 'push_step', 'finish')

    ops.verb_me(spec, 'push_step', 'abort')



def finish(spec, opts):
    """
    Finish off this pushed commit.
    """
    state = ops.read_state_data(spec)
    verbose = state['verbose'] or opts.verbose
    edit_commit_file = state['edit_commit_file'] or opts.edit_commit_file
    if verbose:
        print "Merge back and commit this part of the push_step"
    
    weld_root = spec.base_dir
    base_dir = state["base_dir"]
    base_name = state['base_name']
    orig_branch = state['base_branch']
    working_branch = state['working_branch']

    try:
        os.makedirs(layout.pushing_dir(weld_root))
    except:
        pass

    # Now check out the place we want to be on the main branch.
    if verbose:
        print "Check out %s on the root .. "%state['current_branch']
    git.checkout(weld_root, state['current_branch'])

    mi = layout.push_merging_file(weld_root, base_name)
    if not os.path.exists(mi):
        # We weren't merging, so do ..
        try:
            run_silently(['touch', mi ])
            git.merge_to_current(base_dir, orig_branch, verbose = state['verbose'], commit = True)
        except GiveUp as e:
            lines = e.message.splitlines()
            lines = ['  %s'%line for line in lines]
            raise GiveUp(ops.merge_advice(
                             base_name, '\n'.join(lines), base_dir))

    # And then merge *that* back into the original branch
        
    if verbose:
        print 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        print 'In', base_dir
        run_to_stdout(['git', 'status'], cwd=base_dir)
        print 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

    if verbose:
        print 'Merge base back into original branch (%s -> %s)'%(working_branch, orig_branch)
    git.checkout(base_dir, orig_branch, verbose=verbose)
    git.merge_to_current(base_dir, working_branch, squash=False, verbose=verbose)


    commit_file = layout.push_commit_file(weld_root, base_name)
    with open(commit_file, 'w') as f:
        f.write('X-Weld-State: Pushed %s from weld %s\n'%(base_name, spec.name))
        f.write('\n')

    if verbose:
        print 'Commit using file %s'%commit_file
    # We've still to do the commit
    # This seems like an appropriate time to let the user edit the commit
    # file, if they've asked to do so
    if edit_commit_file:
        push_utils.edit_file(commit_file)
        
    git.commit_using_file(base_dir, commit_file, all=True, verbose=verbose)
    if verbose:
        print 'Deleting', commit_file
    os.remove(commit_file)

    head_base_commit = git.query_current_commit_id(base_dir)

    # Now mark the weld with where/when the push happened
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
    if os.path.exists(layout.state_dir(weld_root)):
        shutil.rmtree(layout.state_dir(weld_root))
    
    print "push_step complete. Remember to push the base in %s ."%(layout.base_repo(base_dir, base_name))


def abort(spec, opts):
    """
    Abort a push-step; this is a little bit horrid.
    """
    state = ops.read_state_data(spec)
    base_name = state['base_name']
    orig_branch = state['current_branch']
    working_branch = state['working_branch']
    weld_root = spec.base_dir
    base_dir = os.path.join(layout.weld_dir(weld_root), 'bases', base_name)
    
    try:
        git.merge_abort(base_dir)
    except GiveUp:
        pass
        
    # Move back on the weld.
    git.switch_branch(weld_root, state['current_branch'])
    # git reset
    git.hard_reset(base_dir)
    # Move back on to the branch we started the base on.
    git.switch_branch(base_dir, state['base_branch'])
    # Erase the working branch (we want to lose all work on it)
    try:
        git.remove_branch(base_dir, working_branch, irrespective = True)
    except:
        pass
    # Erase all state.
    if (os.path.exists(layout.state_dir(weld_root))):
        shutil.rmtree(layout.state_dir(weld_root))



# End file.

    
    
    
                                                                
    
    
