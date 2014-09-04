"""
pull_step.py - Pull a base into a repo
"""

import os
import shutil

import welded.git as git
import welded.ops as ops
import welded.layout as layout
import welded.push_utils as push_utils

from welded.headers import merge_marker
from welded.query import query_last_merge_or_push
from welded.status import get_status
from welded.utils import GiveUp, classify_seams, run_to_stdout, run_silently

def pull_step(spec, base_name, opts):
    """
    Pull a base into the current branch.
    """
    
    verbose = opts.verbose

    if verbose:
        print "Weld pull-step %s"%base_name

    weld_root = spec.base_dir
    base_obj = spec.query_base(base_name)
    if (base_obj is None):
        raise GiveUp("No such base  '%s'"%base_name)

    # No unstaged changes, please
    if git.has_local_changes(weld_root, verbose = verbose):
        raise GiveUp("'git status' reports local changes; please commit or stash them.")
        
    root_branch = git.current_branch(weld_root)
    
    if (len(ops.list_verbs(spec)) > 0):
        raise GiveUp('We are part way through a weld operation; finish it (or abort it) and try again')
    
    if (root_branch.startswith('weld-')):
        raise GiveUp("You are currently on a branch ('%s') used by weld - please " 
                     "get iff it and try again"%(root_branch))

    root_head = git.query_current_commit_id(weld_root)
    (verb, last_weld_sync, last_base_sync, seams) = query_last_merge_or_push(weld_root, base_name)
    if opts.ignore_history or (last_weld_sync is None):
        # No previous merge
        last_weld_sync = git.query_init(weld_root)
        last_base_sync = None
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
    working_branch = git.new_branch_name(weld_root, 'weld-pulling', 
                                         last_weld_sync)
    base_repo = layout.base_repo(weld_root, base_name)

    # Now let's do some housekeeping so that abort() will work properly.
    state = { }
    state['base_last'] = git.query_current_commit_id(base_repo)        
    state['spec'] = spec
    state['base_name'] = base_name
    state['base_obj'] = base_obj
    state['weld_root'] = spec.base_dir
    state['orig_branch'] = root_branch
    state['working_branch' ] = working_branch
    state['base_repo'] = base_repo
    state['base_branch'] = git.current_branch(base_repo)
    state['next_idx_to_merge'] = 0
    state['last_idx_merged'] = -1
    state['log'] = [ ]
    state['base_seams'] = spec.bases[base_name].get_seams()
    state['weld_directories'] = [s.get_source() for s in state['base_seams'] ]
    state['last_idx_committed'] = -1
    state['verbose'] = opts.verbose
    state['edit_commit_file'] = opts.edit_commit_file

    if (state['base_last'] == last_base_sync):
        print "Your last pull from this base was '%s', which is the head of your base repo."%last_base_sync
        print "Nothing to do."
        return

    ops.write_state_data(spec, state)
    ops.verb_me(spec, 'pull_step', 'abort')
    # In case initialisation fails.
    ops.next_verbs(spec)

    print("Enumerating commits on the base between last sync and current branch ('%s')"%state['base_branch'])
    changes = git.list_changes(base_repo, last_base_sync, 'HEAD')
    state['changes'] = changes

    print("Branching the weld at %s to get the last sync. "%last_base_sync)
    git.checkout(weld_root, commit_id = last_weld_sync, new_branch_name = working_branch)

    base_obj = spec.query_base(base_name)

    print("Classifying seams .. ")
    (deleted_in_new, seams_changed, added_in_new) = classify_seams(seams, base_obj.get_seams())

    # Mess with deleted and added seams since the last pull.
    # We don't need to modify, because we will do that later.
    print("Bringing weld into line with base seams at last merge")
    base_head = state['base_branch']
    ops.delete_seams(spec, base_obj, deleted_in_new, last_base_sync)
    ops.add_seams(spec, base_obj, added_in_new, last_base_sync)
    
    ops.write_state_data(spec, state)
    ops.verb_me(spec, 'pull_step', 'abort')

    next_action = ''
    if (len(state['changes']) > 0):
        if git.has_local_changes(weld_root):
            print "Seams have changed since the last push; issuing an initial commit to adjust for this"
            state['initial_commit'] = True
            ops.verb_me(spec, 'pull_step', 'initial_commit', verb = 'commit')
            next_action = 'commit'
        else:
            ops.verb_me(spec, 'pull_step', 'step')
            next_action = 'step'
    else:
        ops.verb_me(spec, 'pull_step', 'finish')
        next_action = 'finish'

    ops.next_verbs(spec)
    ops.do(spec, next_action, opts)

