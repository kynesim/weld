"""
query.py - Query data from weld
"""

import git
import utils
import db
import headers
import ops

def query_base(spec, base_name):
    """
    What is the latest commit on a given base?
    """
    # Find the last merge. This returns (<commit-id>, None, []) if there
    # was no last merge
    (commit_id, base_commit_id, seams) = headers.query_last_merge(spec.base_dir, base_name)
    b = spec.query_base(base_name)
    ops.update_base(spec, b)
    current_base_cid = ops.query_head_of_base(spec, b)
    print "The last commit for base %s was our cid %s,"%(base_name, commit_id)
    print "  base cid %s"%(base_commit_id)
    print "  the base is now at %s"%(current_base_cid)

    if base_commit_id is None and seams == []:
        print "  There was no 'last merge' for %s"%base_name
    

def query_bases(spec):
    for n in spec.base_names():
        b = spec.query_base(n)
        print " %s\b"%b.name
        for s in b.seams:
            print "  %s: %s -> %s\n"%(s.name, s.get_source(),s.get_dest())

def query_seam_changes(spec, base_name):
    # Find the last merge. This returns (<commit-id>, None, []) if there
    # was no last merge
    (commit_id, base_commit_id, seams) = headers.query_last_merge(spec.base_dir, base_name)
    b = spec.query_base(base_name)
    ( deleted_in_new, changes, added_in_new ) = utils.classify_seams(seams, b.get_seams())
    print "Seams:"
    print " D: %s"%deleted_in_new
    print " C: %s"%changes
    print " A: %s"%added_in_new
    return 1
    

# End file.

    
    
