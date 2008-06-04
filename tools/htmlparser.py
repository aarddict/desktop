#!/usr/bin/python
# coding: utf-8
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

from simplexmlparser import SimpleXMLParser
import sys
import re
import urllib

class HTMLParser(SimpleXMLParser):

    text = property(lambda self: self.docBuffer)
    
    def __init__(self):
        SimpleXMLParser.__init__(self)
        self.goodtags =  ['h1', 'h2', 'h3', 'h4', 'a', 'b', 'i', 'ref', 'p', 'br', 'img', 'big', 'small', 'sup', 'blockquote', 'tt', 'li']
        self.tags = []
        self.tagStack = []
        self.docBuffer = ""
        self.tagBuffer = ""
        self.textUnicodeLength = 0

        self.reHref = re.compile(r"^(\.\./)?(.+?)/?(#.*)?$")
        
    def handleStartElement(self, tag, attrsDict):

        self.bufferCharacterData()
        
        if not tag in self.goodtags:
            return

        #sys.stderr.write("HTML start tag: <%s> at '%s'\n" % (tag, self.text[-20:]))

        if tag in ["p", "br"]:
            if self.docBuffer and self.docBuffer[-1] != "\n": 
                self.docBuffer += "\n"
                self.textUnicodeLength += 1
            return

        elif tag == "li":
            if self.docBuffer and self.docBuffer[-1] != "\n": 
                self.docBuffer += "\n"
                self.textUnicodeLength += 1
            self.docBuffer += "\xE2\x80\xA2 "
            self.textUnicodeLength += 2
            return
        
        elif tag in ["h1", "h2", "h3", "h4", "blockquote", "tt"]:
            if self.docBuffer and self.docBuffer[-1] != "\n": 
                self.docBuffer += "\n"
                self.textUnicodeLength += 1

        elif tag == "ref":
                self.docBuffer += "["
                self.textUnicodeLength += 1

        if "href" in attrsDict:
            href = attrsDict["href"]
            href = self.reHref.sub(r"\2", href)
            attrsDict["href"] = urllib.unquote(href).replace("_", " ")
            
        t = [tag, self.textUnicodeLength, 0, attrsDict]
        self.tagStack.append(t)

    def handleEndElement(self, tag):

        self.bufferCharacterData()
        
        if not tag in self.goodtags:
            return

        #sys.stderr.write("HTML end tag: </%s> at '%s'\n" % (tag, self.text[-20:]))

        if tag == "br":
            # i.e. <br/>
            if self.docBuffer and self.docBuffer[-1] != "\n": 
                self.docBuffer += "\n"
                self.textUnicodeLength += 1
            return

        elif tag == "p":
            if self.docBuffer and self.docBuffer[-1] != "\n": 
                self.docBuffer += "\n"
                self.textUnicodeLength += 1
            if self.docBuffer and self.docBuffer[-2] != "\n": 
                self.docBuffer += "\n"
                self.textUnicodeLength += 1
            return

        elif tag == "li":
            if self.docBuffer and self.docBuffer[-1] != "\n": 
                self.docBuffer += "\n"
                self.textUnicodeLength += 1
            return

        elif tag in ["h1", "h2", "h3", "h4", "blockquote", "tt"]:
            if self.docBuffer and self.docBuffer[-1] != "\n": 
                self.docBuffer += "\n"
                self.textUnicodeLength += 1

        elif tag == "ref":
                self.docBuffer += "]"
                self.textUnicodeLength += 1

        if (len(self.tagStack) == 0) or (self.tagStack[-1][0] != tag):
            if (len(self.tagStack) > 1) and (self.tagStack[-2][0] == tag):
                t = self.tagStack.pop()
                #sys.stderr.write("Discarded HTML end tag: </%s> at '%s'\n" % (t[0], self.text[-20:]))
            else:
                #sys.stderr.write("Mismatched HTML end tag: </%s> at '%s %s'\n" % (tag, repr(self.text[-20:]), repr(self.tagStack)))
                return

        t = self.tagStack.pop()
        t[2] = self.textUnicodeLength
        self.tags.append(t)

    def handleCharacterData(self, data):
        
        #sys.stderr.write("Data: %s\n" % repr(data))
        self.tagBuffer += data.replace("\n", " ")

    def bufferCharacterData(self):

        # character data is utf-8 but length (used for tag offsets) must be based on unicode
        if not self.tagBuffer:
            return
        try:
            if self.docBuffer and self.docBuffer[-1] == "\n" and self.tagBuffer[0] == " ":
                self.tagBuffer = self.tagBuffer.lstrip()
            self.textUnicodeLength = self.textUnicodeLength + len(self.tagBuffer.decode("utf-8"))
            self.docBuffer += self.tagBuffer
        except:
            sys.stderr.write("Undecodable string: %s\n" % (repr(self.tagBuffer)))
            
        self.tagBuffer = ""

    def handleCleanup(self):
        self.bufferCharacterData()
        
if __name__ == '__main__':
    import sys

    s = 'entry<html><p>hiho</p><h1>This is the départment&quot;s</h1><br>\n<a href="the red">this<br/><i>and</i> <b>that</i></b></a> <ul><li>item1</li><li>item2</li></ul></html>exit'

    print s
    print ""

    parser = HTMLParser()
    parser.parseString(s)
    print repr(parser.text)
    print repr(parser.tags)

    print "Done."





