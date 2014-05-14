==========================
Weld - the original README
==========================

*This chapter is being rewriten, and possibly split into separate parts. Some
of it may be inaccurate. Please be patient.*

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

Getting weld
============
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

...and more stuff to be written


How things work
===============

Things to remember not to do in a world of welds
------------------------------------------------

Do not use git submodules in bases, as weld will not preserve them.

Do not use commit messages that start "X-WeldState:", as weld uses such for
its own purposes.

Do not use branches that start "weld-", as weld uses such for its own purposes
(and is not very careful in checking if you're on an offending branch).

Do not change the ``origin`` remote of a weld - the weld command assumes that
``origin`` is the origin remote it should use.

How "weld pull" does its stuff
------------------------------
*Obviously, the code is the final word on what happens, but this is intended
as reasonable background.*

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

   It also checks whether:

   * the user is part way through an unfinished ``weld pull`` or ``weld push``
   * the weld could be updated with ``git pull`` (it looks at the remote
     repository to determine this)
   * the current branch is a weld-specific branch (starting with ``weld-``).

   and refuses to proceeed if any of those is true (this is essentially what
   ``weld status`` does, so you can do it beforehand as well).

#. It finds the last time that ``weld pull`` or ``weld push`` was done for
   this base, by looking for the most recent commit with an ``X-Weld-State:
   Merged <base-name>`` or ``X-Weld-State: Pushed <base-name>`` message. If
   there isn't  one (i.e., this is the first ``weld pull`` or ``weld push``
   for this weld), then it uses the ``X-Weld-State: Init`` commit instead.

       For ``weld pull`` we want to know the last time our base was
       synchronised with the weld as a whole. Since both ``weld pull`` and
       ``weld push`` do this, we can use either as the relevant place to work
       from.

#. Weld makes sure its copy of the base is up-to-date:

   a. If it doesn't yet have a clone of the base, it does::

         cd .weld/bases
         git clone <base-repository> <base>
         cd <base>
         git pull

   b. If it does have a clone of the base, it does::

         cd .weld/bases/<base>
         git pull

   In either case, it notes the HEAD commit of the base.

#. It determines which (if any) seams have been deleted, changed or added in
   the weld (with respect to the now up-to-date base). If all of those lists
   are empty, there is nothing to do, and the ``weld pull`` for this base is
   finished.

#. It branches the weld. The branch point is the synchronisation commit that
   was found earlier (the last ``weld pull`` or ``weld push`` commit, or else
   the Init commit).

       (The branch name used is chosen to be unique to this repository, and
       is currently of the form "weld-merge-<commit-id>-<index>", where
       <commit-id> is the first 10 characters of the synchronisation commits
       SHA1 id, and <index> is chosen to make the branch unique in case that
       is not enough.)

#. It then:

   * deletes any deleted seams
   * modifies any modified seams
   * adds any added seams

   within that branch.

   Deleting a seam is easy - it just means deleting the appropriate directory.

   Adding a seam just copies the directory structure for that seam across
   from the base into the correct place in the weld.

   Modifying a seam uses ``git diff`` to determine the appropriate changes in
   the base, and then replays them in the weld.

     .. note:: *TODO* It occurs to me that the technique use in ``weld push``
        might be more efficient than this last, if it turns out to be usable -
        I'd need to think on this further. (Tibs)

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
   f. deletes the ``complete.py`` and ``abort.py`` scripts

   At the moment, this doesn't delete the temporary/working branch (which will
   show as a loop if you look in gitk). Future versions of weld may do so
   as part of the "complete" phase, but during the current active development
   it's thought to be useful to leave the branch visible.

#. If the merge didn't succeed, and the user chooses to do ``weld abort``,
   then the ``abort.py`` script is run, which:

   * switches back to the original branch
   * deletes the temporary/working branch
   * deletes the ``complete.py`` and ``abort.py`` scripts

Also note that the ``weld-`` branches are always meant to be local to the
current repository - they're not meant to be pushed anywhere else.

