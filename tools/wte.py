#!/usr/bin/python
# coding: utf-8
"""
This script extracts template pages from a Wiki xml dump and stores them in a
shelve object (persisted to the output file specified). This enables template processing
during actual Wiki conversion. Template pages are pages with names in the template namespace. 
Template namespaces are different in different languages. Language is specified as input 
parameter with two-letter language code and defaults to "en"

This file is part of Aarddict Dictionary Viewer
(http://code.google.com/p/aarddict)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2008  Jeremy Mortis and Igor Tkach
"""

import sys
import shelve
import optparse
import os
import re
from simplexmlparser import SimpleXMLParser
from simplexmlparser import unescape

class TemplateParser(SimpleXMLParser):

    def __init__(self):
        SimpleXMLParser.__init__(self)
        self.tagstack = []
        self.title = ""
        self.text = ""
        self.StartElementHandler = self.handleStartElement
        self.EndElementHandler = self.handleEndElement
        self.CharacterDataHandler = self.handleCharacterData
        self.prefixMap = {"en":"Template:", "fr":"Modèle", "ru":"Шаблон:"}
        self.pageCount = 0

    def handleStartElement(self, tag, attrs):
        self.tagstack.append([tag, []])


    def handleEndElement(self, tag):

        if not self.tagstack:
            return
        
        entry = self.tagstack.pop()
        
        if entry[0] != tag:
            sys.stderr.write("Mismatched mediawiki tag: %s in %s at %s\n" % (repr(tag), repr(self.title), repr(entry)))
            return

        entrytext = "".join(entry[1])
        
        if tag == "title":
            self.title = self.clean(entrytext, oneline=True)
            self.title = self.title.replace("_", " ")
        
        elif tag == "text":
            self.text = entrytext
                        
        elif tag == "page":

            self.pageCount += 1
            if self.pageCount % 100 == 0:
                sys.stderr.write("\r%i / %i" % (self.pageCount, len(self.templateDb)))
                
            titleTokens = self.title.split(":", 1)

            if len(titleTokens) == 1:
                return
            
            if titleTokens[0] != self.prefixMap[self.language]:
                return
            
            #sys.stderr.write("%s\n" % self.title)

            self.text = unescape(self.text)
            self.text = re.compile(r"<noinclude>.*?</noinclude>", re.DOTALL).sub("", self.text)
            self.templateDb[titleTokens[1]] = self.text

            self.text = ""
            return
            
    def handleCharacterData(self, data):

        if not self.tagstack:
            if data.strip():
                sys.stderr.write("orphan data: '%s'\n" % data)
            return
        self.tagstack[-1][1].append(data)

    def handleCleanup(self):
        pass

    def clean(self, s, oneline = False):
        if oneline:
            s = s.replace("\n", " ")
        return s.strip()

#__main__
usage = "usage: %prog [options] "
parser = optparse.OptionParser(version="%prog 1.0", usage=usage)

parser.add_option(
    '-o', '--output-file',
    help='Output file'
    )
parser.add_option(
    '-i', '--input-file',
    help='Input file'
    )
parser.add_option(
    '-l', '--lang',
    help='Language',
    default = 'en'
    )

options, args = parser.parse_args()

if options.input_file:
    inputFile = open(options.input_file, "rb", 4096)
else:
    inputFile = sys.stdin

if not options.output_file:
    parser.print_help()
    sys.exit()
    
p = TemplateParser()

p.language = options.lang
p.templateDb = shelve.open(options.output_file, "n")

p.parseFile(inputFile)

sys.stderr.write("\r%i / %i\n" % (p.pageCount, len(p.templateDb)))

p.templateDb.close()
    
sys.stderr.write("Done.\n")




