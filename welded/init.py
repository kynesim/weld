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
    os.mkdir(layout.weld_dir(weld.base_dir))
    # Create a spec file (the current file can be empty)
    weld.write(layout.spec_file(weld.base_dir))
    # Create a .gitignore
    f = open(os.path.join(where, ".gitignore"), "wb+")
    f.write(".welded/pending\n")
    f.write(".welded/bases/**\n")
    f.close()
    # Add these to the repo
    git.add(where, [ layout.spec_file(weld.base_dir), ".gitignore" ])
    # Commit.
    git.commit(where, "Weld initialisation", [ layout.header_init() ])
    print("Weld initialised OK.\n")


# End file.
    
    
