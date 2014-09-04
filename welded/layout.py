"""
layout.py - tells weld where things are stored
"""

import os

def weld_dir(base_dir):
    return os.path.join(base_dir, ".weld")

def state_dir(base_dir):
    return os.path.join(base_dir, '.weld', 'state')

def pending_verb_dir(base_dir):
    return os.path.join(base_dir, '.weld', 'state', 'pending_verbs')

def pending_verb_file(base_dir, verb):
    return os.path.join(base_dir, '.weld', 'state', 'pending_verbs', '%s.py'%verb)

def state_data_file(base_dir):
    return os.path.join(base_dir, '.weld', 'state', 'data.bin')

def state_data_file_x(base_dir):
    return os.path.join(base_dir, '.weld', 'state', 'data.bin.x')

def verb_dir(base_dir):
    return os.path.join(base_dir, '.weld', 'state', 'verbs')

def verb_file(base_dir,verb):
    return os.path.join(base_dir, '.weld', 'state', 'verbs', '%s.py'%verb)

def spec_file(base_dir):
    return os.path.join(base_dir, ".weld", "welded.xml")

def base_repo(base_dir, base):
    return os.path.join(base_dir, ".weld", "bases", base)

def count_file(base_dir):
    return os.path.join(base_dir, ".weld", "counter")

def pushing_dir(base_dir):
    return os.path.join(base_dir, '.weld', 'state', 'pushing')

def commit_file(base_dir, base_name):
    return os.path.join(base_dir, '.weld', 'state', '_commit_%s.txt'%base_name)

def push_commit_file(base_dir, base_name):
    return os.path.join(base_dir, '.weld', 'state', 'pushing', '_commit_%s.txt'%base_name)

def push_merging_file(base_dir, base_name):
    return os.path.join(base_dir, '.weld', 'state', 'pushing', '_merging_%s'%base_name)

def merging_file(base_dir, base_name):
    return os.path.join(base_dir, '.weld', 'state', 'merging_%s'%base_name)

# End file.
