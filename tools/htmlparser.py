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

class HTMLParser(SimpleXMLParser):

    def __init__(self):
        SimpleXMLParser.__init__(self)
        self.StartElementHandler = self.handleStartElement
        self.EndElementHandler = self.handleEndElement
        self.CharacterDataHandler = self.handleCharacterData
        self.goodtags =  ['h1', 'h2', 'a', 'b', 'i', 'ref', 'p', 'br', 'img', 'big', 'small', 'sup', 'blockquote', 'tt']
        self.tags = []
        self.tagstack = []
        self.text = ""
    
    def handleStartElement(self, tag, attrsDict):

        if not tag in self.goodtags:
            return

        #sys.stderr.write("HTML start tag: <%s> at '%s'\n" % (tag, self.text[-20:]))

        if tag == "p":
            self.text = self.text + "\n\n"
            return

        if tag == "br":
            self.text = self.text + "\n"
            return
            
        t = [tag, len(self.text), -1, attrsDict]
        self.tagstack.append(t)

    def handleEndElement(self, tag):

        if not tag in self.goodtags:
            return

        #sys.stderr.write("HTML end tag: </%s> at '%s'\n" % (tag, self.text[-20:]))

        if tag == "br" or tag == "p":
            # i.e. <br/> </p>
            return

        if (len(self.tagstack) == 0) or (self.tagstack[-1][0] != tag):
            sys.stderr.write("Mismatched HTML end tag: </%s> at '%s'\n" % (tag, self.text[-20:]))
            return

        t = self.tagstack.pop()
        t[2] = len(self.text)
        self.tags.append(t)

    def handleCharacterData(self, data):

        self.text = self.text + data

    def getText(self):
        text = self.text
        return text

    def getTags(self):
        return self.tags
    
if __name__ == '__main__':
    import sys

    s = '<h1>This is the départment&quot;s</h1><br>\n<a href="the red">this<br/><i>and</i> <b>that</i></b></a>'

    print s
    print ""

    parser = HTMLParser()
    parser.parseString(s)
    print repr(parser.text)
    print repr(parser.tags)

    print "Done."





