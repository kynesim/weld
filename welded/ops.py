"""
Generic operations
"""

import git
import utils
import layout
import headers
import os

def update_base(spec, base):
    """
    Update the local base checkout
    """
    b = layout.base_repo(spec.base_dir, base.name)
    if (not os.path.exists(b)):
        os.makedirs(b)
    g = os.path.join(b, ".git")
    if (not os.path.exists(g)):
        git.clone(b, base.uri, base.branch, base.tag, base.rev)
    # Now update ..
    git.pull(b, base.uri, base.branch, base.tag, base.rev)
    
def query_head_of_base(spec, base_obj):
    """
    Query the head of this base
    """
    return git.query_current_commit_id(layout.base_repo(spec.base_dir, base_obj.name))

def delete_seams(spec, base_obj, seams, base_commit):
    """
    Take the array of seam objects in seams and delete them from base_obj in spec, then
    commit the result.
    """
    if (len(seams) > 0):
        raise utils.Bug("delete_seams not yet implemented")

def modify_seams(spec, base_obj, changes, old_commit, new_commit):
    """
    Take the array of seam objects in changes and apply the changes from old_commit to
    new_commit to them
    """
    for c in changes:
        print "W: Applying changes to seam (%s->%s) from %s to %s\n"%(c.source, c.dest, old_commit, new_commit)
        raise utils.Bug("modify_seams not yet implemented")

def add_seams(spec, base_obj, seams, base_commit):
    """
    Take the array of seam objects in seams and create the new seams in seams.
    """
    for s in seams:
        print("W: Creating new seam (%s->%s) from %s \n"%(s.get_source(), s.get_dest(), base_obj.name))
        # Really, just copy the directories over. If there are files already there, keep them.
        src = os.path.join(layout.base_repo(spec.base_dir, base_obj.name), s.get_source())
        dest = os.path.join(spec.base_dir, s.get_dest())
        try:
            os.makedirs(dest)
        except:
            pass
        # Now just rsync it all over
        utils.run(["rsync", "-avz", os.path.join(src, "."), os.path.join(dest, ".")])
        # Make sure you add all the files in the subdirectory
        git.add_in_subdir(spec.base_dir, dest)
    # Now commit them with an appropriate header.
    hdrs = headers.seam_op(headers.SEAM_VERB_ADDED, base_obj, seams, base_commit)
    git.commit(spec.base_dir, hdrs, [] )

COMPLETION_PREFIX="import pull\n" + \
    "def go(spec):"
COMPLETION_SUFFIX="\n"

def write_completion(spec, cmds_ok, cmds_abort):
    f = open(layout.completion_file(spec.base_dir), "w+")
    f.write(COMPLETION_PREFIX)
    f.write(cmds_ok)
    f.write(COMPLETION_SUFFIX)
    f.close()
    f = open(layout.abort_file(spec.base_dir), "w+")
    f.write(COMPLETION_PREFIX)
    f.write(cmds_abort)
    f.write(COMPLETION_SUFFIX)
    f.close()

def done_completion(spec):
    os.unlink(layout.completion_file(spec.base_dir))
    os.unlink(layout.abort_file(spec.base_dir))


def do_completion(spec):
    c = layout.completion_file(spec.base_dir)
    if (os.path.exists(c)):
        f = utils.dynamic_load(c)
        f.go(spec)
        os.unlink(c)
        os.unlink(layout.abort_file(spec.base_dir))
    else:
        raise utils.GiveUp("No pending command to complete")
    
def do_abort(spec):
    c  = layout.abort_file(spec.base_dir)
    if (os.path.exists(c)):
        f = utils.dynamic_load(c)
        f.go(spec)
        os.unlink(c)
        os.unlink(layout.completion_file(spec.base_dir))
    else:
        raise utils.GiveUp("No pending command to abort")


# End file.
