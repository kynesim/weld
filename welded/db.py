"""
The weld database; contains a description of a weld.
"""

from xml.sax.saxutils import quoteattr
from functools import total_ordering

class Base:
    """
    Represents a base
    """
    
    # Name.
    name = None
    # URI
    uri = None

    # Branch
    branch = None

    # Tag
    tag = None
    
    # rev
    rev = None

    # seams using this base. Since seams can be anonymous, an array.
    seams = [ ]

    def __init__(self):
        self.name = None
        self.uri = None
        self.branch = None
        self.tag = None
        self.rev = None
        self.seams = [ ]

    def get_seams(self):
        return self.seams

    def __repr__(self):
        res = "<base name=%s uri=%s"%(quoteattr(self.name), quoteattr(self.uri))
        if (self.branch is not None):
            res = res + " branch=%s"%(quoteattr(self.branch))
        if (self.tag is not None):
            res = res + " tag=%s"%(quoteattr(self.tag))
        if (self.rev is not None):
            res = res + " rev=%s"%(quoteattr(self.rev))
        res = res + " />\n"
        for s in self.seams:
            res += "  " + s.__repr__() + "\n"
        return res

@total_ordering
class Seam:
    """
    Represents a seam
    """

    # Name
    name = None

    # Base - this is a Base object
    base = None

    # Source directory
    source = None

    # Destination
    dest = None

    def __init__(self):
        self.name = None
        self.base = None
        self.source = None
        self.dest = None

    def get_source(self):
        if (self.source is None):
            return "."
        else:
            return self.source

    def get_dest(self):
        if (self.dest is None):
            # XXX Is this sensible? Is "source=." really the same as not
            # XXX specifying source (I suspect that (a) yes and (b) yes,
            # XXX in which case we need to document it).
            return "."
        else:
            return self.dest

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        res = "<seam"
        if (self.name is not None):
            res += " name=%s"%(quoteattr(self.name))
        if (self.base is not None):
            res += " base=%s"%(quoteattr(self.base.name))
        if (self.source is not None):
            res += " source=%s"%(quoteattr(self.source))
        if (self.dest is not None):
            res += " dest=%s"%(quoteattr(self.dest))
        # XXX Surely we also need branch and/or other things as well?
        # XXX (just as in the XML file...)
        res = res + "/>"
        return res

    def __eq__(self, other):
        return repr(self) == repr(other)

    def __ne__(self, other):
        return repr(self) != repr(other)

    def __lt__(self, other):
        return repr(self) < repr(other)

    def __hash__(self):
        return hash(repr(self))

    def srcdest(self):
        res = ""
        if (self.source is not None):
            res = res + self.source
        res = res + ":"
        if (self.dest is not None):
            res = res + self.dest
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
    
    def seam_names(self):
        """
        Returns a hash table of seam name -> (something)
        """
        rv = { }
        for b in self.bases.values():
            for s in b.seams.keys():
                rv[s] = True
        return rv

    def base_names(self):
        return self.bases.keys()

    def set_dir(self, where):
        self.base_dir = where
    
    def query_base(self, n):
        return self.bases[n]

    def write(self, where_to):
        with open(where_to, "wb+") as f:
            f.write("<?xml version='1.0' ?>\n")
            f.write(self.__repr__())

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        res = "<weld name=%s>\n"%(quoteattr(self.name))
        if (self.origin is not None):
            res += "<origin uri=%s />\n"%(quoteattr(self.origin))
        for b in self.bases.itervalues():
            res += b.__repr__()
        res += "</weld>\n"
        return res
        

# End file.
