"""
Syntax: weld <options> [command]

Do

$ weld help

For more detail.
"""
# ^^ Doing it this way means we don't need to construct
# the help message unless you actually ask for it
# (=> faster startup)

import errno
import os
import subprocess

from optparse import OptionParser

import welded.utils as utils
import utils
import db
import parser
import init
import pull
import push
import layout
import ops
import query
import git
import status

main_parser = OptionParser(usage = __doc__)
main_parser.add_option("-v", "--verbose", action="store_true",
                       dest="verbose", default = False,
                       help="report extra information, if appropriate")
main_parser.add_option("-t", "--tuple", action="store_true",
                       dest="as_tuple", default = False,
                       help="also report information as a tuple, if appropriate")

# CommandName -> CommandClass
g_command_dict = { }

# Main command names (we have no aliases yet, but one day .. )
g_command_names = [ ]

def command(command_name):
    """
    Some of Tony's magic; a decorator to register commands
    """
    if (command_name in g_command_dict):
        raise utils.Bug("Command '%s' defined twice."%command_name)
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
        if (obj.needs_weld()):
            try:
                obj.set_weld_dir(utils.find_weld_dir(os.getcwd()))
            except Exception as e:
                raise utils.GiveUp('Cannot find .weld directory\n%s: %s'%(e.__class__.__name__, e))
        return obj.go(opts, args[1:])
    else:
        raise utils.GiveUp('Unrecognised command %r'%cmd)


class Command(object):
    """
    Abstract base class for commands, with utilities for the wise.
    """
    cmd_name = "<PleaseRegisterYourCommand>"

    def set_weld_dir(self, w):
        self.weld_dir = w
        p = parser.Parser()
        spec_name = layout.spec_file(w)
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
                raise utils.GiveUp("Base '%s' is unknown"%(a))
        return bases.keys()
    

@command('init')
class Init(Command):
    """
    Initialise a new weld in the current directory using the 
    given xml description
    """

    def syntax(self):
        return "init <weld-xml-file>"

    def go(self, opts, args):
        if (len(args) != 1):
            raise utils.GiveUp("Missing <weld-xml-file>")
        
        p = parser.Parser()
        weld = p.parse(args[0])
        init.init_weld(weld, os.getcwd())

    def needs_weld(self):
        # init doesn't need a weld.
        return False

@command('pull')
class Pull(Command):
    """
    Pull the named base(s).

    If more than one base name is given, pull each base in turn.

    If _all is given, pull all bases.
    """
    def go(self,opts,args):
        to_pull = self.base_set_from_args(args)
        if opts.verbose:
            print("Pulling bases: %s"%(to_pull))
        for p in to_pull:
            rv = pull.pull_base(self.spec, p)
            if rv != 0:
                return rv

@command('push')
class Push(Command):
    """
    Push the named base(s).

    If more than one base name is given, push each base in turn.

    If _all is given, push all bases.
    """
    def go(self,opts,args):
        to_push = self.base_set_from_args(args)
        if opts.verbose:
            print("Pushing bases: %s"%(to_push))
        for p in to_push:
            rv = push.push_base(self.spec, p, verbose=opts.verbose)
            if rv != 0:
                return rv

@command('help')
class Help(Command):
    """
    Give help on weld options and commands
    """
    def go(self, opts, args):
        print("Weld: \n")
        print(" --verbose             Be verbose \n")
        print("\nWeld commands: \n ")
        for c in g_command_names:
            obj = g_command_dict[c]()
            print("%s\n%s\n"%(obj.syntax(), obj.help()))
        print("\n")

    def needs_weld(self):
        # help doesn't need a weld
        return False

@command('finish')
class Finish(Command):
    """
    Finish a pending operation
    """
    def go(self, opts, args):
        spec = self.spec
        ops.do_finish(spec)

@command('abort')
class Abort(Command):
    """
    Abort a pending operation
    """
    def go(self, opts, args):
        spec = self.spec
        ops.do_abort(spec)

@command('query')
class Query(Command):
    """
    Query the database

      weld query base <base_name>    Query the current state of <base_name>
      weld query bases               List bases
      weld query seam-changes <base_name>  Query the seam changes for <base_name>
    """
    def go(self,opts,args):
        if (len(args) < 1):
            raise utils.GiveUp("query requires a subcommand")
        cmd = args[0]
        if (cmd == "base"):
            if (len(args) < 2):
                raise utils.GiveUp("query base requires a base name")
            query.query_base(self.spec, args[1])
        elif (cmd == "bases"):
            query.query_bases(self.spec)
        elif (cmd == "seam-changes"):
            if (len(args) != 2):
                raise utils.GiveUp("query seam-changes requires a base name")
            query.query_seam_changes(self.spec, args[1])
        else:
            raise utils.GiveUp("No query subcommand '%s'"%cmd)

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
            raise utils.Giveup('Too many arguments - "weld status [<remote-name>]"')

        verbose = opts.verbose
        output_tuple = opts.as_tuple
        where = self.spec.base_dir

        if args:
            remote_name = args[0]
        else:
            remote_name = None

        in_weld_pull, in_weld_push, should_git_pull, should_git_push = \
                status.get_status(where, remote_name=remote_name, verbose=verbose)

        if verbose:
            print

        if in_weld_pull:
            print 'Part way through "weld pull"'
            print 'Fix any problems and then "weld finish", or give up using "weld abort"'
        elif verbose:
            print 'Not part way through a "weld pull"'

        if in_weld_push:
            print 'Part way through "weld push"'
            print 'Fix any problems and then "weld continue", or give up using "weld abort"'
        elif verbose:
            print 'Not part way through a "weld push"'

        if should_git_pull: print 'You should do "git pull"'
        if should_git_push: print 'You should do "git push"'

        if verbose:
            if should_git_pull is None and should_git_push is None:
                print 'No need to "git pull" or "git push", there is no remote'
            elif not should_git_pull and not should_git_push:
                print 'No need to "git pull" or "git push"'

        if output_tuple:
            print in_weld_pull, in_weld_push, should_git_pull, should_git_push

# End file.
