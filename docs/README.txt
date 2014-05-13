==========================
Weld - the original README
==========================

The multiple repository model used by muddle makes it quite difficult
to track changes. It would be simpler if there was a single git 
repository for a project which could track back to other repositories.

weld is the tool which makes that possible.

weld uses a directory, ``.weld``, inside your git repository to store
meta-information about which repositories you use and where they 
come from.

Because all the best shell scripts parse XML, the files inside ``.weld``
are written in XML. We did consider using Python, but felt that given
the highly declarative nature of the information described, the 
number of opportunities for self-mutilation was just too high.


Files in .welded
================

 .weld/welded.xml 
   This is the file that describes this weld. It is a copy of the XML file
   given to weld init.

 .weld/completion
   A set of instructions for weld finish to perform once you have
   completed your merge (i.e., "weld pull")

 .weld/bases/ ..
   Copies of all your bases.

 .weld/counter
   Counts upward; this is used to force changes so we never have
   empty commits - git commit --allow-empty doesn't really work and
   can easily lose commits.

bases and seams
===============

A **base** is a git repository (and branch) from which one pulls seams and to
which they are pushed.

A **seam** is a mapping from a directory in a git repository to a directory in
the weld in which it will appear.

weld.xml
========

A typical weld.xml::

   <?xml version="1.0" ?>
   <weld name="frank">
     <origin uri="ssh://git@home.example.com/ribbit/fromble" />
     <base name="project124" uri="ssh://git@foo.example.com/my/base" branch="b" rev=".." tag=".."/>
     <base name="igniting_duck" uri="ssh://git@bar.example.com/wobble" />
     <seam base="project124" dest="flibble" />
     <seam base="igniting_duck" source="foo" dest="bar" />
   </weld>
 

This file tells weld:

   * This weld is called frank. This name is not used for anything at the
     moment (caveat: It may be used in the "X-Weld-State: Pushed" markers)
   * The origin for this weld is at ssh://git@home.example.com/ribbit/fromble.
   * This weld draws from two bases: project124 and igniting_duck
   * project124 turns up in a directory in the weld called flibble.
   * igniting_duck/foo turns up in <weld>/bar

Details
-------
The XML file must:

* start with an XML version line: ``<?xml version="1.0" ?>``, because
  otherwise it wouldn't be XML

* continue with the start of a weld definition: ``<weld name=``\ *name*\
  ``>``. Whilst the weld name is required, it is not currently used for
  anything.

* which contains an ``<origin uri=``\ *origin*\ ``/>`` entity (althogh the
  ``uri`` is optional at the moment)

* as well as zero or more base and seam definitions

* and end with the end of a weld definition: ``</weld>``

Comments are allowed as normal, and are ignored (and will not be retained when
the XML file is copied).

Only one weld definition is allowed in a file, although this may or may not be
checked - regardless, any weld definitions after the first are ignored.

With a weld definition, there are two types of entity:

* base definitions
* seam definitions

These may occur in any order. A base must have at least one corresponding
seam, and a seam must belong to a single base. The two are linked by the base
name,

A base definition contains:

* ``name`` - the name of this base
* ``uri`` - the URI for the repository from which this base is to
  cloned/checked out
* ``branch``, ``rev`` or ``tag`` - the branch, revision or tag to clone/check
  out. These defaut to "master", "HEAD" and (essentially) "HEAD" respectively.
  It is not currently defined what happens if you specify more than one of
  these for a particular base.

A seam definition contains:

* ``base`` - the name of the base that this seam belongs to. This base must
  already have been defined in the XML file.
* ``name`` - the name of this seam. This is optional, and defaults to None
* ``source`` - where the seam's contents are taken from in the base
  repository. This is optional, and defaults to ``"."``, meaning the top
  (root) of the repository.
* ``dest`` - where the seam is to be put in the target directory in the weld.
  This is optional and defaults to ???.
* ``current`` - ??? This is optional and defaults to ???

It is not defined what happens if the same base or seam is defined more than
once (with either the same values or different values).

It *is* intended that two bases with diffferent names be regarded as
different, although what happens if that is the only difference between them
is not defined.

  *Do not cross the streams.* Specifically, no two different seams should have
  the same destination, lest weld get terribly confused. This also means
  that destinations that "nest" - e.g., ``src/fred`` and ``src/fred/jim`` -
  are forbidden.

Going behind weld's back
========================

As with muddle, weld attempts to support you going behind its back. This
mainluy means assuming that you're going to use git to do stuff regardless.
Indeed, we shall see that using git directly is integral to the correct use of
welds.

A summary of weld commands  
==========================

weld init <weld-xml-file>
  
   This command takes a <weld-xml-file> that you have written and creates a git 
   repository for it.

   The XML file is written to ``.weld/welded.xml``.

   An initial ``.gitignore`` file is created, which tells git to ignore
   various weld working files, including ``.weld/bases``.

weld pull <base-name>

   The special "name" ``_all`` means "pull all bases".

weld finish

   Finish a weld pull that had problems (indicating that the problems were
   fixed).

weld abort

   Abort a weld pull that had problems (thus discarding it)

weld query bases

   List the bases, and their seams

weld query base <base-name>

   Report on the current state of the named base.

weld query seam-changes <base-name>

   Report on the seam changes for the named base.

weld status

   If we are part way through a ``weld pull`` or ``weld push`` say so.

   Otherwise, report on whether we should do a ``git pull`` or ``git push`` of
   our weld. This is intended to be useful before doing a ``weld pull`` or
   ``weld push`` of our bases.

Headers that weld introduces
============================

Weld will occasionally leave commits containing messages to itself.
It is important that you do not start any other commit messages
with ``X-Weld-State``

The messages it leaves are:

X-Weld-State: Init

 Indicates that the weld started here (with nothing merged)

X-Weld-State: PortedCommit <base-name>/<commit-id> [<seams>]

 Indicates that it ...

X-Weld-State: Seam-Added <base-name>/<commit-id> [<seams>]

 Indicates that it ...

X-Weld-State: Seam-Deleted <base-name>/<commit-id> [<seams>]

 Indicates that it ...

X-Weld-State: Seam-Changed <base-name>/<commit-id> [<seams>]

 Indicates that it ...

X-Weld-State: Merged <base-name>/<commit-id> [<seams>]

 Indicates that it merged <base-name> <commit-id> with the following seams.

X-Weld-State: Pushed  <base-name>/<commit-id> [<seams>]

 Indicates that it ...

Note that the ``X-Weld-State: Seam-`` messages only occur in the branches on
which base merging is done.

In the base repositories, it can also leave a commit message of the
form::

  X-Weld-State: Pushed <base-name> from weld <weld-name>

This commit will then contain a sequence of lines, each of which is
(currently) the "short" SHA1 id for a squashed component commit, followed by
its one line summary - so for instance::

    X-Weld-State: Pushed igniting_duck from weld fromble
    
    e8addb1 Add trailing comments across the bases and to the weld
    7eaa68a One-duck: Also build one-duck, same as one
    f589384 One-duck: Add a comment to the end of the Makefile

The format of this message may change in the future.

Using the weld command line tool
================================
weld init
---------
::

  weld init <weld-xml-file>

Reads in a weld XML file, and:

1. writes out the same data (possibly in a different order) to
   ``.weld/welded.xml``
2. Does a ``git init``
3. Write a ``.gitignore`` to ignore various transient files that may appear
   in the ``.weld`` directory.
4. Commits the ``.gitignore`` and ``.weld/welded.xnl`` to git, with the commit
   message::

      X-Weld-State: Init

      Weld initialisation

...and more stuff to be written


Interesting information
=======================
...or stuff Tibs is learning about weld that will get put somewhere else
later, but he doesn't want to lose...

How "weld pull" does its stuff
------------------------------
Remember, "weld pull" updates its idea of the bases, and then updates the
seams in the weld "to match".

  The main code for this is in ``welded/pull.py``

So we're pulling a base

  (You can also pull multiple bases at once, by giving multiple base names on
  the command line, or use ``weld pull _all`` to pull all bases, but these
  both just work by doing this whole sequence for each base in turn. Note that
  this can be more confusing, for instance if the Nth base requires remedial
  action to take to "finish" it, at which point you have to fix the problem,
  do ``weld finish``, and then give the original weld command again to pull
  the remaining bases.)

  (Pulling an individual seam would in theory be possible, but rather fiddly,
  and of questionable use anyway, so we'll go with just pulling bases).

Given the name of a base:

#. Weld checks that there are no local changes in the weld - specifically, it
   runs ``git status`` in the weld's base directory (the directory containing
   the ``.weld`` directory). If there are any files in the weld that could be
   added with ``git add`` or committed with ``git commit``, then it will
   refuse to proceed, suggesting that the user commit or stash the changes
   first.

#. It finds the last merge for the given base-name (i.e., the last commit with
   an ``X-Weld-State: Merged <base-name>`` message). If there isn't one, it
   finds the ``X-Weld-State: Init`` commit.

#. Weld makes sure its copy of the base is up-to-date:

   a. If it doesn't yet have a clone of the base, it does::

         cd .weld/bases
         git clone <base-repository>
         cd <base>
         git pull

   b. If it does have a clone of the base, it does::

         cd .weld/bases/<base>
         git pull

   and notes the HEAD commit of the base.

#. It determines which (if any) seams have been deleted, changed or added in
   the weld (with respect to the now up-to-date base). If all of those lists
   are empty, there is nothing to do, and the ``weld pull`` for this base is
   finished.

#. Back in the "main" directory structure (outside the .weld) it branches.
   The branch point is the last "X-Weld-State: Merged <base>" commit, or the
   "X-Weld-State: Init" commit, as located above.

       (The branch name used is chosen to be unique to this repository, and
       is currently of the form "weld-merge-<base>-<index>", where <index> is
       chosen to make the branch unique.)

#. It then:

   * deletes any deleted seams
   * modifies any modified seams
   * adds any added seams

   within that branch.

#. It writes ``.weld/complete.py`` and ``.weld/abort.py``, which can later be
   used by the ``weld finish`` and ``weld abort`` commands if necessary (and
   which will be deleted if the ``weld pull`` of this base doesn't need user
   interaction).

#. It merges the original branch (typically ``master``) onto this temporary
   branch. This will commonly "just work", but if anything goes wrong, the
   ``weld pull`` stops with a return code of 1 and a message of the form::

        <merge error message>
        Merge failed
        Either fix your merges and then do 'weld finish',
        or do 'weld abort' to give up.

#. If the merge onto the branch succeeded, or if the user fixes problems and
   then does ``weld finish``, then the ``complete.py`` script is run, which:

   a. changes back to the original branch
   b. calculates the difference between this branch and the temporary branch
      on which we did our merge
   c. applies that patch to this original branch
   d. makes sure that any changed files are added to the git index (it does
      this over the entire weld, but that should be OK because nothing else
      should be changing the weld whilst we're busy)
   e. commits this whole operation using an appropriate ``X-Weld-State: Merged
      <base-name>`` message.
   f. deletes the ``finish.py`` and ``abort.py`` scripts

   At the moment, this doesn't delete the temporary/working branch (which will
   show as a loop if you look in gitk). Future versions of weld may do so
   as part of the "complete" phase, or we may add a "weld tidy" command
   to remove them, but during the current active development it's thought to
   be useful to leave the branch visible.

#. If the merge didn't succeed, and the user chooses to do ``weld abort``,
   then the ``abort.py`` script is run, which:

   * switches back to the original branch
   * deletes the temporary/working branch
   * deletes the ``finish.py`` and ``abort.py`` scripts

Also note that the "weld-" branches are always meant to be local to the
current repository - they're not meant to be pushed anywhere else.

Not having those "remotes/origin/weld-" branches
------------------------------------------------
If you do a ``weld pull`` and then do a ``git push`` of the weld, in general
the transient branches will not be propagated to the weld's remote.

However, if you clone directly from a "working weld", then by default all
branches are cloned, which is (a) untidy, and (b) mak cause future working
branches to have the same name as earlier (remote) working branches.

If you have git version 1.7.10 or later, then you can instead clone a
"working" weld using::

  git clone --single-branch <weld-directory>

to retrieve (in this case) just ``master`` (or use ``-b <branch`` to name a
specific branch).

Of course, unfortunately, if you later do a ``git pull``, then the branches
will be fetched for you at that stage, so it's not a perfect solution.

How "weld push" should work
---------------------------
Again, we're only going to look at doing "weld push" on a single base - the
command line will (probably) take more than one base name, pr the magic
``_all``, but we'll ignore that here.

  *This is still to be implemented as a "weld push" command*

So doing ``weld push`` for a given base name works as follows:

#. The seams for the base are looked up, and thus the individual seam
   directories identified.

#. The original branch (of the weld) is remembered.

#. The commit id of the last push for the given base-name (i.e., the last
   commit with an ``X-Weld-State: Pushed <base-name>`` message) is located. If
   there isn't one, the ``X-Weld-State: Init`` commit is used.

#. ``git log`` is used to determine what commits have happened between that
   last push and HEAD. Then all the ``X-Weld-State`` commits are removed from
   the list.

   If that leaves an empty list of commits, then nothing needs to be pushed
   for this base name, and we are finished.

#. At the moment, in the development version of the code, a tag may be put at
   the last-Pushed (or Init) commit. This is not required by anything else,
   and just serves to make it more obvious how ``weld push`` works.

#. For each seam in this base, the changes for each commit in the list are
   calculated, using ``git diff``, and remembered.

      I am assuming that they are saved to a file with a name of the form
      something like
      ``.weld/pushing/<base-name>/<seam-name>/<index>-diff.txt``
      where ``<index>`` retains the appropriate order of the differences
      (which is, carefully, the correct order to apply them in, the reverse
      of the order of the commit ids we found in our ``git log`` list).

      This means that ``.weld/pushing`` needs adding to the default
      ``.gitignore`` file that ``weld init`` creates.

#. Two script files, ``.weld/continue.py`` and ``.weld/abort.py``, are
   written.

#. The base is branched, so that our amendments to it can be done on that
   branch.

#. The ``continue.py`` script is run.

   This applies the patches for each seam in the appropriate ``pushing``
   directory - i.e., it:

   a. takes the first patch from the first available ``<seam-name>`` directory
   b. uses ``git apply`` to apply it
   c. deletes the patch file
   d. if that leaves the directory empty, deletes the ``<seam-name>``
      directory

#. If the ``git apply`` succeeded, it then:
  
   * goes on to the next patch file for that seam, or starts on the next
     ``<seam-name>`` directory, and so on, until there are no ``<seam-name>``
     directories left,
   * at which point it deletes ``pushing/<branch-name>`` directory, and also
   * deletes the ``continue.py`` and ``abort.py`` scripts

   It then:

   * commits the changes to the base with a message of the form
     ``X-Weld-State: Pushed <base-name> from weld <weld-name>``, and summary
     lines for the actual changes we've folded in.
   * merges the branch back onto the base's original branch (using a
     fast-forward only merge)
   * does a ``git push`` of the base to its remote

   Given a ``weld pull`` before this final ``git push``, this should succeed
   because the base was up-to-date before the push.

   Then, back in the weld, it adds an empty commit containg the message
   ``X-Weld-State: Pushed <base-name>/<commit-id> <seams>``, so that we have a
   record of where the push was done from (for use in future ``weld push``
   commands).

   Note that this means you should consider doing a ``git push`` of your weld
   after any ``weld pull`` command.

#. If a problem occurred with the ``git apply``, then the user is expected to
   fix it, and then issue a ``weld continue`` command (which just re-runs the
   ``continue.py`` script, so behaves as described above), or to issue a
   ``weld abort`` command, which:

   * deletes the working branch on the base
   * deletes the ``pushing/<base-name>`` directory
   * deletes the ``continue.py`` and ``abort.py`` scripts

.. vim: set filetype=rst tabstop=8 softtabstop=2 shiftwidth=2 expandtab:
