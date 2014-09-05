"""
Syntax: weld <options> [command]

Do

$ weld help

For more detail.
"""
# ^^ Doing it this way means we don't need to construct
# the help message unless you actually ask for it
# (=> faster startup)

import os

from optparse import OptionParser

import welded.init
import welded.parser
import welded.query as query
import welded.status
import welded.ops as ops

from welded.layout import spec_file
from welded.push_step import push_step
from welded.pull_step import pull_step
from welded.utils import Bug, GiveUp, find_weld_dir

main_parser = OptionParser(usage = __doc__)
main_parser.add_option("-v", "--verbose", action="store_true",
                       dest="verbose", default = False,
                       help="report extra information, if appropriate")
main_parser.add_option("-t", "--tuple", action="store_true",
                       dest="as_tuple", default = False,
                       help="also report information as a tuple, if appropriate")
main_parser.add_option("-e", "--edit", action="store_true",
                       dest="edit_commit_file", default = False,
                       help='edit the "weld push" commit file for each base before using it')
main_parser.add_option("--commit-style", action="store",
                       dest="commit_style", default = None,
                       help=( "Indicate the desired commit style for this operation:\n"
                              "  oneline       (default) git log --oneline \n"
                              "  long          The whatchanged summary of changes\n"
                              "  summary       The summary list of changes (default)\n") )
main_parser.add_option("-i", "--ignore-history", action="store_true",
                       dest="ignore_history", default = False,
                       help='Ignore all history when pulling or pushing: DANGEROUS!')
main_parser.add_option('-f', '--finish-stepping', action="store_true",
                       dest="finish_stepping", default = False,
                       help="When in a stepped pull or push, squash the rest of the pull " + 
                       "or push and get to the end of the change list.")
main_parser.add_option('--single-commit-stepping', action="store_true",
                       dest="single_commit_stepping", default = False,
                       help="When in a stepped pull or push, just replicate commit messages for the rest of the pull/push")

# CommandName -> CommandClass
g_command_dict = { }

# Main command names (we have no aliases yet, but one day .. )
g_command_names = [ ]

def command(command_name):
    """
    Some of Tony's magic; a decorator to register commands
    """
    if (command_name in g_command_dict):
        raise Bug("Command '%s' defined twice."%command_name)
    def remember(klass):
        g_command_dict[command_name] = klass
        klass.cmd_name = command_name
        return klass

    g_command_names.append(command_name)
    return remember

def go(args):
    """
    Main entry point
    """
    (opts, args) = main_parser.parse_args()

    # Find a command.
    if (len(args) < 1):
        main_parser.print_usage()
        return 1

    cmd = args[0]
    if (cmd in g_command_dict):
        obj = g_command_dict[cmd]()
    else:
        obj = g_command_dict['do']()
        # .. so that there is something here to lop off in a few
        # lines.
        args.insert(0, 'do')

    if (obj.needs_weld()):
        weld_dir = find_weld_dir(os.getcwd())
        obj.set_weld_dir(weld_dir)
        ops.ensure_state_dir(weld_dir)

    return obj.go(opts, args[1:])


class Command(object):
    cmd_name = "<PleaseRegisterYourCommand>"
    """
    Abstract base class for commands, with utilities for the wise.
    """
    cmd_name = "<PleaseRegisterYourCommand>"

    def set_weld_dir(self, w):
        self.weld_dir = w
        p = welded.parser.Parser()
        spec_name = spec_file(w)
        self.spec = p.parse(spec_name)
        self.spec.set_dir(self.weld_dir)

    def syntax(self):
        """ 
        Short-mode syntax for this command
        """
        return self.cmd_name

    def help(self):
        """ 
         Long-mode help for this command.
         """
        return self.__class__.__doc__

    def needs_weld(self):
        # Most commands need a weld.
        return True

    def base_set_from_args(self, args):
        bases = { } 
        for a in args:
            if (a=="_all"):
                for x in self.spec.base_names():
                    bases[x] = True
            elif (a in self.spec.bases):
                bases[a] = True
            else:
                raise GiveUp("Base '%s' is unknown"%(a))
        return bases.keys()
    

@command('look')
class Look(Command):
    """Report the available verbs. This is typically used during an
       operation to report the possible options for continuing the 
       operation after manual intervention.

       One day, it will also play tetris
    """
    
    def syntax(self):
        return "look"

    def go(self, opts, args):
        l = ops.list_verbs(self.spec)
        if (len(l) > 0):
            for x in l:
                print "%s"%x
        else:
            print "\nNo verbs available."

   
@command('init')
class Init(Command):
    """Initialise a new weld in the current directory

    The directory should initially be empty. So, for instance, given a weld
    XML file called "fromble.xml":

        $ mkdir fromble
        $ cd fromble
        $ weld init ../fromble.xml

    The command:

    1. Parses the XML file to determine the description of the weld
    2. Writes out its understanding of that XML to ".weld/welded.xml"
       (the order of entities may change, and any XML comments will be lost)
    3. Does a "git init" in the current directory.
    4. Writes a ".gitignore" file to ignore various transient files that may
       appear in the ".weld" directory.
    5. Commits the ".gitignore" and ".weld/welded.xml" files to git, with the
       commit message::

          X-Weld-State: Init

          Weld initialisation
    """

    def syntax(self):
        return "init <weld-xml-file>"

    def go(self, opts, args):
        if (len(args) != 1):
            raise GiveUp("Missing <weld-xml-file>")
        
        p = welded.parser.Parser()
        weld = p.parse(args[0])
        welded.init.init_weld(weld, os.getcwd())

    def needs_weld(self):
        # init doesn't need a weld.
        return False

@command('pull')
class Pull(Command):
    """
    Pull the named base(s).

    If more than one base name is given, pull each base in turn.

    If _all is given, pull all bases.

    If -i (or --ignore-history) is given, we ignore all previous history -
    this is useful if you are messing with your welded.xml

    If pulling a base fails (typically because human intervention is needed
    to sort out a merge), then either use "weld abort" to give up on the
    operation, or fix the merge and use "weld finish" to finish the operation.

    If you specify multiple bases to "weld pull", and have to "weld finish" or
    "weld abort" one of them, the "weld pull" will not continue on to the next
    base; you will have to reissue the command again.
    """
    def go(self,opts,args):
        to_pull = self.base_set_from_args(args)
        if len(to_pull) == 0:
            print 'You must name a base to pull'
            return 1
        if opts.verbose:
            print "Pulling bases: %s"%(', '.join(to_pull))
        for p in to_pull:
            opts.finish_stepping = True
            rv = pull_step(self.spec, base_name, opts)
            if rv != 0:
                return rv

@command('pull-step')
class PullStep(Command):
    """
    Pull the named base a step at a time.
    
    A pullstep is exactly like a pull (and takes the same options)
    except that the individual commits from the base are merged into
    the weld.
    """
    def go(self, opts, args):
        to_pull = self.base_set_from_args(args)
        if len(to_pull) == 0:
            print "You must name a base to pull"
            return 1
        if opts.verbose:
            print 'Pull-step - bases are: %s'%(', '.join(to_pull))
        for base_name in to_pull:
            rv = pull_step(self.spec, base_name, opts)
            if (rv != 0):
                return rv

@command('push-step')
class PushStep(Command):
    """
    Push the named base(s) a step at a time.

    If more than one base name is given, push each base in turn.
    
    If _all is given, push all bases (one at a time)

    A pushstep is exactly like a push (and takes the same options), 
    except that each source commit is replicated to the base.

    If you specify --edit (-e) then you will be given the opportunity
    to approve each commit before it happens (you will need to issue
    "weld finish" or "weld abort").

    """
    def go(self, opts, args):
        to_push = self.base_set_from_args(args)
        if len(to_push) == 0:
            print 'You must name a base to push'
            return 1
        if opts.verbose:
            print 'Push-step - bases are: %s'%(', '.join(to_push))
        for base_name in to_push:
            rv = push_step(self.spec, base_name,
                           opts)
            if rv != 0:
                return rv

