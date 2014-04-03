"""
Initialise a weld
"""

import utils
import os
import utils
import db
import layout
import git

def init_weld(weld, where):
    """
    Initialise the given weld in the given directory
    """
    
    # Initialise a repository.
    if (os.path.exists(os.path.join(where, ".git"))):
        raise utils.GiveUp("Cannot initialise a weld where there is already a git repo")
    git.init(where)
    weld.set_base(where)
    # Write the weld directory.
    os.mkdir(layout.weld_dir(weld))
    # Create a spec file (the current file can be empty)
    weld.write(layout.current_file(weld))
    # Add this to the repo
    git.add(where, [ layout.current_file(weld) ])
    # Commit.
    git.commit(where, "Weld initialisation", [ layout.header_init() ])
    print("Weld initialised OK.\n")


# End file.
    
    
