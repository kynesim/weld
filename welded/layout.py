"""
layout.py - tells weld where things are stored
"""

import utils
import os
import db

def weld_dir(base_dir):
    return os.path.join(base_dir, ".weld")

def current_file(base_dir):
    return os.path.join(base_dir, ".weld", "current.xml")

def spec_file(base_dir):
    return os.path.join(base_dir, ".weld", "welded.xml")

def base_repo(base_dir, base):
    return os.path.join(base_dir, ".weld", "bases", base)

def header_init():
    return ("X-Weld-State", "Init")

def header_grep_merge(base):
    return "^X-Weld-State: Merged %s/"%base

def header_grep_init():
    return "^X-Weld-State: Init"

# End file.
