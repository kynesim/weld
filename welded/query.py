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
    current_base_id = ops.query_head_of_base(spec, b)
    print "Base %s"%base_name
    print "  last merge %s"%commit_id
    print "  base merge %s"%base_commit_id
    print "  base HEAD  %s"%current_base_id
    #print "The last commit for base %s was our cid %s,"%(base_name, commit_id)
    #print "  base cid %s"%(base_commit_id)
    #print "  the base is now at %s"%(current_base_id)

    # I introduced the following, but I'm not convinced it helps, given
    # "base merge None" is fairly explicit *if you understand what the above
    # is saying*, which is actually the difficult bit...
    #if base_commit_id is None and seams == []:
    #    print "  There was no 'last merge' for %s"%base_name

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
    # Find the last merge. This returns (<commit-id>, None, []) if there
    # was no last merge
    (commit_id, base_commit_id, seams) = headers.query_last_merge(spec.base_dir, base_name)
    b = spec.query_base(base_name)
    ( deleted_in_new, changes, added_in_new ) = utils.classify_seams(seams, b.get_seams())
    print "Seams:"
    print "  D: %s"%deleted_in_new
    print "  C: %s"%changes
    print "  A: %s"%added_in_new
    return 1
    

# End file.

    
    
