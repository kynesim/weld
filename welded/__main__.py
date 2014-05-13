#! /usr/bin/env python
#
# -*- mode: python -*-
#

"""
Main program for weld
"""

import os
import sys
import traceback

# Nasty trick to import the package we are in.
a_file = os.path.abspath(os.path.realpath(__file__))
a_dir = os.path.split(a_file)[0]
p_dir = os.path.split(a_dir)[0]
sys.path.insert(0, p_dir)

try:
    # Import goes here
    import cmdline
    from utils import Bug, GiveUp
except ImportError:
    # Perhaps we are being run through a soft link.
    sys.path = [a_dir] + sys.path[1:]
    import cmdline
    from utils import Bug, GiveUp


if __name__ == "__main__":

    try:
        cmdline.go(sys.argv[1:])
        sys.exit(0)
    except Bug as e:
        print("")
        print("%s"%e)
        traceback.print_exc()
        sys.exit(e.retval)
    except GiveUp as e:
        print("")
        text = str(e)
        if text:
            print(text)
        sys.exit(e.retval)

# End file.
