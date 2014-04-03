"""
parser.py - constructs a db.Weld from an XML file.
"""

import utils
import db
import xml.dom.minidom

class Parser:
    def __init__(self):
        self.weld = None

    def parse(self, name):
        data = open(name)
        dom = xml.dom.minidom.parse(data)
        return self.parse_dom(dom)
    
    def parse_dom(self, dom):
        return self.handle_weld(dom)
    
    def handle_weld(self, dom):
        weld = db.Weld()
        node = dom.documentElement
        if (node.hasAttribute("name")):
            weld.name = node.getAttribute("name")
        else:
            raise GiveUp("Weld has no name")

        origins = dom.getElementsByTagName("origin")
        if (len(origins) > 0):
            weld.origin = origins[0].attributes["uri"]
        bases = dom.getElementsByTagName("base")
        repos = dom.getElementsByTagName("repo")
        for b in bases:
            base_obj = self.handle_base(weld, b)
        for r in repos:
            repo_obj = self.handle_repo(weld, r)
        return weld

    def handle_base(self, weld, node):
        b = db.Base()
        if (not node.hasAttribute("name")):
            raise utils.GiveUp("Base without a name")
        b.name = node.getAttribute("name")
        b.uri = node.getAttribute("uri")
        weld.bases[b.name] = b

    def handle_repo(self, weld, node):
        r = db.Repo()
        if (not node.hasAttribute("name")):
            raise utils.GiveUp("Repo without a name")
        r.name = node.getAttribute("name")
        if (not node.hasAttribute("base")):
            raise utils.GiveUp("Repo %s has no base."%r.name)
        base_name = node.getAttribute("base")
        if (not (base_name in weld.bases)):
            raise utils.GiveUp("Repo %s has base %s, which is not defined."%(r.name, base_name))
        r.base =  weld.bases[base_name];
        if (node.hasAttribute("branch")):
            r.branch = node.getAttribute("branch")
        if (node.hasAttribute("tag")):
            r.tag = node.getAttribute("tag")
        if (node.hasAttribute("rev")):
            r.rev = node.getAttribute("rev")
        if (node.hasAttribute("rel")):
            r.rel = node.getAttribute("rel")
        if (node.hasAttribute("current")):
            r.current = node.getAttribute("current")
        r.base.repos[r.name] = r



# End file.

