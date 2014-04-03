"""
layout.py - tells weld where things are stored
"""

import utils
import os
import db

def weld_dir(weld):
    return os.path.join(weld.base_dir, ".weld")

def current_file(weld):
    return os.path.join(weld.base_dir, ".weld", "current.xml")

def spec_file(weld):
    return os.path.join(weld.base_dir, ".weld", "welded.xml")

def header_init():
    return ("X-Weld-State", "Init")

# End file.
