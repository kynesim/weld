"""
The weld database; contains a description of a weld.
"""

import utils
from xml.sax.saxutils import quoteattr

class Base:
    """
    Represents a base
    """
    
    # Name.
    name = None
    # URI
    uri = None

    # repos using this base: maps name -> Repo
    repos = { }

    def __init__(self):
        self.name = None
        self.uri = None
        self.repos = { }

    def __repr__(self):
        res = "<base name=%s uri=%s />\n"%(quoteattr(self.name), quoteattr(self.uri))
        for r in self.repos.itervalues():
            res += "  " + r.__repr__() + "\n"
        return res

class Repo:
    """
    Represents a repository
    """

    # Name
    name = None

    # Base - this is a Base object
    base = None

    # Branch
    branch = None

    # Tag
    tag = None
    
    # rev
    rev = None
    
    # Where to check out into.
    rel = None

    # The current revision in the weld.
    current = None
    
    def __init__(self):
        self.name = None
        self.base = None
        self.branch = None
        self.tag = None
        self.rev = None
        self.rel = None
        self.current = None

    
    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        res = "<repo name=%s base=%s"%(quoteattr(self.name), quoteattr(self.base.name))
        if (self.branch is not None):
            res = res + " branch=%s"%(quoteattr(self.branch))
        if (self.tag is not None):
            res = res + " tag=%s"%(quoteattr(self.tag))
        if (self.rev is not None):
            res = res + " rev=%s"%(quoteattr(self.rev))
        if (self.rel is not None):
            res =res + " rel=%s"%(quoteattr(self.rel))
        if (self.current is not None):
            res = res + " current=%s"%(quoteattr(self.current))
        res = res + "/>"
        return res



class Weld:
    # The name of this weld.
    name = None
    # Base directory for this weld (the directory which contains .git and .weld)
    base_dir = None

    # Origin for this weld.
    origin = None

    # Bases - maps a name to a Base
    bases = { }
    
    def __init__(self):
        self.name = "[anonymous]"
    
    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        res = "<weld name=%s>\n"%(quoteattr(self.name))
        if (self.origin is not None):
            res += "<origin uri=%s />\n"%(quoteattr(self.origin))
        for b in self.bases.itervalues():
            res += b.__repr__()
        res += "</weld>"
        return res
        

# End file.
