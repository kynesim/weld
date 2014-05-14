"""
Parse the various headers that weld leaves for itself
"""

import re
import json

from welded.db import Seam
from welded.utils import GiveUp

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
    seams = str_to_seams(m.group(3))
    return (base_name, commit_id, seams)

def str_to_seams(text):
    """Convert a seam array representation to an array of Seam instances
    """
    arr = json.loads(text)
    seams = []
    for a in arr:
        s = Seam()
        (s.source, s.dest) = a
        seams.append(s)
    return seams

def decode_log_entry(log_entry, base_name, verb_sequence):
    """Look in the log entry for the first "X-Weld-State: <verb> <base_name>"

    (where <verb> is one of the strings in 'verb_sequence')

    That is, when it finds:

        X-Weld-State: <verb> <base_name>/<commit_id> <seams>

    it returns (<verb>, <commit_id>, <seams>)

    Returns (None, None, None) if it doesn't find anything suitable.
    """
    hdrs = decode_headers(log_entry)
    # Find all the pulls/pushes
    for verb, data in hdrs:
        if verb in verb_sequence:
            # Gotcha!
            this_base_name, commit_id, seams = decode_commit_data(data)
            if this_base_name == base_name:
                return verb, commit_id, seams
    return None, None, None

def print_headers(lst):
    for l in lst:
        (verb, params) = l
        print "X-Weld-State: %s %s\n"%(verb, params)


def header_init():
    return ("X-Weld-State", "Init")

def header_grep_merge(base):
    return "^X-Weld-State: Merged %s/"%base

def header_grep_push(base):
    return "^X-Weld-State: Pushed %s/"%base

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



# End file.
