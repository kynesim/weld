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

main_parser = OptionParser(usage = __doc__)
main_parser.add_option("--verbose", action="store_true", 
                       dest = "verbose", default = False)

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
            raise utils.Bug("No weld detection yet!")
        return obj.go(opts, args[1:])


class Command(object):
    """
    Abstract base class for commands, with utilities for the wise.
    """
    cmd_name = "<PleaseRegisterYourCommand>"

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


@command('init')
class Init(Command):
    """
    Initialise a new weld in the current directory using the 
    given xml description
    """

    def syntax(self):
        return "init [weld.xml]"

    def go(self, opts, args):
        if (len(args) != 1):
            raise utils.GiveUp("Missing weld.xml")
        
        p = parser.Parser()
        weld = p.parse(args[0])
        print "%s\n"%(weld.__repr__())

    def needs_weld(self):
        # init doesn't need a weld.
        return False


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

# End file.
