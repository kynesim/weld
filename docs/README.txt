==========================
Weld - the original README
==========================

*This chapter is being rewriten, and possibly split into separate parts. Some
of it may be inaccurate. Please be patient.*

Why we needed weld
==================
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

Getting the weld command line tool
==================================
Getting weld needs git. If you don't have git on your system, and you're on
a Debian based system (Debian, Ubuntu, Linux Mint, etc.), then you can do::

  $ sudo apt-get install git gitk

(the ``gitk`` program is an invaluable UI for looking at the state of git
checkouts - it's always worth checking it out as well as git itself).

Then decide where to put weld. I have a ``sw`` directory for useful software
checkouts, so I would do::

  $ cd sw
  $ git clone https://code.google.com/p/weld/

which creates me a directory ``~/sw/weld``.

.. note:: Sometimes (luckily not often) the Google code repositories give
   errors. In this case, the only real solution is to try again later.

To *use* weld, you can then either:

1. just type ``~/sw/weld/weld`` - this is the simplest thing to do,
   but the longest to type.

2. add an alias to your ``.bashrc`` or equivalent::

      alias weld="${HOME}/sw/weld/weld"

3. add ``~/sw/weld`` to your PATH::

      export PATH=${PATH}:${HOME}/sw/weld

4. add a link - for instance, if you have ``~/bin`` on your path, do::

     cd ~/bin
     ln -s ~/sw/weld/weld .

Personally, I use the second option, but all are sensible.

You should now be able to do::

  $ weld help

and get meaningful output.

Terminology: welds, bases and seams
===================================
A **weld** is a git repository containing all of the source code for a
project.

``weld`` is also the command line tool that is used to maintain welds.

A **seam** is a mapping from a directory in an external git repository to the
directory in the weld in which it will appear.

Colloquially it is also the directory in the weld that is so described.

A **base** is an external git repository (and implicitly its branch or
other specifiers) from which one pulls seams and to which they are pushed.

The term may also be used to refer to the clone of that external directory in
the ``.weld/bases`` directory.

weld.xml
========

A simple weld.xml::

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
  moment (caveat: It is put into the "X-Weld-State: Pushed" markers in the
  base, but otherwise never referenced).
* The origin for this weld is at ssh://git@home.example.com/ribbit/fromble.
* This weld draws from two bases: project124 and igniting_duck.
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

.. warning:: *Do not cross the streams.* Specifically, no two different seams
   should have the same destination, lest weld get terribly confused. This
   also means that destinations that "nest" - e.g., ``src/fred`` and
   ``src/fred/jim`` - are forbidden.

.. note:: I am not aware of anything that ensures that the origin URI
   corresponds to the place that you actually clone the weld from. Indeed,
   since it is a URI (and not a URL), it need not so corresppnd. However, if
   you do something obscure based on this, then no-one is going to like you.

Files in .weld
==============
When you first clone a weld, the only file in the ``.weld`` directory will be:

* ``welded.xml`` - this is the file that describes this weld. It is a copy of
  the XML file given to weld init.

After doing a ``weld pull``, a ``weld push``, or a ``weld query`` on a base
(which may need to "pull" the base to find out about it), there will also be:

* ``bases/`` - this is a directory containing a clone of each of your bases,
  retrieved as they are needed.

You may also see:

* ``counter`` - this is a file whose content counts upward. It is used to
  force changes so we never have empty commits when doing ``weld pull`` (or
  ``weld push``). It appears to be necessary because - ``git commit
  --allow-empty`` can sometimes lose commits.

During a ``weld pull`` or ``weld push`` you will also see:

* ``complete.py`` - the script that ``weld finish`` runs.
* ``abort.py`` - the script that ``weld abort`` runs.

and ``weld push`` also creates:

* ``pushing/`` - which contains the commit message to be used at the end of
  the ``weld push``, and a marker to indicate whether a merge is in progress.

All of these should be deleted when the ``weld pull`` or ``weld push`` is
finished (and, specifically, ``weld finish`` and ``weld abort`` should delete
them).

Things to remember not to do in a world of welds
================================================
Do not use git submodules in bases, as weld will not preserve them.

Do not use commit messages that start "X-WeldState:", as weld uses such for
its own purposes.

Do not use branches that start "weld-", as weld uses such for its own purposes
(and is not very careful in checking if you're on an offending branch).

Do not change the ``origin`` remote of a weld - the weld command assumes that
``origin`` is the origin remote it should use.

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

   Finish a weld pull or push that had problems (indicating that the problems
   were fixed).

weld abort

   Abort a weld pull or push that had problems (thus discarding it)

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

Commit messages that weld inserts
=================================

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



.. vim: set filetype=rst tabstop=8 softtabstop=2 shiftwidth=2 expandtab:
