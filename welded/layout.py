"""
layout.py - tells weld where things are stored
"""

import utils
import os
import db

def weld_dir(base_dir):
    return os.path.join(base_dir, ".weld")

def complete_pull_file(base_dir):
    return os.path.join(base_dir, ".weld", "complete.py")

def abort_file(base_dir):
    return os.path.join(base_dir, ".weld", "abort.py")

def spec_file(base_dir):
    return os.path.join(base_dir, ".weld", "welded.xml")

def base_repo(base_dir, base):
    return os.path.join(base_dir, ".weld", "bases", base)

def count_file(base_dir):
    return os.path.join(base_dir, ".weld", "counter")

def continue_push_file(base_dir):
    return os.path.join(base_dir, ".weld", "continue.py")

def pushing_dir(base_dir, base=None, seam=None):
    if seam:
        return os.path.join(base_dir, '.weld', 'pushing', base, seam)
    elif base:
        return os.path.join(base_dir, '.weld', 'pushing', base)
    else:
        return os.path.join(base_dir, '.weld', 'pushing')

def push_commit_file(base_dir, base_name):
    return os.path.join(pushing_dir(base_dir), 'push_commit_%s.txt'%base_name)

# End file.
