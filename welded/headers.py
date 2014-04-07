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

def decode_commit_data(data):
    """
    data is a string like:
    <base>/<cid> [seams]
    - decode it.
    """
    rep = re.compile(r'([^/]+)/([^\s]+)\s+(.*)$')
    m = rep.match(data)
    if (m is None):
        raise GiveUp("Attempt to parse '%s' as a commit-data header failed."%(data))
    # m.group(3) is some seams..
    (base_name, commit_id) = (m.group(1), m.group(2))
    arr = json.loads(m.group(3))
    seams = [ ]
    for a in arr:
        s = db.Seam()
        (s.source, s.dest) = a
        seams.append(s)
    return (base_name, commit_id, seams)

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
    rv = "X-Weld-State: Merged %s/%s %s"%(base_obj.name, base_commit, pickle_seams(seams))
    return rv

def query_last_merge(where, base_name):
    """
    Find the last merge of base in where and return ( commit-id, merge-commit-id, seams )
    
    If this base was never merged, return (commit-id, None, [])

    """
    commit_id = git.query_merge(where, base_name)
    log_entry = git.log(where, commit_id)
    hdrs = decode_headers(log_entry)
    # Find all the merges
    for h in hdrs:
        (verb, data) = h
        if (verb == "Merged"):
            # Gotcha!
            (in_base_name, cid, seams) = decode_commit_data(data)
            if (base_name == in_base_name):
                return (commit_id, cid, seams)

    return (commit_id, None, [ ])



# End file.
