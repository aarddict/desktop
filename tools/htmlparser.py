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

    text = property(lambda self: "".join(self.textBuffer))

    def __init__(self):
        SimpleXMLParser.__init__(self)
        self.goodtags =  ['h1', 'h2', 'a', 'b', 'i', 'ref', 'p', 'br', 'img', 'big', 'small', 'sup', 'blockquote', 'tt']
        self.tags = []
        self.tagStack = []
        self.textBuffer = []
        self.textUnicodeLength = 0
        
    def handleStartElement(self, tag, attrsDict):

        if not tag in self.goodtags:
            return

        #sys.stderr.write("HTML start tag: <%s> at '%s'\n" % (tag, self.text[-20:]))

        if tag == "p":
            self.textBuffer.append("\n\n")
            self.textUnicodeLength = self.textUnicodeLength + 2
            return

        if tag == "br":
            self.textBuffer.append("\n")
            self.textUnicodeLength = self.textUnicodeLength + 1
            return
            
        t = [tag, self.textUnicodeLength, 0, attrsDict]
        self.tagStack.append(t)

    def handleEndElement(self, tag):

        if not tag in self.goodtags:
            return

        #sys.stderr.write("HTML end tag: </%s> at '%s'\n" % (tag, self.text[-20:]))

        if tag == "br" or tag == "p":
            # i.e. <br/> </p>
            return

        if (len(self.tagStack) == 0) or (self.tagStack[-1][0] != tag):
            if (len(self.tagStack) > 1) and (self.tagStack[-2][0] == tag):
                t = self.tagStack.pop()
                #sys.stderr.write("Discarded HTML end tag: </%s> at '%s'\n" % (t[0], self.text[-20:]))
            else:
                sys.stderr.write("Mismatched HTML end tag: </%s> at '%s %s'\n" % (tag, self.text[-20], repr(self.tagStack)))
                return

        t = self.tagStack.pop()
        t[2] = self.textUnicodeLength
        self.tags.append(t)

    def handleCharacterData(self, data):
        try:
            u = data.decode("utf-8")
            self.textUnicodeLength = self.textUnicodeLength + len(u)
            self.textBuffer.append(data)
        except Exception, e:
            sys.stderr.write(str(e) + "\n")
    
if __name__ == '__main__':
    import sys

    s = '<html><h1>This is the départment&quot;s</h1><br>\n<a href="the red">this<br/><i>and</i> <b>that</i></b></a></html>'

    print s
    print ""

    parser = HTMLParser()
    parser.parseString(s)
    print repr(parser.text)
    print repr(parser.tags)

    print "Done."





