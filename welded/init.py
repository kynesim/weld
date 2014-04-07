"""
Initialise a weld
"""

import utils
import os
import utils
import db
import layout
import git
import headers

def init_weld(weld, where):
    """
    Initialise the given weld in the given directory
    """
    
    # Initialise a repository.
    if (os.path.exists(os.path.join(where, ".git"))):
        raise utils.GiveUp("Cannot initialise a weld where there is already a git repo")
    git.init(where)
    weld.set_dir(where)
    # Write the weld directory.
    os.mkdir(layout.weld_dir(weld.base_dir))
    # Create a spec file (the current file can be empty)
    weld.write(layout.spec_file(weld.base_dir))
    # Create a .gitignore
    f = open(os.path.join(where, ".gitignore"), "wb+")
    f.write(".weld/complete.*\n")
    f.write(".weld/abort.*\n")
    f.write(".weld/bases\n")
    # In case you edit stuff.
    f.write(".weld/*~\n")
    f.write(".weld/bases/**\n")
    f.close()
    # Add these to the repo
    git.add(where, [ layout.spec_file(weld.base_dir), ".gitignore" ])
    # If there is an origin in the weld file, add it to git
    if (weld.origin is not None):
        git.set_remote(where, 'origin', weld.origin)

    # Commit.
    git.commit(where, "Weld initialisation", [ headers.header_init() ])
    print("Weld initialised OK.\n")


# End file.
    
    
