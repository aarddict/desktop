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
        self.bufpos = 0
        self.tagpos = 0
        
        while True:

            self.tagpos = self.scanTo("<") 
            
            if self.tagpos > self.bufpos:
                self.handleRawCharacterData(self.buffer[self.bufpos:self.tagpos])
                self.bufpos = self.tagpos

            if self.EOF:
                break

            if self.buffer[self.tagpos:self.tagpos+4] == "<!--":
                endpos = self.scanTo("-->") + 3
                self.bufpos = endpos
                continue
          
            endpos = self.scanTo(">") + 1
  
            tag = self.buffer[self.tagpos+1:endpos-1]
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
                    tagElements = tag.split(" ")
                    self.handleStartElement(tagElements[0], self.makeAttrDict(tagElements[1:]))

            self.bufpos = endpos
            
    def scanTo(self, string):
        #sys.stderr.write("scanto: %s\n" % string)
        scanpos = self.bufpos
        while True:
            pos = self.buffer.find(string, scanpos)
            if pos >= 0:
                #sys.stderr.write("found: %s %i\n" % (string,pos))
                return pos
            scanpos = len(self.buffer)
            if self.EOF:
                return scanpos
            newdata = self.file.read(100000)
            #sys.stderr.write("Read: %s\n" % (repr(newdata)))
            if newdata == "":
                self.EOF = True
                #sys.stderr.write("eof: %s %i\n" % (string,scanpos))
            if len(self.buffer) > 1000000:
                raise Exception("SimpleXMLParser buffer overflow\n")
            #sys.stderr.write("append: %s\n" % (newdata))
            self.buffer = "".join([self.buffer[self.bufpos:], newdata])
            scanpos = scanpos - self.bufpos
            self.tagpos = self.tagpos - self.bufpos
            self.bufpos = 0
            

    def makeAttrDict(self, tokens):
        attrDict = {}

        # handle quoted strings containing spaces
        i = 0
        while i < len(tokens):
            if tokens[i] == "":
                tokens.pop(i)
            elif (tokens[i].count('"') == 1) and (i+1 < len(tokens)):
                tokens[i] = tokens[i] + " " + tokens[i+1]
                tokens.pop(i+1)
            elif (tokens[i].count("'") == 1) and (i+1 < len(tokens)):
                tokens[i] = tokens[i] + " " + tokens[i+1]
                tokens.pop(i+1)
            else:
                i = i + 1

        for t in tokens:
            sep = t.find("=")
            if sep == -1:
                name = t
                value = ""
            else:
                name = t[:sep]
                value = t[sep+1:]
            if value and (value[0] == '"') and (value[-1] == '"'):
                value = value[1:-1]
            if value and (value[0] == "'") and (value[-1] == "'"):
                value = value[1:-1]
            attrDict[name] = value
        return attrDict
    
    def handleStartElement(self, tag, attrsList):
            
        sys.stderr.write("XML start tag: <%s> %s\n" % (tag, str(attrsList)))

    def handleEndElement(self, tag):

        sys.stderr.write("XML end tag: </%s>\n" % tag)

    def handleRawCharacterData(self, data):
        data = data.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", '&')
        self.handleCharacterData(data)
        
    def handleCharacterData(self, data):

        sys.stderr.write("data: '%s'\n" % data)
    
if __name__ == '__main__':
    import sys

    p = SimpleXMLParser() 
    s = '''
    <h1
    >This is a &quot;title&quot;</h1><br>\n<a href="there"
    class=x>this<br/><i class='yyy'>and</i>  <!---ignore me <really> -->zz
    asdfffffffffffsssssssssssssssssssssssssssssssssssssssssssssssss
    ddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
    fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    ggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg
    hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh
    iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii
    lllllllllllllllllllllllllllllllllllllllllllllllllllllllllllll
    <b>that</i><span selected></b></a><minor /><a href="big daddy">yowza</a>
    '''
    print s
    
    p.parseString(s)

    print "Done."