@command('push')
class Push(Command):
    """
    Push the named base(s).

    If more than one base name is given, push each base in turn.

    If _all is given, push all bases.

    If you specify --edit (-e) then you will be given the opportunity to
    edit the commit file for each base. The editor to use is $GIT_EDITOR
    (if defined), else $VISUAL (if defined), else $EDITOR (if defined),
    and otherwise 'vi'.

    If you specify --long-commit (-l) then the (squashed) commit to the
    base will have a long commit message, otherwise a summary of changes
    will be used as the commitlog.

    If -i (or --ignore-history) is given, we ignore all previous history -
    this is useful if you are messing with your welded.xml

    If pushing a base fails (typically because human intervention is needed
    to sort out a merge), then either use "weld abort" to give up on the
    operation, or fix the merge and use "weld finish" to continue with
    any remaining patches.

    If you specify multiple bases to "weld push", and have to "weld finish"
    or "weld abort" one of them, the "weld push" will not continue on to the
    next base; you will have to reissue the command again.
    """
    def go(self,opts,args):
        to_push = self.base_set_from_args(args)
        if len(to_push) == 0:
            print 'You must name a base to push'
            return 1
        if opts.verbose:
            print "Pushing bases: %s"%(', '.join(to_push))
        for base_name in to_push:
            opts.finish_stepping = True
            rv = push_step(self.spec, base_name, opts)
            if rv != 0:
                return rv

@command('help')
class Help(Command):
    """
    Give help on weld options and commands
    """
    def go(self, opts, args):
        print("Weld: \n")
        print main_parser.print_help()
        print("\nWeld commands: \n ")
        for c in g_command_names:
            obj = g_command_dict[c]()
            print("%s\n%s\n"%(obj.syntax(), obj.help()))
        print("\n")

    def needs_weld(self):
        # help doesn't need a weld
        return False

@command('do')
class Do(Command):
    """
    Performs a verb during a command that needed user intervention.

    Get a list with "weld look"

    Remember that if you had to do "weld finish" on a "weld push", then
    you may have updated the remote base repository in a way that is not
    consistent with the equivalent source code in the main weld. As such,
    you may need to do "weld pull" of the base.
    """
    def go(self,opts,args):
        if (len(args)  < 1):
            raise GiveUp("No verb supplied to 'do'")
        ops.do(self.spec, args[0], opts = opts, do_next_verbs = True)

@command('finish')
class Finish(Command):
    """
    Finish a "weld pull" or a "weld pull" that needed user intervetion.

    """
    def go(self, opts, args):
        ops.do(self.spec, 'finish', opts, do_next_verbs = True)

@command('abort')
class Abort(Command):
    """
    Abort a "weld pull" or "weld push" that needed user intervention
    """
    def go(self, opts, args):
        ops.do(self.spec, 'abort', opts, do_next_verbs = True)

