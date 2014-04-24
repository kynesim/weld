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


