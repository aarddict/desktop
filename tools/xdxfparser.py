#!/usr/bin/python

# Process XDXF files
#
# Jeremy Mortis (mortis@ucalgary.ca)

import os
import sys
import re

from simplexmlparser import SimpleXMLParser

from aarddict.article import Article
from aarddict.article import Tag
import aarddict.pyuca

class XDXFParser(SimpleXMLParser):

    def __init__(self, collator, metadata, consumer):
        self.databucket = ""
        self.collator = collator
        self.metadata = metadata
        self.consumer = consumer
        self.tagstack = []

    def handleStartElement(self, tag, attrs):

        if tag == "xdxf":
            if attrs.get("lang_from"):
                self.metadata["index_language"] = attrs.get("lang_from")
            if attrs.get("lang_to"):
                self.metadata["article_language"] = attrs.get("lang_to")

        self.tagstack.append([tag, ""])

    def handleEndElement(self, tag):

        entry = self.tagstack.pop()

        if entry[0] != tag:
            sys.stderr.write("mismatched tag: " + repr(entry) + "\n")
            return

        if tag == "full_name":
            self.metadata["title"] = self.clean(entry[1], oneline=True)

        if tag == "description":
            self.metadata["description"] = self.clean(entry[1])
        
        if tag == "k":
            self.k = self.clean(entry[1], oneline=True)

        if tag == "ar":
            self.ar = self.clean(entry[1])
            self.consumer(self.k, self.ar)
            
    def handleCharacterData(self, data):

        if not self.tagstack:
            if data.strip():
                sys.stderr.write("Orphan data: " + repr(data) + "\n")
            return
            
        entry = self.tagstack.pop()
        entry[1] = entry[1] + data
        self.tagstack.append(entry)

    def clean(self, s, oneline = False):
        s = re.compile(r"^\s*", re.MULTILINE).sub("", s)
        s = re.compile(r"\s*$", re.MULTILINE).sub("", s)
        s = re.compile(r"\n\n*").sub(r"\n",s)
        if oneline:
            s = s.replace("\n", "")
            
        return s


def article_printer(title, article):
    print "=================================="
    print title
    print "=================================="
    print article

    
if __name__ == '__main__':

    collator = aarddict.pyuca.Collator("aarddict/allkeys.txt", strength = 1)
   
    string = """
<xdxf lang_from="FRE" lang_to="ENG" format="visual">
<full_name>French-English dictionary</full_name>
<description>Copyright: Converted under GNU Public License; Version: 1.1</description>
<ar><k>Maison</k>
House</ar>
<ar><k>Voiture</k>
Car</ar>
</xdxf>
"""

    metadata = {}
    
    parser = XDXFParser(collator, metadata, article_printer)
    parser.parseString(string)

    print metadata
    
    print "Done."


