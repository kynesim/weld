====
Weld
====

(in text because I am far less neat than Tony).

The multiple repository model used by muddle makes it quite difficult
to track changes. It would be simpler if there was a single git 
repository for a project which could track back to other repositories.

weld is the tool which makes that possible.

weld uses a directory, .welded, inside your git repository to store
meta-information about which repositories you use and where they 
come from.

Because all the best shell scripts parse XML, the files inside .welded
are written in XML. We did consider using Python, but felt that given
the highly declarative nature of the information described, the 
number of opportunities for self-mutilation was just too high.


Files in .welded
================

 .welded/weld.xml 
   This is a top-level file that describes this weld.

 .welded/completion
   A set of instructions for weld finish to perform once you have
    completed your merge.

 .welded/bases/ ..
   Copies of all your bases.

 .welded/counter
   Counts upward; this is used to force changes so we never have
   empty commits - git commit --allow-empty doesn't really work and
   can easily lose commits.

bases and seams
===============

 A base is a git repository (and branch) from which one pulls seams and to which
   they are pushed.

 A seam is a mapping from a directory in a git repository to a directory in the 
   weld in which it will appear.

weld.xml
========

 A typical weld.xml:

 <?xml version="1.0" ?>
 <weld name="frank">
   <origin uri="ssh://git@home.example.com/ribbit/fromble" />

   <base name="project124" uri="ssh://git@foo.example.com/my/base" branch="b" rev=".." tag=".."/>
   <base name="igniting_duck" uri="ssh://git@bar.example.com/wobble" />

   <seam base="project124" dest="flibble" />
   <seam base="igniting_duck" source="foo" dest="bar" />

 </weld>
 

 This file tells weld:

   * This weld is called frank - this name is used when upstreaming.
   * The origin for this weld is at ssh://git@home.example.com/ribbit/fromble.
   * This weld draws from two bases: project124 and igniting_duck
   * project124 turns up in a directory in the weld called flibble.
   * igniting_duck/foo turns up in <weld>/bar

Going behind weld's back
========================

 As with muddle, weld attempts to support you going behind its back.


Using weld   
==========

 weld init weld.xml
  
   This command takes a weld.xml that you have written and creates a git 
    repository for it, including writing you a .git/info/sparse-checkout file.

 weld import

   This command imports any missing repos into the weld. If any branches have
    changed, 

 weld upstream <base>

   Here is where the magic happens. Weld collects all the diffs that might affect
  <base> and ports them (individually) upstream to that base. Weld axdds a
  Welded-From: <name>/<commit-id> to each comment.

 weld sync <URI>

   Weld will check out the .weld from <URI> and synchronise with it -
this is largely a clone, but because weld will write a sparse-checkout file
you do not need to check out any parts of the repository which are not 
currently in the weld.

Headers that weld introduces
============================

 Weld will occasionally leave commits containing messages to itself.
It is important that you do not start any legitimate commit messages
with

X-Weld-State:

 The messages it leaves are:

X-Weld-State: Merged/[base]:[commit-id]  [src]:[dest] ...

 Indicates that it merged [base]:[commit-id] with the following seams.

X-Weld-State: Init

 Indicates that the weld started here (with nothing merged)

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
So we're pulling a base.

  (pulling an individual seam would in theory be possible, but rather fiddly,
  and of questionable use anyway, so we'll go with just pulling bases).

1. Weld makes sure its copy of the base is up-to-date

   a. If it doesn't yet have a clone of the base, it does::

         cd .weld/bases
         git clone <base-repository>
         cd <base>
         git pull

   b. If it does have a clone of the base, it does::

         cd .weld/bases/<base>
         git pull

2. Back in the "main" directory structure (outside the .weld) it branches
   with a branch name of the form "weld-merge-<base>-<index>", where <index>
   is chosen to make the branch unique in this repository. The branch point is
   the last "X-Weld-State: Merged <base>" commit, or the "X-Weld-State: Init"
   commit.

3. It rsyncs the source directory (as specified in the seam in the weld XML
   file) onto the target directory (ditto), and commits that.

4. It rebases (from) the branch point (to HEAD) onto this branch.

5. It does a squash merge of the branch back onto master, and commits that
   with an "X-Weld-State: Merged <base>" message.

Note that it doesn't delete the "transient" branch (and the last such branch
may actually appear to be an ancestor of HEAD). We may add a "weld tidy"
command at some time to remove "weld-" branches, but during the current active
development they may be useful.

