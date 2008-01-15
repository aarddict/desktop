#!/usr/bin/python
"""
This file is part of AardDict (http://code.google.com/p/aarddict) - 
a dictionary for Nokia Internet Tablets. 

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
import shlex
import re

class SimpleXMLParser:

    def __init__(self):
        self.StartElementHandler = self.handleStartElement
        self.EndElementHandler = self.handleEndElement
        self.CharacterDataHandler = self.handleCharacterData
        self.file = None

    def parseString(self, string):
        self.file = None
        self.EOF = True
        self.openTag = False
        self.buffer = string
        self._parse()

    def parseFile(self, file):
        self.file = file
        self.EOF = False
        self.openTag = False
        self.buffer = ""
        self.extendBuffer()
        self._parse()
    
    def _parse(self):

        while True:
            if self.EOF:
                if not self.buffer:
                    break
                if self.openTag:
                    sys.stderr.write("incomplete XML tag: %s\n" % self.buffer)
                    break

            pos = self.buffer.find("<")
            if pos == -1:
                self.handleRawCharacterData(self.buffer)
                self.buffer = ""
                self.extendBuffer()
                continue

            if pos > 0:
                self.handleRawCharacterData(self.buffer[:pos])
                self.buffer = self.buffer[pos:]

            pos = self.buffer.find(">")
            if pos == -1:
                self.openTag = True
                self.extendBuffer()
                continue
            
            tag = self.buffer[1:pos]
            if tag:
                if tag[0] == '/':
                    self.EndElementHandler(tag[1:])
                elif tag[-1] == '/':
                    tag = tag.replace(" ", "")
                    self.StartElementHandler(tag[:-1], {})
                    self.EndElementHandler(tag[:-1])
                else:
                    tagElements = tag.split(" ", 1)
                    self.StartElementHandler(tagElements[0], self.makeAttrDict(tag))

            self.buffer = self.buffer[pos+1:]

    def extendBuffer(self):
        if self.EOF:
            return
        if not self.file:
            self.EOF = True
            return
        newData = self.file.read(1024)
        if not newData:
            self.EOF = True
        else:
            self.buffer = self.buffer + newData
        
                
    def makeAttrDict(self, s):
        attrDict = {}
        try:
            tokens = shlex.split(s)
        except:
            return {}
        for t in tokens[1:]:
            sep = t.find("=")
            if sep == -1:
                name = t
                value = ""
            else:
                name = t[:sep]
                value = t[sep+1:]
            attrDict[name] = value
        return attrDict
    
    def handleStartElement(self, tag, attrsList):
            
        sys.stderr.write("XML start tag: <%s> %s\n" % (tag, str(attrsList)))

    def handleEndElement(self, tag):

        sys.stderr.write("XML end tag: </%s>\n" % tag)

    def handleRawCharacterData(self, data):
        data = data.replace("&lt;", "<")
        data = data.replace("&gt;", ">")
        data = data.replace("&quot;", '"')
        data = data.replace("&amp;", '&')
        self.CharacterDataHandler(data)
        
    def handleCharacterData(self, data):

        sys.stderr.write("data: '%s'\n" % data)
    
if __name__ == '__main__':
    import sys

    p = SimpleXMLParser() 
    s = '<h1>This is a &quot;title&quot;</h1><br>\n<a href="there" class=x>this<br/><i>and</i> <b>that</i><span selected></b></a><minor /><a href="big daddy">yowza</a>'
    print s
    
    p.parseString(s)

    print "Done."





