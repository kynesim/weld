"""
Initialise a weld
"""

import os

import welded.layout as layout
import welded.git as git

from welded.utils import GiveUp
from welded.headers import header_init

def init_weld(weld, where):
    """
    Initialise the given weld in the given directory
    """
    
    # Initialise a repository.
    if (os.path.exists(os.path.join(where, ".git"))):
        raise GiveUp("Cannot initialise a weld where there is already a git repo")
    git.init(where)
    weld.set_dir(where)
    # Write the weld directory.
    os.mkdir(layout.weld_dir(weld.base_dir))
    # Create a spec file (the current file can be empty)
    weld.write(layout.spec_file(weld.base_dir))
    # Create a .gitignore
    with open(os.path.join(where, ".gitignore"), "wb+") as f:
        f.write(".weld/state/**\n")
        f.write(".weld/pushing\n")
        f.write(".weld/bases\n")
        # In case you edit stuff.
        f.write(".weld/*~\n")
        f.write(".weld/bases/**\n")
    # Add these to the repo
    git.add(where, [ layout.spec_file(weld.base_dir), ".gitignore" ])
    # If there is an origin in the weld file, add it to git
    if (weld.origin is not None):
        git.set_remote(where, 'origin', weld.origin)

    # Commit.
    git.commit(where, "Weld initialisation", [ header_init() ])
    print("Weld initialised OK.\n")


# End file.
    
    
