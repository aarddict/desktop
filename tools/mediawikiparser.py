#!/usr/bin/python
# coding: utf-8

"""
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

import os
import sys
import re
from simplexmlparser import SimpleXMLParser

from aarddict.article import Article
from aarddict.article import Tag
import aarddict.pyuca

# http://code.google.com/p/wikimarkup
import wikimarkup

class MediaWikiParser(SimpleXMLParser):

    def __init__(self, collator, metadata, consumer):
        SimpleXMLParser.__init__(self)
        self.collator = collator
        self.metadata = metadata
        self.consumer = consumer
        self.tagstack = []
        self.title = ""
        self.text = ""
        self.StartElementHandler = self.handleStartElement
        self.EndElementHandler = self.handleEndElement
        self.CharacterDataHandler = self.handleCharacterData
        self.reRedirect = re.compile(r"^#REDIRECT", re.IGNORECASE)
        self.reLeadingSpaces = re.compile(r"^\s*", re.MULTILINE)
        self.reTrailingSpaces = re.compile(r"\s*$", re.MULTILINE)
        self.reSquare2 = re.compile(r"\[\[(.*?)\]\]")
        
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

        if tag == "sitename":
            self.metadata["title"] = self.clean(entrytext, oneline=True)

        elif tag == "base":
            m = re.compile(r"http://(.*?)\.wikipedia").match(entrytext)
            if m:
                self.metadata["index_language"] = m.group(1)
                self.metadata["article_language"] = m.group(1)
        
        elif tag == "title":
            self.title = self.clean(entrytext, oneline=True)
        
        elif tag == "text":
            self.text = entrytext
                        
        elif tag == "page":
            
            if self.weakRedirect(self.title, self.text):
                return

            if self.title.lower().startswith("image:"):
                return

            if self.title.lower().startswith("template:"):
                return

            if self.title.lower().startswith("category:"):
                return

            if self.title.lower().startswith("wikipedia:"):
                return
                
            self.text = self.reRedirect.sub("See:", self.text)
            try:
                self.text = wikimarkup.parse(self.text, False).strip()
            except Exception, e:
                sys.stderr.write("Unable to translate wiki markup: %s\n" % str(e))
                self.text = ""
            self.text = self.parseLinks(self.text)
            self.text = self.parseTemplates(self.text)
            self.text = self.text.replace("&lt;", "<").replace("&gt;", ">");
            if not self.text.startswith("<p>See:"):
                self.text = "<h1>" + self.title + "</h1>" + self.text
            #sys.stderr.write("Mediawiki article: %s %s\n" % (self.title, self.text[:40]))
            self.consumer(self.title, self.text)
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
        s = self.reLeadingSpaces.sub("", s)
        s = self.reTrailingSpaces.sub("", s)
        return s.strip()
    
    def weakRedirect(self, title, text):
        if self.text.startswith("#REDIRECT"): 
            m = self.reSquare2.search(text)
            if m:
                redirect = m.group(1)
                redirectKey = self.collator.getCollationKey(redirect)
                titleKey = self.collator.getCollationKey(title)
                if redirectKey == titleKey:
                    #sys.stderr.write("Weak redirect: " + repr(title) + " " + repr(redirect) + "\n")
                    return True
        return False

    def parseLinks(self, s):

        left = -1
        while 1:
            left = s.find("[[", left + 1)
            if left < 0:
                break
            nest = 2
            right = left + 2
            while (nest > 0) and (right < len(s)):
                if s[right] == "[":
                    nest = nest + 1
                elif s[right] == "]":
                    nest = nest - 1
                right = right + 1
                        
            if (nest != 0):
                #sys.stderr.write("Mismatched brackets: %s %s %s\n" % (str(left), str(right), str(nest)))
                return ""
                        
            link = s[left:right]
            #sys.stderr.write("Link: %s\n" % link)
            
            # recursively parse nested links
            link = self.parseLinks(link[2:-2])
            if not link:
                return ""

            p = link.split("|")

            c = p[0].find(":")

            if c >= 0:
                t = p[0][:c]
                if t == "Image":
                    r = '<img href="' + p[0][c+1:] + '">' + p[-1] + '</img>'
                else:
                    r = ""
            else:
                r = '<a href="' + p[0] + '">' + p[-1] + '</a>'
            

            s = "".join([s[:left], r, s[right:]]) 
        
        return s

    def parseTemplates(self, s):

        left = -1
        while 1:
            left = s.find("{{", left + 1)
            if left < 0:
                break
            nest = 2
            right = left + 2
            while (nest > 0) and (right < len(s)):
                if s[right] == "{":
                    nest = nest + 1
                elif s[right] == "}":
                    nest = nest - 1
                right = right + 1
                        
            if (nest != 0):
                #sys.stderr.write("Mismatched braces: %s %s %s\n" % (str(left), str(right), str(nest)))
                return ""
                        
            template = s[left:right]
            #sys.stderr.write("Template: %s\n" % template)
            
            # recursively parse nested templates
            template = self.parseTemplates(template[2:-2])
            if not template:
                return ""

            # default behaviour is to remove templates
            if template[:8].lower() == "infobox ":
                #sys.stderr.write("Infobox: %s\n" % repr(template))
                template = "<p>============<br>" + template[8:]
                template = template.replace("|", "<br>")
                template = re.compile(r" +").sub(" ", template)
                template += "<br>=============</p>"
            else:
                #sys.stderr.write("Template ignored: %s\n" % repr(template))
                template = ""
        
            s = "".join([s[:left], template, s[right:]]) 
        
        return s

def printDoc(title, text):
    print repr(title)
    print repr(text)

if __name__ == '__main__':
    import sys

    s = """
entry<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.3/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.mediawiki.org/xml/export-0.3/ http://www.mediawiki.org/xml/export-0.3.xsd" version="0.3" xml:lang="fr">
<siteinfo>
<sitename>Wikipédia</sitename>
<base>http://fr.wikipedia.org/wiki/Accueil</base>
<generator>MediaWiki 1.12alpha</generator>
</siteinfo>
<page>
<title>Antoine Meillet</title>
<id>3</id>
<revision>
<id>19601668</id>
<timestamp>2007-08-10T21:17:41Z</timestamp>
<contributor>
<username>Gribeco</username>
<id>24358</id>
</contributor>
<minor />
<text xml:space="preserve">'''PJ''' [[nov]] [[Moul]] here is a line.
The main {{export}} of any {{country}} is the people.
{{infobox hi there {{good}} neighbour}}
</text>
</revision>
</page>
</mediawiki>exit
"""
   
    print s
    print ""
    
    collator = aarddict.pyuca.Collator("aarddict/allkeys.txt")    
    parser = MediaWikiParser(collator, {}, printDoc)
    parser.parseString(s)
    
    print "Done."