def initial_commit(spec, opts):
    """
    Do a commit.
    """
    state = ops.read_state_data(spec)
    weld_root = state['weld_root']
    base_name = state['base_name']
    verbose = state['verbose']
    
    if verbose:
        print "Starting initial_commit"

    # This is the initial cleanup commit.
    commit_file = layout.commit_file(weld_root, base_name)
    with open(commit_file, 'w') as f:
        f.write('\n')
        f.write('Initial weld adjustment for a pull from %s/%s'%(base_name, state['base_last']))
        f.write('\n')    
    if (state['edit_commit_file'] or opts.edit_commit_file):
        push_utils.edit_file(commit_file)
    git.commit_using_file(spec.base_dir, commit_file, all = True, verbose = state['verbose'])
    ops.write_state_data(spec, state)
    ops.verb_me(spec, 'pull_step', 'abort')
    ops.verb_me(spec, 'pull_step', 'step')
    ops.next_verbs(spec)
    ops.do(spec, 'step', opts)

def step(spec, opts):
    """
    pull-step step function; merge next-idx-to-merge. If you've run out, finish.
    """
    while True:
        state = ops.read_state_data(spec)
        weld_root = state['weld_root']
        changes = state['changes']
        idx = state['next_idx_to_merge']
        idx_from = state['last_idx_merged']
        base_repo = state['base_repo']
        base_seams = state['base_seams']
        if idx >= len(changes):
            print("All done")
            raise GiveUp("Finalisation not yet implemented")

        if idx_from >= 0:
            last_cid = changes[idx_from]
        else:
            last_cid = None

        cid = changes[idx]
        no_further_commits = (idx == len(changes)-1)

        # Right. So, does this commit change something we care about?
        print "Stepping:  searching from   %s"%last_cid
        print "                     to     %s"%cid
        base_changes = push_utils.escape_states(
            git.what_changed(base_repo, 
                             last_cid,
                             cid,
                             state['weld_directories']))
        if base_changes:
            changed = True
            if state['verbose']:
                print '\n'.join(base_changes)
        else:
            changed = False
            if state['verbose']:
                print "No explicit change for these seams in this base commit"
        
        if changed or no_further_commits:
            # Check out the right version of the base.
            git.checkout(base_repo, cid)

            # Sync up the seams. There is no need for modify_seams, we can just sync.
            for s in base_seams:
                if s.source is None:
                    from_dir = base_repo
                else:
                    from_dir = os.path.join(base_repo, s.source)
                to_dir = os.path.join(weld_root, s.get_dest())
                #print "s = %s"%s
                push_utils.make_files_match(from_dir, to_dir, do_commits = False, verbose = state['verbose'])

            if (not('log' in state)):
                state['log'] = [ ]
            if base_changes:
                base_changes.extend(state['log'])
                state['log'] = base_changes
            state['last_idx_merged'] = state['next_idx_to_merge']

        state['next_idx_to_merge'] = state['next_idx_to_merge'] + 1
        # .. aaand stash everything so that commit can find it.
        has_local_changes = git.has_local_changes(weld_root)

        ops.write_state_data(spec, state)
        if ((not has_local_changes) and no_further_commits):
            ops.verb_me(spec, 'pull_step', 'finish')
        else:
            ops.verb_me(spec, 'pull_step', 'step')
            if (state['last_idx_merged'] >= 0):
                ops.verb_me(spec, 'pull_step', 'commit')

        ops.verb_me(spec, 'pull_step', 'inspect')
        ops.verb_me(spec, 'pull_step', 'abort')
        
        if has_local_changes:
            if opts.single_commit_stepping and state['last_idx_merged'] >= 0:
                commit(spec, opts, allow_edit = False)
                state = ops.read_state_data(spec)
            elif (not opts.finish_stepping) or state['last_idx_merged'] < 0 :
                break
        elif no_further_commits:
            state['all_done'] = True
            ops.write_state_data(spec, state)
        
            
        if no_further_commits:
            break
        
        ops.next_verbs(spec)
    
    if no_further_commits:
        if ('all_done' in state):
            print "All done. Do 'weld finish' when ready"
        else:
            print "Stepping complete. Commit when you are ready and we will finish the pull"
    else:
        print "Weld stepped to %s - check changes and when you are happy, either step or commit"%cid
        if (state['last_idx_merged'] < 0):
            print(" - We stopped because there are local changes here that don't correspond to a \n" 
                  "   base commit; you likely need to commit a .gitignore or those changes manually.\n")


def inspect(spec, opts):
    """
    Inspect the current log
    """
    state = ops.read_state_data(spec)
    print "Commit log: "
    if ('log' in state):
        print "\n".join(state['log'])
    print "\n Files affected: \n"
    run_to_stdout(['git', 'status'], cwd=state['base_repo'])
    ops.repeat_verbs(spec)


