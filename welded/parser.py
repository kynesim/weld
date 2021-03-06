"""
parser.py - constructs a Weld from an XML file.
"""

import xml.dom.minidom

from welded.db import Weld, Base, Seam
from welded.utils import GiveUp

class Parser:
    def __init__(self):
        self.weld = None

    def parse(self, name):
        dom = xml.dom.minidom.parse(name)
        return self.parse_dom(dom)
    
    def parse_dom(self, dom):
        return self.handle_weld(dom)
    
    def handle_weld(self, dom):
        weld = Weld()
        node = dom.documentElement
        if (node.hasAttribute("name")):
            weld.name = node.getAttribute("name")
        else:
            raise GiveUp("Weld has no name")

        origins = dom.getElementsByTagName("origin")
        if (len(origins) > 0):
            # XXX Should the URI be optional?
            # XXX Should we allow other attributes?
            weld.origin = origins[0].getAttribute("uri")
        bases = dom.getElementsByTagName("base")
        seams = dom.getElementsByTagName("seam")
        for b in bases:
            self.handle_base(weld, b)
        for s in seams:
            self.handle_seam(weld, s)
        return weld

    def handle_base(self, weld, node):
        b = Base()
        if (not node.hasAttribute("name")):
            raise GiveUp("Base without a name")
        b.name = node.getAttribute("name")
        b.uri = node.getAttribute("uri")
        if (node.hasAttribute("branch")):
            b.branch = node.getAttribute("branch")
        if (node.hasAttribute("tag")):
            b.tag = node.getAttribute("tag")
        if (node.hasAttribute("rev")):
            b.rev = node.getAttribute("rev")

        weld.bases[b.name] = b

    def handle_seam(self, weld, node):
        s = Seam()
        if (node.hasAttribute("name")):
            s.name = node.getAttribute("name")
        if (not node.hasAttribute("base")):
            raise GiveUp("Seam %s has no base."%s.name)
        base_name = node.getAttribute("base")
        if (not (base_name in weld.bases)):
            raise GiveUp("Seam %s has base %s, which is not defined."%(s.name, base_name))
        s.base =  weld.bases[base_name]
        if (node.hasAttribute("source")): 
            s.source= node.getAttribute("source")
        if (node.hasAttribute("dest")): 
            s.dest = node.getAttribute("dest")
        if (node.hasAttribute("current")):
            s.current = node.getAttribute("current")
        s.base.seams.append(s)

# End file.
