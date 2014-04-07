"""
layout.py - tells weld where things are stored
"""

import utils
import os
import db

def weld_dir(base_dir):
    return os.path.join(base_dir, ".weld")

def completion_file(base_dir):
    return os.path.join(base_dir, ".weld", "complete.py")

def abort_file(base_dir):
    return os.path.join(base_dir, ".weld", "abort.py")

def spec_file(base_dir):
    return os.path.join(base_dir, ".weld", "welded.xml")

def base_repo(base_dir, base):
    return os.path.join(base_dir, ".weld", "bases", base)



# End file.