Not having those "remotes/origin/weld-" branches
------------------------------------------------
If you do a ``weld pull`` and then do a ``git push`` of the weld, in general
the transient branches will not be propagated to the weld's remote.

However, if you clone directly from a "checked out" weld (rather than from a
bare repository), then by default all branches are cloned, which is (a)
untidy, and (b) mak cause future working branches to have the same name as
earlier (remote) working branches.

If you have git version 1.7.10 or later, then you can instead clone a
"working" weld using::

  git clone --single-branch <weld-directory>

to retrieve (in this case) just ``master`` (or use ``-b <branch`` to name a
specific branch).

Of course, unfortunately, if you later do a ``git pull``, then the branches
will be fetched for you at that stage, so it's not a perfect solution. But
then maybe you shouldn't clone a "checked out" weld.

How "weld push" works
---------------------
*Obviously, the code is the final word on what happens, but this is intended
as reasonable background.*

Again, we're only going to look at doing "weld push" on a single base - the
command line will take more than one base name, or the magic ``_all``, but
we'll ignore that here.

So doing ``weld push`` for a given base name works as follows:

#. Weld checks that there are no local changes in the weld - specifically, it
   runs ``git status`` in the weld's base directory (the directory containing
   the ``.weld`` directory). If there are any files in the weld that could be
   added with ``git add`` or committed with ``git commit``, then it will
   refuse to proceed, suggesting that the user commit or stash the changes
   first.

   It also checks whether:

   * the user is part way through an unfinished ``weld pull`` or ``weld push``
   * the weld could be updated with ``git pull`` (it looks at the remote
     repository to determine this)
   * the current branch is a weld-specific branch (starting with ``weld-``).

   and refuses to proceeed if any of those is true (this is essentially what
   ``weld status`` does, so you can do it beforehand as well).

#. Weld makes sure its copy of the base is up-to-date:

   a. If it doesn't yet have a clone of the base, it does::

         cd .weld/bases
         git clone <base-repository> <base>
         cd <base>
         git pull

   b. If it does have a clone of the base, it does::

         cd .weld/bases/<base>
         git pull

#. It finds the last time that ``weld push`` was done for this base, by
   looking for the most recent commit with an ``X-Weld-State: Pushed
   <base-name`` message. If there isn't one (i.e., this is the first ``weld
   push`` for this weld), then it uses the ``X-Weld-State: Init`` commit
   instead.

      Why do we use the last ``weld push``, and not the last ``weld push``
      *or* ``weld pull``?
     
      Consider the following "pseudo git log"::
     
        6   +   change B to a file in base <fred>
        5   o   X-Weld-State: Merged <fred>/...
        4   -   a change to some irrelevant file(s)
        3   +   change A to a file in base <fred>
        2   o   X-Weld-State: Pushed <fred>/...
        1   x   some common commit
     
      So we last did ``weld pull`` at commit 5, and the weld thus contains all
      the changes from base <fred> up to that point.
     
      However, we last did a ``weld push`` at commit 2, which means that
      changes 3 and 6 have still to be applied to base <fred>. But change 3 is
      before our last ``weld pull``, so we definitely want the last ``push``.
     
      .. note:: Remember: ``weld pull`` updates the base from its remote, and
         then brings any changes therein into our weld. It does not propagate
         any changes in the weld back to the base.

#. Weld looks up the current seams being used for this base. This tells it
   which directories (in the weld and in the base) it is interested in.

#. It looks up all of the changes in the weld since the synchronisation point
   (using ``git log --one-line``) and remembers them.

   If there aren't any, it has finished.

#. It trims out any ``X-Weld-State`` commits from that list, and remembers
   *it*.

   Again, if there are no changes (left), then it has finished.

#. As an aid during development (so this may go away later on), it tags the
   synchronisation commit, using a tag name of the form
   ``weld-last-<base-name>-sync-<commit-id>``, where <commit-id> is the first
   10 characters of its SHA1 commit id.

