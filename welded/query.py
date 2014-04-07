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
    (commit_id,base_commit_id,seams) = headers.query_last_merge(spec.base_dir, base_name)
    b = spec.query_base(base_name)
    ops.update_base(spec, b)
    current_base_cid = ops.query_head_of_base(spec, b)
    print("The last commit for base %s was our cid %s,\n  base cid %s"%(base_name, 
                                                                        commit_id,
                                                                        base_commit_id))
    print("  the base is now at %s \n"%(current_base_cid))
    

# End file.

    
    
