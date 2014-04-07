"""
Parse the various headers that weld leaves for itself
"""

import git
import re
import json

SEAM_VERB_ADDED = "Added"
SEAM_VERB_DELETED = "Deleted"
SEAM_VERB_MODIFIED = "Changed"

def decode_headers(log_entry):
    """
    Returns a list of headers [ ( verb, rest ) ]
    """
    lines = log_entry.split('\n')
    rv = [ ]
    rep = re.compile(r'^X-Weld-State:\s+([A-Za-z0-9]+)\s*(.*)$')
    for l in lines:
        m = rep.match(l)
        if (m is not None):
            rv.append( ( m.group(1), m.group(2) ) )
    return rv

def print_headers(lst):
    for l in lst:
        (verb, params) = l
        print "X-Weld-State: %s %s\n"%(verb, params)


def header_init():
    return ("X-Weld-State", "Init")

def header_grep_merge(base):
    return "^X-Weld-State: Merged %s/"%base

def header_grep_init():
    return "^X-Weld-State: Init"


def pickle_seams(seams):
    t = [ ]
    for s in seams:
        t.append( ( s.source, s.dest ) )
    return json.dumps(t)

def seam_op(verb, base_obj, seams, base_commit):
    """
    Construct seam operation header.
    """
    rv = "X-Weld-State: Seam-%s %s/%s %s"%(verb, base_obj.name, base_commit, pickle_seams(seams))
    return rv

def merge_marker(base_obj, seams, base_commit):
    """
    Construct a merge header
    """
    rv = "X-Weld-State: Merged %s/%s "%(base_obj.name, base_commit)
    for s in seams:
        rv += seam_desc(s)
    return rv

def query_last_merge(where, base):
    """
    Find the last merge of base in where and return ( commit-id, merge-commit-id, seams )
    
    If this base was never merged, return (commit-id, None, [])

    """
    commit_id = git.query_merge(where, base)
    log_entry = git.log(where, commit_id)
    hdrs = decode_headers(log_entry)
    merge_commit_id = None
    seams_merged = [ ]
    # Find all the merges
    for h in hdrs:
        (verb, data) = h
        if (verb == "Merged"):
            # Gotcha!
            raise GiveUp("Merged header not yet implemented")

    return (commit_id, merge_commit_id, seams_merged )



# End file.
