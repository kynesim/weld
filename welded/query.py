"""
query.py - Query data from weld
"""

import welded.git as git
import welded.ops as ops

from welded.utils import classify_seams, GiveUp
from welded.headers import decode_log_entry

def query_base_commits(spec, base_name):
    # Find the last merge. This returns (None, None, []) if there wasn't one
    last_weld_merge, last_base_merge, seams = query_last_merge(spec.base_dir, base_name)
    weld_init = git.query_init(spec.base_dir)
    # Find the last push. Similar things happen if there wasn't one
    last_weld_push, last_base_push, seams = query_last_push(spec.base_dir, base_name)
    # In order to determine the HEAD of our base, we need to make sure it is
    # there (in .weld/bases/<base-name>)
    b = spec.query_base(base_name)
    ops.update_base(spec, b)
    base_head = ops.query_head_of_base(spec, b)
    return (last_weld_merge, last_base_merge, last_weld_push, last_base_push,
            base_head, weld_init)

def print_sha1_ids(base_name,
                   last_weld_merge, last_base_merge,
                   last_weld_push,  last_base_push,
                   base_head, weld_init):
    print "Base %s"%base_name
    print "  last merge, weld %s"%last_weld_merge
    print "              base %s"%last_base_merge
    print "  last push,  weld %s"%last_weld_push
    print "              base %s"%last_base_push
    print "  base HEAD  %s"%base_head
    print "  weld Init  %s"%weld_init

def query_base(spec, base_name):
    """
    What is the latest commit on a given base?
    """
    (last_weld_merge, last_base_merge, last_weld_push, last_base_push,
            base_head, weld_init) = query_base_commits(spec, base_name)
    print_sha1_ids(base_name,
            last_weld_merge, last_base_merge, last_weld_push, last_base_push,
            base_head, weld_init)

def query_bases(spec):
    """Report on the bases we have, and their seams.

    Values are sorted so that the order is predictable.
    """
    for n in sorted(spec.base_names()):
        b = spec.query_base(n)
        print "Base %s\b"%b.name
        for s in sorted(b.seams):
            print "  Seam %s: %s -> %s"%(s.name, s.get_source(),s.get_dest())

def query_seam_changes(spec, base_name):
    # Find the last merge. This returns (None, None, []) if there wasn't one
    (commit_id, base_commit_id, seams) = query_last_merge(spec.base_dir, base_name)
    if commit_id is None:
        # There was no previous merge - fall back to changes since Init
        commit_id = git.query_init(spec.base_dir)
    b = spec.query_base(base_name)
    ( deleted_in_new, changes, added_in_new ) = classify_seams(seams, b.get_seams())
    print "Seams:"
    print "  D: %s"%deleted_in_new
    print "  C: %s"%changes
    print "  A: %s"%added_in_new
    return 1

def query_match(spec, base_name):
    """Report the commit id that is the last "common point"
    """
    print '<Aaagh>'

def query_last_merge(where, base_name):
    """
    Find the last merge of base in where

    Returns ( base-commit-id, merge-commit-id, seams ) where base-commit-id
    is the SHA1 id of the commit in 'base_name' that was merged,
    merge-commit-id is the SHA1 id of the Merged commit in 'where', and
    'seams' is a list of the seams implicated in that merge.

    If base 'base_name' has never been merged, then we return (None, None, []),
    and the caller will probably have to make do with the Init commit.
    """
    commit_id = git.query_merge(where, base_name)
    if commit_id is None:
        return (None, None, [])
    log_entry = git.log(where, commit_id)
    verb, cid, seams = decode_log_entry(log_entry, base_name, ["Merged"])
    if verb:
        return (commit_id, cid, seams)
    else:
        raise GiveUp('Unable to find "X-Weld-State: Merged" data in merge commit\n'
                     'In base %s, id %s\n%s'%(base_name, commit_id,
                         '\n'.join(['  {}'.format(x) for x in log_entry.splitlines()])))

def query_last_push(where, base_name):
    """
    Find the last push of base in where and return ( commit-id, pull-commit-id, seams )

    If base 'base_name' has never been merged, then we return (None, None, []),
    and the caller will probably have to make do with the Init commit.
    """
    commit_id = git.query_push(where, base_name)
    if commit_id is None:
        return (None, None, [])
    log_entry = git.log(where, commit_id)
    verb, cid, seams = decode_log_entry(log_entry, base_name, ["Pushed"])
    if verb:
        return (commit_id, cid, seams)
    else:
        raise GiveUp('Unable to find"X-Weld-State: Pushed" data in push commit\n'
                     'In base %s, id %s\n%s'%(base_name, commit_id,
                         '\n'.join(['  {}'.format(x) for x in log_entry.splitlines()])))

def query_last_merge_or_push(where, base_name):
    """
    Find the last push or merge of base in where

    Return ( verb, weld-commit-id, base-commit-id, seams )

    If base 'base_name' has never been pushed or merged, then we return

      (None, None, None, []),

    and the caller will probably have to make do with the Init commit.
    """
    commit_id = git.query_merge_or_push(where, base_name)
    if commit_id is None:
        return (None, None, None, [])
    log_entry = git.log(where, commit_id)
    verb, cid, seams = decode_log_entry(log_entry, base_name, ["Pushed", "Merged"])
    if verb:
        return (verb, commit_id, cid, seams)
    else:
        raise GiveUp('Unable to find"X-Weld-State: Pushed" data in push commit\n'
                     'In base %s, id %s\n%s'%(base_name, commit_id,
                         '\n'.join(['  {}'.format(x) for x in log_entry.splitlines()])))

# End file.
