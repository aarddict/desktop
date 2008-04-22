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
        buffer = ""
        buflen = 0
        bufpos = 1
        tag = ""
        data = ""
        
        while True:

            if bufpos >= buflen:
                buffer = file.read(100000)
                buflen = len(buffer)
                bufpos = 0
                
            if not buffer:
                break
            
            if tag:
                pos = buffer.find(">", bufpos)
                if pos >= 0:
                    tag += buffer[bufpos:pos+1]
                    bufpos = pos+1
                    if tag.startswith("<!--"):
                        if tag.endswith("-->"):
                            tag = ""
                            continue
                        else:
                            continue
                    else:
                        self.processTag(tag)
                        inTag = False
                        tag = ""
                        continue
                else:
                    tag += buffer[bufpos:]
                    bufpos = buflen
                    continue

            pos = buffer.find("<", bufpos)
            if pos == -1:
                data += buffer[bufpos:]
                # don't split "&nbsp;" etc.
                if buffer[-5:].find("&") == -1:
                    self.processData(data)
                    data = ""
                bufpos = buflen
            else:
                if pos > bufpos:
                    data += buffer[bufpos:pos]
                self.processData(data)
                data = ""
                bufpos = pos + 1
                tag = "<"

        self.handleCleanup()
        
    def processTag(self, tag):
        tag = tag[1:-1]
        tag = tag.replace("\n", " ")

        if not tag:
            return
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
            attrDict[self.unescape(name)] = self.unescape(value)
        return attrDict

    def processData(self, data):
        self.handleCharacterData(self.unescape(data))

    def handleStartElement(self, tag, attrsList):
        # usually overridden
        sys.stderr.write("XML start tag: <%s> %s\n" % (tag, str(attrsList)))

    def handleEndElement(self, tag):
        # usually overridden
        sys.stderr.write("XML end tag: </%s>\n" % tag)
        
    def handleCharacterData(self, data):
        # usually overridden
        sys.stderr.write("XML data: '%s'\n" % data)

    def handleCleanup(self):
        # usually overridden
        sys.stderr.write("XML cleanup\n")

    def unescape(self, s):
        return s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", '&').replace("&mdash", "\xE2\x80\x94").replace("&nbsp;", "\xE2\x80\x87")

        
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
    <b>that</i><span selected></b></a><minor /><a href="big &quot;daddy&quot; o">yow&nbsp;za</a>
    '''
    print s
    
    p.parseString(s)

    print "Done."





