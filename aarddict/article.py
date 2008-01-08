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

import os
from sgmllib import SGMLParser
import simplejson
import bz2
import struct
import sys

class Article:

    def __init__(self, title = "", text = "", tags = [], compress = "none"):
        self.title = title
        self.text = text
        self.tags = tags
        self.compress = compress

    def __str__(self):
        s = "title: " + self.title + "\n"
        s = s + "text: " + self.text + "\n"
        for tag in self.tags:
            s = s + "tag: " + str(tag) + "\n"
        return s

    def fromHTML(self, string):
        self.text = ""
        self.tags = []
        p = ArticleTagParser(self)
        p.feed(string)
        if __debug__:
            f = open("debug.html", "w")
            f.write(string)
            f.close()
        
    def fromJSON(self,string):
        self.text, tagList = simplejson.loads(string)
        self.tags = []
        for tagListItem in tagList:
            tag = Tag()
            tag.fromList(tagListItem)
            self.tags.append(tag)
        
    def fromFile(self, file, offset):
        file.seek(offset)
        record_length = struct.unpack('L', file.read(struct.calcsize("L")))[0]
        #sys.stderr.write("record length, offset: " + str(record_length) + " " + str(offset) + "\n")
        if self.compress == "bz2":
            s = file.read(record_length)
        else:
            s = bz2.decompress(file.read(record_length))

        self.fromJSON(s)

    def toJSON(self):
        tagList = []
        for tag in self.tags:
            tagList.append(tag.toList())
        return simplejson.dumps([self.text, tagList])

    def toFile(self, file):
        if self.compress == "bz2":
            s = bz2.compress(self.toJSON())
        else:
            s = self.toJSON()

        #sys.stderr.write("write article: " + file.tell() + " " + len(s) + " " + self.title)
        file.write(struct.pack("L", len(s)) + s)
        return struct.calcsize("L") + len(s)

class Tag:

    def __init__(self, name = "", start = -1, end = -1, attributes = {}):
        self.name = name
        self.start = start
        self.end = end
        self.attributes = attributes

    def __str__(self):
        return self.name + " " + str(self.start) + " " +  str(self.end) + " " + str(self.attributes)
    
    def toList(self):
        return [self.name, self.start, self.end, self.attributes]

    def fromList(self, list):
        self.name, self.start, self.end, self.attributes = list

    
class ArticleTagParser(SGMLParser):

    def __init__(self, article):
        SGMLParser.__init__(self)
        self.article = article
        self.tagstack = []

    def do_p(self, attrsList):
        self.article.text = self.article.text + "\n\n"

    def do_br(self, attrsList):
        self.article.text = self.article.text + "\n"
    
    def unknown_starttag(self, tag, attrsList):

        attrsDict = {}
        attrsDict.update(attrsList)
            
        t = Tag(tag, len(self.article.text), -1, attrsDict)
        self.tagstack.append(t)

    def unknown_endtag(self, tag):

        if (len(self.tagstack) == 0) or (self.tagstack[-1].name != tag):
            sys.stderr.write("Mismatched end tag: </" + tag + "> in " + self.article.title + " at \"" + self.article.text[-20:] + "\"\n")
            return
        t = self.tagstack.pop()
        t.end = len(self.article.text) - 1
        self.article.tags.append(t)

    def handle_data(self, data):

        self.article.text = self.article.text + data

if __name__ == '__main__':
    import sys

    s = '<title>This is a title</title><br>\n<a href="there">this <i>and</i> <b>that</b></a>'
    article = Article()

    article.fromHTML(s)

    print article

    json = article.toJSON()
    print json
    
    article.fromJSON(json)
    print article

    print "Done."