#. In the base, it branches at the synchronisation point (remember,
   ``X-Weld-State`` commit messages record the equivalent commit id in the
   base as well), using a branch name of the form
   "weld-pushing-<commit-id>-<index>".

#. We then update the branch in the base:

   For each seam that the base currently has in our weld:

   1. We use ``git ls-files`` in the appropriate seam in the weld to find out
      which files git is managing.
   2. We do the same in the corresponding directory in the base.
   3. For files which the seam (in the weld) has, but the base does not, we
      do ``git rm``. We commit that change.
   4. For all the other files in the seam, we just copy them over into the
      base (actually, we use ``rsync``). It is, of course, quite likely that
      many of them won't have changed, but that's OK. Then we ``git add`` all
      of the files we've copied, in the base, and commit that change as well.

   .. note:: Any seams that are not in the weld are, by definition, not of
      interest to us. Even if they were in the weld at the last
      synchronisation point, the fact they aren't *now* means we are not
      interested in any (possible) intermediate changes - if we cared about
      such changes, we should have done ``weld push``  then.

#. We prepare a final commit message, and write out the ``.weld/complete.py``
   and ``.weld/abort.py`` files.

#. We run the ``complete.py`` file to finish off our ``weld push``. This:

   * sets the merging indicator (touches a file in the ``.weld/pushing``
     directory)
   * in the base, if the merging indicator is not set, merges the original
     branch (normally "master") into our working branch - this should just
     proceed with no problems
   * still in the base, merges that back into the original branch
   * still in the base, commits the change using the saved commit message

       The commit message has a summary of the corresponding commits from the
       weld, as output by ``git log --one-line``.

       If the user specified ``weld push -edit``, then they get the chance to
       edit the message before it is used.

   * notes the new HEAD commit id in the base
   * adds an ``X-Weld-State: Pushed <base-name>/<commit-id>`` commit to the
     weld, using that commit id (this is, of course, notionally an empty
     commit).
   * deletes the merging indicator and the saved commit message.

If something did go wrong, then ``weld finish`` just does that last item again
(which is why we need the merging indicator). ``weld abort`` deletes the
working branch, and then deletes the merging indicator and saved commit
message.

Tree
----
::

   $ cd fromble
   $ tree.py -fold .git -fold .weld
   fromble/
   ├─.git/...
   ├─.gitignore
   ├─.weld/...
   ├─124/
   │ ├─four/
   │ │ ├─Makefile
   │ │ ├─four-and-a-bit.c
   │ │ └─four.c
   │ ├─one/
   │ │ ├─Makefile
   │ │ └─one.c
   │ ├─three/
   │ │ ├─Makefile
   │ │ ├─three-and-a-bit.c
   │ │ └─three.c
   │ └─two/
   │   ├─Makefile
   │   └─two.c
   ├─one-goose/
   │ ├─Makefile
   │ └─one.c
   └─two-duck/
     ├─Makefile
     └─two.c

   $ tree.py -fold .git .weld
   .weld/
   ├─bases/
   │ ├─igniting_duck/
   │ │ ├─.git/...
   │ │ ├─one/
   │ │ │ ├─Makefile
   │ │ │ └─one.c
   │ │ └─two/
   │ │   ├─Makefile
   │ │   └─two.c
   │ └─project124/
   │   ├─.git/...
   │   ├─four/
   │   │ ├─Makefile
   │   │ ├─four-and-a-bit.c
   │   │ └─four.c
   │   ├─one/
   │   │ ├─Makefile
   │   │ └─one.c
   │   ├─three/
   │   │ ├─Makefile
   │   │ ├─three-and-a-bit.c
   │   │ └─three.c
   │   └─two/
   │     ├─Makefile
   │     └─two.c
   ├─counter
   └─welded.xml


.. vim: set filetype=rst tabstop=8 softtabstop=2 shiftwidth=2 expandtab:
