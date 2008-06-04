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
import codecs
import StringIO

from mwlib import cdbwiki, uparser, htmlwriter
from simplexmlparser import SimpleXMLParser

import aarddict.pyuca

class MediaWikiParser(SimpleXMLParser):

    def __init__(self, collator, metadata, templateDb, consumer):
        SimpleXMLParser.__init__(self)
        self.collator = collator
        self.metadata = metadata
        self.templateDb = templateDb
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
            self.metadata["title"] = entrytext.replace("\n", "").strip()

        elif tag == "base":
            m = re.compile(r"http://(.*?)\.wik").match(entrytext)
            if m:
                self.metadata["index_language"] = m.group(1)
                self.metadata["article_language"] = m.group(1)
        
        elif tag == "title":
            self.title = entrytext.replace("\n", "").replace("_", " ").strip()

            sys.stderr.write("Mediawiki article: %s\n" % (self.title))
        
        elif tag == "text":
            self.text = entrytext
                        
        elif tag == "page":

            t = self.title.split(":", 1)
            if len(t) > 1 and t[0] in ["image", "template", "category", "wikipedia"]:
                return

            if self.text.startswith("#REDIRECT"): 
                m = self.reSquare2.search(self.text)
                if m:
                    redirect = m.group(1)
                    redirect = redirect.replace("_", " ")
                    redirectKey = self.collator.getCollationKey(redirect)
                    titleKey = self.collator.getCollationKey(self.title)
                    if redirectKey != titleKey:
                        self.consumer(self.title, "#REDIRECT " + redirect)
                    #sys.stderr.write("Weak redirect: " + repr(title) + " " + repr(redirect) + "\n")
                return

            #sys.stderr.write("mediawiki text: %s\n" % repr(self.text.decode("utf8")))
            mwObject = uparser.parseString(title=self.title.decode("utf8"), raw=self.text.decode("utf8"), wikidb=self.templateDb)
            htmlFile = StringIO.StringIO(u"")
            htmlwriter.HTMLWriter(htmlFile).write(mwObject)
            self.text = htmlFile.getvalue().encode("utf8")
            htmlFile.close()
            #sys.stderr.write("mediawiki html: %s\n" % repr(self.text.decode("utf8")))
            self.consumer(self.title, self.text)
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


def printDoc(title, text):
    print repr(title)
    print repr(text)

if __name__ == '__main__':
    import sys

    s = """
entry<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.3/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.mediawiki.org/xml/export-0.3/ http://www.mediawiki.org/xml/export-0.3.xsd" version="0.3" xml:lang="fr">
<siteinfo>
<sitename>Wikipedia</sitename>
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
<text xml:space="preserve">&lt;!-- comment --&gt;'''PJ''' &quot;white&quot; [[big_bang]] [[Moul]] here is a line.
{{-nom-|fr}}
The main {{export}} of any {{country}} is the 90" tall {{m}} people.
{{infobox|hi there {{good}}|neighbour}}
[[Image:Albedo-e hg.svg|thumb|Percentage of reflected sun light in
relation to various surface conditions of the earth]]
[[It's all about "quotes"]]
* here
* is
** a
*** list
# number 1
# number 2
blah
</text>
</revision>
</page>
</mediawiki>exit
"""
   
    print s
    print ""

    templateDb = cdbwiki.WikiDB("/var/d3/wiktionary-fr-tpl.cdb")
    collator = aarddict.pyuca.Collator("aarddict/allkeys.txt")    
    parser = MediaWikiParser(collator, {"index_language": "fr"}, templateDb, printDoc)
    parser.parseString(s)
    
    print "Done."