def commit(spec, opts, allow_edit= True):
    """
    It's now time for a commit.
    """
    state = ops.read_state_data(spec)
    base_name = state['base_name']
    last_cid_committed = None
    changes = state['changes']
    verbose = state['verbose'] or opts.verbose
    edit_commit_file = state['edit_commit_file'] or opts.edit_commit_file
    if (state['last_idx_committed'] >= 0):
        last_cid_committed = changes[state['last_idx_committed']]
    last_cid_merged = changes[state['last_idx_merged']]

    if (len(changes) == 0 or last_cid_merged == changes[-1]):
        print "All commits added. Finishing.."
        finishing = True
    else:
        finishing = False

    weld_root = spec.base_dir
    try:
        os.makedirs(layout.pushing_dir(weld_root))
    except:
        pass

    if (state['last_idx_committed'] != state['last_idx_merged']):
        commit_file = layout.commit_file(weld_root, base_name)
        with open(commit_file, 'w') as f:
            f.write('\n')
            if (last_cid_committed is not None):
                dots_string = "%s..%s"%(last_cid_committed, last_cid_merged)
            else:
                dots_string = "%s"%last_cid_merged
            f.write('X-Weld-Stepwise-Pull: %s %s'%(base_name, dots_string))
            f.write('\n')
            if (len(state['log']) > 0):
                f.write('\n'.join(state['log']))
            else:
                f.write('(* No log: this commit was likely a branch switch  *)')
        
        # Now just commit.
        if (allow_edit and edit_commit_file):
            push_utils.edit_file(commit_file)
        if verbose:
            run_to_stdout(['git', 'status'], cwd = weld_root)
        git.commit_using_file(weld_root, commit_file, all = True, verbose = state['verbose'])
        if verbose:
            print "Removing temporary commit file."
        os.remove(commit_file)
    else:
        print "Skipping commit - no changes to commit"
    
    if finishing:
        state['all_done'] = True
    state['log'] = [ ]
    state['commit_list'] = [ ]
    state['last_idx_committed'] = state['last_idx_merged']
    ops.write_state_data(spec, state)
    
    if not finishing:
        ops.verb_me(spec, 'pull_step', 'step')
    else:
        ops.verb_me(spec, 'pull_step', 'finish')
        print "We are all done; use 'weld finish' to finish the pull"

    ops.verb_me(spec, 'pull_step', 'abort')
    
def finish(spec, opts):
    """
    Finish off this pull. 
    
    Merge the working branch back to the main weld branch.
    """
    state = ops.read_state_data(spec)
    verbose = state['verbose'] or opts.verbose
    weld_root = state['weld_root']
    working_branch = state['working_branch']
    orig_branch = state['orig_branch']
    base_obj = state['base_obj']
    base_last = state['base_last']
    base_name = state['base_name']
    base_repo = state['base_repo']
    edit_commit_file = state['edit_commit_file'] or opts.edit_commit_file
    
    if verbose:
        print "Merging main branch into working branch .. "
    mi = layout.merging_file(weld_root, base_name)
    if not os.path.exists(mi):
        # Weren't merging, so ..
        try:
            run_silently(['touch', mi ])
            git.merge_to_current(weld_root, orig_branch, verbose = verbose)
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
                         'and do "weld finish", or abort using "weld abort"'%(
                    base_name, '\n'.join(lines), base_repo))
    if verbose:
        if state['verbose']:
            print 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
            print 'In', base_dir
            run_to_stdout(['git', 'status'], cwd=weld_root)
            print 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

    if verbose:
        print "Merging back to orig branch .. "
    git.checkout(weld_root, orig_branch)
    git.merge_to_current(weld_root, working_branch, squash = False, verbose = verbose)
    
    if verbose:
        print "Leaving pull marker .. "
    commit_file = layout.commit_file(weld_root, base_name)
    hdr = merge_marker(base_obj, base_obj.get_seams(), base_last)
    with open(commit_file, 'w') as f:
        f.write('\n')
        f.write(hdr)
        f.write('\n')
    if (edit_commit_file):
        push_utils.edit_file(commit_file)
    
    git.commit_using_file(weld_root, commit_file, all = True, verbose = verbose)
    if verbose:
        print "Deleting %s"%commit_file
    os.remove(commit_file)

    # .. and that's all, folks.
    if os.path.exists(layout.state_dir(weld_root)):
        shutil.rmtree(layout.state_dir(weld_root))
    
    print "pull_step complete. Yay! "

def abort(spec, opts):
    state = ops.read_state_data(spec)
    weld_root = state['weld_root']
    # Check out the right version of the base.
    git.checkout(state['base_repo'], state['base_branch'])
    # Remove anything compromising ..
    git.hard_reset(weld_root)
    # Move the weld back to its old branch
    git.checkout(weld_root, state['orig_branch'])
    # Remove the working branch
    try:
         git.remove_branch(weld_root, state['working_branch'], irrespective = True)
    except:
        pass
    # Erase all state.
    if (os.path.exists(layout.state_dir(weld_root))):
        shutil.rmtree(layout.state_dir(weld_root))



# End file.
    
    
    
            
        
    
    
