"""
push_utils.py - Pusher utilities
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
from welded.utils import run_silently, run_to_stdout, GiveUp

def list_files_involved(base_changes):
    """
    Returns a list of (letter, path) pairs.
    """
    r = re.compile(r'^:([0-9]+)\s+([0-9]+)\s+([0-9a-f]+)...\s+([0-9a-f]+)...\s+([A-Z])\s+(.*)$')
    rv = [ ]
    for b in base_changes:
        m = r.match(b)
        if (m is not None):
            rv.append((m.group(5), m.group(6).strip()))
    return rv
    

def list_files_by_attribute(base_changes, attr):
    r = re.compile(r'^:([0-9]+)\s+([0-9]+)\s+([0-9a-f]+)...\s+([0-9a-f]+)...\s+([A-Z])\s+(.*)$')
    rv = [ ]
    for b in base_changes:
        m = r.match(b)
        if (m is not None) and (attr == m.group(5)):
            rv.append(m.group(6).strip())
    return rv


def make_patches_match(base_repo, weld_root, base_changes, base_seams, last_cid, cid, ignore_bad_patches, verbose = False):
    # This is rather horrific. For each change in base_changes,
    #  we mark any seam that has changed.
    #
    #  Then we can use diff_this() to find each diff in turn.
    #   .. and apply_patch to apply it.
    change_records = [ ]
    for q in base_changes:
        change_records.extend(q.split('\n'))

        involved = list_files_involved(change_records)
        
        prefixes = { }
        for i in involved:
            path = i[1]
            if (i[0] == 'D'):
                print " Deleting %s "%i[1]
                if os.path.exists(i[1]):
                    if os.path.isdir(i[1]):
                        shutil.rmtree(i[1])
                    else:
                            os.unlink(i[1])
                    continue

            while True:
                (path,k) = os.path.split(path)
                if path is None or len(path) == 0:
                    break
                else:
                    #print "Entering path %s"%path
                    prefixes[path] = True
                    
        f = False
        for s in base_seams:
            src = s.get_source()
            #print "Testing seam %s"%s.get_source()
            if src in prefixes:
                print "Seam %s is involved in this change"%s
                # Get me the git diff for these changes.
                (os_handle, name) = tempfile.mkstemp(suffix = 'patch', prefix = 'tmpweld')
                os.close(os_handle)

                some_data = git.diff_this(base_repo, src, cid, verbose = verbose,
                                          from_commit_id = last_cid)
                # Write it out, rename all the little as and bs and apply it.
                with open(name, 'w') as fh:
                    fh.write(some_data)
                try:
                    git.apply_patch(weld_root, name, directory = s.get_dest(), verbose = verbose)
                except GiveUp as e:
                    if (ignore_bad_patches):
                        print "Ignoring bad patch - eeek!"
                    else:
                        in_error = True
                    # .. and carry on.
                os.unlink(name)

        # Add the relevant changes.
        to_add = [ ]
        for i in involved:
            if (i[0] != 'D'):
                to_add.append(i[1])
        git.add(weld_root, to_add)

        # That's all folks


def make_files_match(from_dir, to_dir, do_commits = True, verbose=False, delete_missing_from = False, 
                     do_delete_files = True):
    """Make the git handled files in 'to_dir' match those in 'from_dir'
    """

    # if from dir doesn't exist, delete to dir
    # This is used by pull_step.
    if (not os.path.exists(from_dir)):
        if delete_missing_from and os.path.exists(to_dir):
            shutil.rmtree(to_dir)
        return


    # if to_dir doesn't exist, create it - we are probably pushing
    # for the first time - Issue #2
    if (not os.path.exists(to_dir)):
        try:
            os.makedirs(to_dir, 0755)
        except:
            pass

    # What files is git managing for us in each directory?
    if not os.path.exists(from_dir):
        from_files = [ ]
    else:
        from_files = git.list_files(from_dir)
    to_files = git.list_files(to_dir)

    from_files_set = set(from_files)
    to_files_set = set(to_files)

    # We need to remove "by hand" those files which are no longer meant to
    # be in the "to" directory, so work out which files that is
    deleted_files = to_files_set - from_files_set

    if verbose:
        print 'Making files the same'
        print '====================='
        print 'From', from_dir
        print 'To  ', to_dir
        if (len(from_files) > 0):
            max_len = max(len(n) for n in from_files)
        else:
            max_len = 1
        for name in sorted(from_files_set | to_files_set):
            if name in from_files_set and name in to_files_set:
                print '%-*s  %s'%(max_len, name, name)
            elif name in from_files_set:
                print '%-*s'%(max_len, name)
            else:
                print '%-*s  %s'%(max_len, ' ', name)
        print '====================='

    # If we copy over everything from the "from" directory to the "to"
    # directory, and "git add" them all, then that will cope with changes to
    # existing files, and also add in any new files. We then need to remember
    # to "git rm" any files that are meant to have gone away, at which point we
    # can commit all the changes.
    #
    # We use rsync for our copy because it will handle things like:
    #
    #   rsync -a --relative four/jim four/bob <weld_root>/.weld/bases/project124
    #
    # and put "jim" and "bob" into <weld_root>/.weld/bases/project124/four
    if os.path.exists(from_dir):
        cmd = ['rsync', '-a', '--relative']
        cmd += from_files
        cmd += [to_dir]
        run_silently(cmd, cwd=from_dir, verbose=verbose)

    if len(from_files) >0:
        git.add(to_dir, from_files, verbose=verbose)
    if do_commits:
        git.commit_using_message(to_dir, "Add files from %s"%from_dir, verbose=verbose)

    if deleted_files and do_delete_files:
        git.rm(to_dir, list(deleted_files))
        if do_commits: 
            git.commit_using_message(to_dir, "Delete files no longer in %s"%from_dir)


def escape_states(lines):
    """
    Escape X-Weld-State: so it doesn't confuse us later.
    
    We do this by turning it into X-Escaped-Weld, incrementing
    all the "Escaped"s so we can unescape correcly later if necessary.
    """
    new = []
    for line in lines:
        new.append(re.sub(r'X-((Escaped-)*)Weld([^:]+):', 
                          r'X-Escaped-\1Weld\3:', line))
    return new

def edit_file(filename):
    """Allow the user to edit the given file.
    """
    with open(filename) as fd:
        text = fd.read()
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write(text)
    f.close()
    if 'GIT_EDITOR' in os.environ:
        editor = os.environ['GIT_EDITOR']
    elif 'VISUAL' in os.environ:
        editor = os.environ['VISUAL']
    elif 'EDITOR' in os.environ:
        editor = os.environ['EDITOR']
    else:
        editor = 'vi'

    print 'Editing file %s (copy of %s)'%(f.name, filename)
    rv = subprocess.call([editor, f.name])
    if rv != 0:
        raise GiveUp('Editor returned %d, giving up'%rv)

    with open(f.name) as fd:
        text2 = fd.read()

    if text != text2:
        print 'Text changed - updating %s'%filename
        shutil.move(f.name, filename)
    else:
        print 'Text was not changed'


# End file.