@command('query')
class Query(Command):
    """
    Query the database

      weld query base <base_name>

        Query the current state of <base_name>

      weld query bases

        List the known bases

      weld query seam-changes <base_name>

        Query the seam changes for <base_name>

      weld query match <base_name>

        Query the last "common point" between the weld and this branch (the
        last shared "Merge" or "Push" event)

      weld query coverage
    
        Print out a list of which directories in the current weld are covered
        by seams, and which directories correspond to which seam.
        Files and directories which start with a dot are ignored.

    """
    def go(self,opts,args):
        if len(args) < 1:
            raise GiveUp("query requires a subcommand")
        cmd = args[0]
        if cmd == "base":
            if len(args) < 2:
                raise GiveUp("query base requires a base name")
            query.query_base(self.spec, args[1])
        elif cmd == "bases":
            query.query_bases(self.spec)
        elif cmd == "seam-changes":
            if len(args) != 2:
                raise GiveUp("query seam-changes requires a base name")
            query.query_seam_changes(self.spec, args[1])
        elif cmd == "match":
            if len(args) != 2:
                raise GiveUp("query match requires a base name")
            query.query_match(self.spec, args[1])
        elif cmd == "coverage":
            if len(args) != 1:
                raise GiveUp("query coverage requires no arguments")
            where = self.spec.base_dir
            (covers, uncovered) = query.query_coverage(self.spec, where)
            for (d, s) in covers:
                print("%s -> %s"%(d,s.name))
            print("\nUncovered:\n")
            for u in uncovered:
                print(u)
            print("\n")
        else:
            raise GiveUp("No query subcommand '%s'"%cmd)

@command('debug')
class Debug(Command):
    """
    A debugging aid. There are various subcommands:

    debug state        - Print out the contents of the persistent state
    debug log style cid1 cid2  - Print a summary log for cid, to check whatchanged.
    """
    def go(self, opts, args):
        if (len(args) < 1):
            raise GiveUp('Too few arguments - "weld debug <verb>"')
        verbose = opts.verbose
        cmd = args[0]
        if cmd == "state":
            st = ops.read_state_data(self.spec)
            print "Saved state was: \n"
            for k in st:
                print "%s = %s"%(k, st[k])
        elif cmd == "log":
            if (len(args) < 4):
                raise GiveUp('too few arguments - "log <style> <cid1> <cid2>"')
            some_things = ops.log_changes(self.spec.base_dir, args[2], args[3], None,
                                          style = args[1])
            for x in some_things:
                print "THING>%s"%x
        else:
            raise GiveUp("Invalid debug command '%s'"%cmd)
    

@command('status')
class Status(Command):
    """
    Report on the weld status.

      weld status [<remote-name>]

    If we are part-way through a "weld pull" or "weld push", then say so.

    Otherwise, report on whether we should do a "git pull" or "git push" of
    our weld. This is intended to be useful before doing a "weld pull" or
    "weld push" of our bases. Note that it queries the remote to determine
    the HEAD of the branch on the remote.

    If <remote-name> is not given, "origin" is assumed.

    Only the current branch is considered.

    If you specify --verbose (-v) then an explanation of why "git pull" or "git
    push" are/are not needed will be given.

    If you specify --tuple (-t), then an additional last line will be output,
    of the form:

        <in-weld-pull> <in-weld-push> <should-pull> <should-push>

    where each term is either True or False, or None (undecidable) - if an
    early term is True, later terms may be None because we either haven't
    checked, or because (in the case of "git push") it can actually be
    undecidable until a "git pull" has been done.
    """
    def go(self, opts, args):
        if len(args) > 1:
            raise GiveUp('Too many arguments - "weld status [<remote-name>]"')

        verbose = opts.verbose
        output_tuple = opts.as_tuple
        where = self.spec.base_dir

        if args:
            remote_name = args[0]
        else:
            remote_name = None

            in_op, should_git_pull, should_git_push = \
                welded.status.get_status_2(where, remote_name=remote_name,
                                           verbose=verbose)

        if in_op:
            print 'Part way through a weld command - %s'%in_op
            print 'Fix any problems and then "weld finish", or give up using "weld abort"'
        elif verbose:
            print 'Not part way through a "weld pull"'

        if should_git_pull: print 'You should do "git pull"'
        if should_git_push: print 'You should do "git push"'

        if verbose:
            if should_git_pull is None and should_git_push is None:
                print 'No need to "git pull" or "git push", there is no remote'
            elif not should_git_pull and not should_git_push:
                print 'No need to "git pull" or "git push"'

        if output_tuple:
            print in_op, should_git_pull, should_git_push

# End file.
