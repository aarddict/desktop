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
import cStringIO

class SimpleXMLParser:

    def __init__(self):
        pass

    def parseString(self, string):
        file = cStringIO.StringIO(string)
        self.parseFile(file)
        
    def parseFile(self, file):
        self.file = file
        self.EOF = False
        self.buffer = ""
        self.extendBuffer()
        
        while True:

            tagpos = self.scanTo("<")
            
            self.handleRawCharacterData(self.buffer[:tagpos])
            self.buffer = self.buffer[tagpos:]

            if self.EOF:
                break

            if not self.buffer:
                continue

            if self.buffer.startswith("<!--"):
                endpos = self.scanTo("-->")
                if self.buffer[endpos:endpos+3] != "-->":
                    sys.stderr.write("Comment too long: %s\n" % (repr(self.buffer)))
                self.buffer = self.buffer[endpos+3:]
                continue

            endpos = self.scanTo(">")
            
            if self.buffer[endpos] != ">":
                sys.stderr.write("Tag too long: %s\n" % (repr(self.buffer)))
                continue

            tag = self.buffer[1:endpos]
            if tag:
                tag = tag.replace("\n", " ")
                if tag[0] == '/':
                    tag = tag.replace(" ", "")
                    self.handleEndElement(tag[1:])
                elif tag[-1] == '/':
                    tag = tag.replace(" ", "")
                    self.handleStartElement(tag[:-1], {})
                    self.handleEndElement(tag[:-1])
                else:
                    tagElements = tag.split(" ", 1)
                    self.handleStartElement(tagElements[0], self.makeAttrDict(tag))

            self.buffer = self.buffer[endpos+1:]
            
    def scanTo(self, string):
        while not self.EOF:
            pos = self.buffer.find(string)
            if pos >= 0:
                return pos
            pos = len(self.buffer)
            if pos > 10000:
                return pos
            self.extendBuffer()
        return pos

    def extendBuffer(self):
        waslen = len(self.buffer)
        self.buffer = "".join([self.buffer, self.file.readline()])
        if waslen == len(self.buffer):
            self.EOF = True

    def makeAttrDict(self, s):
        attrDict = {}
        tokens = s.split(" ")

        # handle quoted strings containing spaces
        i = 0
        while i < len(tokens):
            if tokens[i] == " ":
                tokens.pop(i)
            elif (tokens[i].count('"') == 1) and (i+1 < len(tokens)):
                tokens[i] = tokens[i] + " " + tokens[i+1]
                tokens.pop(i+1)
            else:
                i = i + 1

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
        self.handleCharacterData(data)
        
    def handleCharacterData(self, data):

        sys.stderr.write("data: '%s'\n" % data)
    
if __name__ == '__main__':
    import sys

    p = SimpleXMLParser() 
    s = '''
    <h1
    >This is a &quot;title&quot;</h1><br>\n<a href="there"
    class=x>this<br/><i>and</i>  <!---ignore me <really> -->
    <b>that</i><span selected></b></a><minor /><a href="big daddy">yowza</a>
    '''
    print s
    
    p.parseString(s)

    print "Done."





