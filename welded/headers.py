"""
Parse the various headers that weld leaves for itself
"""

import re
import json

import git
import db
from utils import GiveUp

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

def header_grep_pull(base):
    return "^X-Weld-State: Pulled %s/"%base

def header_grep_init():
    return "^X-Weld-State: Init"


def pickle_seams(seams):
    t = [ ]
    for s in seams:
        t.append( ( s.source, s.dest ) )
    return json.dumps(t)

def ported_commit(base_obj, seams, cid):
    """
    Construct a ported commit header
    """
    rv = "X-Weld-State: PortedCommit %s/%s %s"%(base_obj.name, cid, pickle_seams(seams))
    return rv

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
        #commit_id = git.query_init(where)
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

    raise GiveUp('Unable to find "X-Weld-State: Merged" data in merge commit\n'
                 'In base %s, id %s\n%s'%(base_name, commit_id,
                     '\n'.join(['  {}'.format(x) for x in log_entry.splitlines()])))

def query_last_push(where, base_name):
    """
    Find the last push of base in where and return ( commit-id, pull-commit-id, seams )

    If this base was never pushed, return (commit-id, None, []), where
    commit-id is the SHA1 id for the Init commit.
    """
    commit_id = git.query_pull(where, base_name)
    if commit_id is None:
        return (None, None, [])
        #commit_id = git.query_init(where)
    log_entry = git.log(where, commit_id)
    hdrs = decode_headers(log_entry)
    # Find all the pulls
    for h in hdrs:
        (verb, data) = h
        if (verb == "Pushed"):
            # Gotcha!
            (in_base_name, cid, seams) = decode_commit_data(data)
            if (base_name == in_base_name):
                return (commit_id, cid, seams)

    raise GiveUp('Unable to find"X-Weld-State: Merged" data in merge commit\n'
                 'In base %s, id %s\n%s'%(base_name, commit_id,
                     '\n'.join(['  {}'.format(x) for x in log_entry.splitlines()])))



# End file.
