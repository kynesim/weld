"""
layout.py - tells weld where things are stored
"""

import os

def weld_dir(base_dir):
    return os.path.join(base_dir, ".weld")

def verb_dir(base_dir):
    return os.path.join(base_dir, '.weld', 'verbs')

def verb_file(base_dir,verb):
    return os.path.join(base_dir, '.weld', 'verbs', '%s.py'%verb)

def complete_file(base_dir):
    return os.path.join(base_dir, ".weld", "complete.py")

def abort_file(base_dir):
    return os.path.join(base_dir, ".weld", "abort.py")

def spec_file(base_dir):
    return os.path.join(base_dir, ".weld", "welded.xml")

def base_repo(base_dir, base):
    return os.path.join(base_dir, ".weld", "bases", base)

def count_file(base_dir):
    return os.path.join(base_dir, ".weld", "counter")

def pushing_dir(base_dir):
    return os.path.join(base_dir, '.weld', 'pushing')

def push_commit_file(base_dir, base_name):
    return os.path.join(base_dir, '.weld', 'pushing', '_commit_%s.txt'%base_name)

def push_merging_file(base_dir, base_name):
    return os.path.join(base_dir, '.weld', 'pushing', '_merging_%s'%base_name)

# End file.
