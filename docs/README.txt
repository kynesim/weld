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

 .welded/status.xml
   This is a file that describes what weld thinks the state
    of the world is, because it needs something to compare
    weld.xml to.


bases, repos and upstreams
==========================

 The origin is where this weld should pull from and push to. It is the 
  origin remote in the corresponding git directory.

 A base is a collection of repositories in weld. bases are rooted at a single URI
   (for the moment).

 A repo is a git repository. It is located relative to a base and checked out
  to some subdirectory in the weld.

 There are some design limitations here:

  - You can't rename directories from an upstream weld.
  - No repo can have more than one base.

weld.xml
========

 A typical weld.xml:

 <?xml version="1.0" ?>
 <weld name="frank">
   <origin uri="ssh://git@home.example.com/ribbit/fromble" />

   <base name="project124" uri="ssh://git@foo.example.com/my/base" />
   <base name="igniting_duck" uri="ssh://git@bar.example.com/wobble" />

   <repo name="muddle" base="project124" branch="herring" tag="frooble_1.0" rev="cd23824.." rel="muddle" />
   <repo name="foo" base="igniting_duck" checkout="frobble/woobit" />

 </weld>
 

 This file tells weld:

   * This weld is called frank - this name is used when upstreaming.
   * The origin for this weld is at ssh://git@home.example.com/ribbit/fromble.
   * This weld draws from two bases: project124 and igniting_duck
   * Check out the git repo at project124 into the local directory muddle, branch herring.
   * Check out the git repo at igniting_duck/frobble/woobit into the local directory.

Going behind weld's back
========================

 As with muddle, weld attempts to support you going behind its back. In 
particular, 


Using weld   
==========

 weld create weld.xml
  
   This command takes a weld.xml that you have written and creates a git 
    repository for it, including writing you a .git/info/sparse-checkout file.

 weld import

   This command imports any missing repos into the weld. If any branches have
    changed, 

 weld upstream <base>

   Here is where the magic happens. Weld collects all the diffs that might affect
  <base> and ports them (individually) upstream to that base. Weld adds a
  Welded-From: <name>/<commit-id> to each comment.

 weld sync <URI>

   Weld will check out the .weld from <URI> and synchronise with it -
this is largely a clone, but because weld will write a sparse-checkout file
you do not need to check out any parts of the repository which are not 
currently in the weld.


End file.


   