Also note that the "weld-" branches are always meant to be local to the
current repository - they're not meant to be pushed anywhere else.

This procedure will preserve the obvious ordering for the "Merged" state
messages, but the "Seam-Added" messages on master may appear reversed (or in
some other unobvious order) because of the way the above is done. This should
not matter.

So one can end up with a git log something like the following (but note I've
shortened the SHA1 ids in the X-Weld-State messages, which are normally
presented at full length)::

  * 5b3b562 (HEAD, master) X-Weld-State: Merged project124/4849616[[null, "124"]]
  * ad9cb22 (weld-merge-project124-1) X-Weld-State: PortedCommit project124/4849616[[null, "124"]]
  * 8e5acbd X-Weld-State: Merged project124/46b0f6c[[null, "124"]]
  * 6192696 X-Weld-State: Merged igniting_duck/ef9c9c0[["one", "one-duck"], ["two", "two-duck"]]
  * d7be62e X-Weld-State: Seam-Added igniting_duck/ef9c9c0[["one", "one-duck"], ["two", "two-duck"]]
  * 43505fb (weld-merge-project124-0) X-Weld-State: Seam-Added project124/46b0f6c[[null, "124"]]
  | * 17be721 (weld-merge-igniting_duck-0) X-Weld-State: Seam-Added igniting_duck/ef9c9c0[["one", "one-duck"], ["two", "two-duck"]]
  |/  
  * f07cd81 X-Weld-State: Init

or (in a user's checkout of the weld)::

  * a4406c3 (HEAD, master) Also build two-duck, same as two
  * 09fe795 Add a comment to the end of the Makefile
  * 86f4852 Add three-and-a-bit
  * 9b95689 X-Weld-State: Merged project124/4849616[[null, "124"]]
  * f2fab93 Ignore executables
  * 68b3e53 (weld-merge-project124-0) X-Weld-State: PortedCommit project124/4849616[[null, "124"]]
  * 8e5acbd (origin/master, origin/HEAD) X-Weld-State: Merged project124/46b0f6c[[null, "124"]]
  * 6192696 X-Weld-State: Merged igniting_duck/ef9c9c0[["one", "one-duck"], ["two", "two-duck"]]
  * d7be62e X-Weld-State: Seam-Added igniting_duck/ef9c9c0[["one", "one-duck"], ["two", "two-duck"]]
  * 43505fb X-Weld-State: Seam-Added project124/46b0f6c[[null, "124"]]
  * f07cd81 X-Weld-State: Init

Not having those "remotes/origin/weld-" branches
------------------------------------------------
As we said above, weld uses branches called "weld-..." to do its work, and
doesn't delete them when it has finished with them. This means that if you
then do a::

  git clone <weld-repository>

you will see (in ``gitk --all`` or with ``git branch -a``) the ``weld-...``
branches in the ``remotes/origin/``. These are of no use at all. The simplest
way to not see them is to not get them in the first place. If you have git
version 1.7.10 or later, then you can do::

  git clone --single-branch <weld-repository>

to retrieve (in this case) just master (or use ``-b <branch`` to name a
specific branch).

Of course, unfortunately, if you later do a ``git pull``, then the branches
will be fetched for you at that stage, so it's not a perfect solution.

Our putative "weld tidy" maybe needs to do more work than we first thought...
.. vim: set filetype=rst tabstop=8 softtabstop=2 shiftwidth=2 expandtab:
