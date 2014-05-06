"""
query.py - Query data from weld
"""

import git
import utils
import db
import headers
import ops

def query_base_commits(spec, base_name):
    # Find the last merge. This returns (None, None, []) if there wasn't one
    last_weld_merge, last_base_merge, seams = headers.query_last_merge(spec.base_dir, base_name)
    weld_init = git.query_init(spec.base_dir)
    # Find the last push. Similar things happen if there wasn't one
    last_weld_push, last_base_push, seams = headers.query_last_push(spec.base_dir, base_name)
    # In order to determine the HEAD of our base, we need to make sure it is
    # there (in .weld/bases/<base-name>)
    b = spec.query_base(base_name)
    ops.update_base(spec, b)
    base_head = ops.query_head_of_base(spec, b)
    return (last_weld_merge, last_base_merge, last_weld_push, last_base_push,
            base_head, weld_init)

def query_base(spec, base_name):
    """
    What is the latest commit on a given base?
    """
    (last_weld_merge, last_base_merge, last_weld_push, last_base_push,
            base_head, weld_init) = query_base_commits(spec, base_name)
    print "Base %s"%base_name
    print "  last merge, weld %s"%last_weld_merge
    print "              base %s"%last_base_merge
    print "  last push,  weld %s"%last_weld_push
    print "              base %s"%last_base_push
    print "  base HEAD  %s"%base_head
    print "  weld Init  %s"%weld_init

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
    (commit_id, base_commit_id, seams) = headers.query_last_merge(spec.base_dir, base_name)
    if commit_id is None:
        # There was no previous merge - fall back to changes since Init
        commit_id = git.query_init(spec.base_dir)
    b = spec.query_base(base_name)
    ( deleted_in_new, changes, added_in_new ) = utils.classify_seams(seams, b.get_seams())
    print "Seams:"
    print "  D: %s"%deleted_in_new
    print "  C: %s"%changes
    print "  A: %s"%added_in_new
    return 1
    

# End file.

    
    
