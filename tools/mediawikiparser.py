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

# http://en.wikipedia.org/wiki/Help:Editing
# http://en.wikipedia.org/wiki/Help:Template        


# todo: check for recursion loops in templates
# handle alternate namespaces {xx:yy}
# use term "formal" parameter for placeholder
# parse tables {|
# parse indents (:)
# handle <nowiki>
# process #switch template function

import os
import sys
import re
import tempfile
import shelve
import aarddict.compactjson

from simplexmlparser import SimpleXMLParser
from simplexmlparser import unescape

from aarddict.article import Article
from aarddict.article import Tag
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
        self.reComment = re.compile(r"<\!--.*?-->", re.DOTALL)
        self.reH6 = re.compile(r"=======(.+?)=======")
        self.reH5 = re.compile(r"======(.+?)======")
        self.reH4 = re.compile(r"=====(.+?)=====")
        self.reH3 = re.compile(r"====(.+?)====")
        self.reH2 = re.compile(r"===(.+?)===")
        self.reH1 = re.compile(r"==(.+?)==")
        self.reBI = re.compile(r"'''''(.+?)'''''")
        self.reB = re.compile(r"'''(.+?)'''")
        self.reI = re.compile(r"''(.+?)''")
        self.reHr = re.compile(r"^-----*")
        self.reList = re.compile(r"^((\*+)|(#+))") 

        self.stackLevel = 0
                                    
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
            m = re.compile(r"http://(.*?)\.wik").match(entrytext)
            if m:
                self.metadata["index_language"] = m.group(1)
                self.metadata["article_language"] = m.group(1)
        
        elif tag == "title":
            self.title = self.clean(entrytext, oneline=True)
            self.title = self.title.replace("_", " ")
        
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

            self.parseLevel = 0
            self.text = self.parseBracketedElements(self.text, {})

            self.text = self.reComment.sub("", self.text)

            self.redirect = (self.reRedirect.search(self.text) != None)
            if self.redirect:
                self.text = self.reRedirect.sub("See:", self.text)
            #sys.stderr.write("\n\nMediawiki article before: %s\n" % (self.text))
            #try:
            #    self.text = wikimarkup.parselite(self.text).strip()
            #except Exception, e:
            #    sys.stderr.write("Unable to translate wiki markup: %s\n" % str(e))
            #    self.text = ""
            self.text = self.parseMiscellaneousMarkup(self.text).strip()
            self.text = self.parseLists(self.text).strip()
            #sys.stderr.write("\n\nMediawiki article 4: %s %s\n" % (self.title, self.text))

            if not self.redirect:
                self.text = "<h1>" + self.title + "</h1>" + self.text
            #sys.stderr.write("Mediawiki article: %s %s %s\n" % (self.title, len(self.text), repr(self.text)))
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
                redirect = redirect.replace("_", " ")
                redirectKey = self.collator.getCollationKey(redirect)
                titleKey = self.collator.getCollationKey(title)
                if redirectKey == titleKey:
                    #sys.stderr.write("Weak redirect: " + repr(title) + " " + repr(redirect) + "\n")
                    return True
        return False

    def parseBracketedElements(self, s, values={}):

        self.parseLevel += 1
        #sys.stderr.write("ParseBracketedElements (in): %i %s %s\n" % (self.parseLevel, repr(s), repr(values)))

        left = 0
        while 1:
            while (left < len(s)) and (s[left] not in ('{', '[')):
                left += 1
            if left >= len(s):
                #sys.stderr.write("ParseBracketedElements (out): %i %s\n" % (self.parseLevel, repr(s)))
                self.parseLevel -= 1
                return s
            elementStartChar = s[left]
            #sys.stderr.write("char: %s\n" % (elementStartChar))
            
            if elementStartChar == '{':
                elementEndChar = '}'
            else:
                elementEndChar = ']' 
            nest = 1
            right = left + 1
            while (nest > 0) and (right < len(s)):
                if s[right] == elementStartChar:
                    nest += 1
                elif s[right] == elementEndChar:
                    nest -= 1
                right += 1
            
            element = s[left:right]
            element = element.replace("\n", "")
            #sys.stderr.write("Element: %s\n" % element)

            if element.startswith("{{"):
                element = self.parseCurly(element, values)
                s = "".join([s[:left], element, s[right:]]) 
            elif element.startswith("[["):
                element = self.parseSquare(element, values)
                s = "".join([s[:left], element, s[right:]])
            else:
                left += 1


    def parseCurly(self, s, values={}):

        #self.stackLevel += 1
        #sys.stderr.write("ParseCurly: %i %s %s\n" % (self.stackLevel, repr(s), repr(values)))
        
        
        #if template in self.templateStack:
        #    sys.stderr.write("Template self-reference: %s\n" % repr(self.templateStack))
        #    return ""
        
        #self.templateStack.append(template)

        # recursively parse nested templates
        if s.startswith("{{{{"):
            r = "{" + self.parseBracketedElements(s[1:-1], values) + "}"

        elif s.startswith("{{{"):
            p = s[3:-3].split("|", 1)
            r = values.get(p[0], "")
            if not s and len(p) > 1:
                r = p[1]
        
        elif s.startswith("{{"):
            r = self.parseBracketedElements(s[2:-2], values)
            #sys.stderr.write("Split: %s\n" % r)
            templateParts = r.split("|")
            templateName = templateParts[0].strip()
            if templateName.startswith("#"):
                r = self.evaluateFunction(templateParts)
            else:
                r = self.evaluateTemplate(templateParts) 
        
        #self.stackLevel -= 1
        #sys.stderr.write("Replaced: %s --> %s\n" % (repr(s),repr(r)))

        return r

    def evaluateFunction(self, parts):

        f = parts[0].split(":")
        if len(f) <= 1:
            sys.stderr.write("Malformed function: %s\n" % (repr(parts)))
            return ""
        
        if f[0] == "#if":
            if f[1].strip():
                return parts[1]
            else:
                if len(parts) == 3:
                    return parts[2]
                else:
                    return ""

        if f[0] == "#ifeq":
            if f[1].strip() == parts[1].strip():
                return parts[2]
            else:
                if len(parts) == 4:
                    return parts[3]
                else:
                    return ""

        sys.stderr.write("Unknown function: %s\n" % (repr(parts)))
        return ""
        

    def evaluateTemplate(self, parts):

        if parts[0] == "NAMESPACE":
            return self.metadata["index_language"]

        if parts[0] == "PAGENAME":
            return self.title

        if parts[0].upper().startswith("UCFIRST:"):
            return parts[0][8:].strip().capitalize()

        if not self.templateDb:
            return ""
        
        template = self.templateDb.get(parts[0], "")

        if template.startswith("#REDIRECT"):
            #sys.stderr.write("redirect: %s %s\n" % (repr(parts[0]), repr(template)))
            m = self.reSquare2.search(template)
            if m:
                redirect = m.group(1).split(":", 1)
                if len(redirect) == 1:
                    redirect = redirect[0]
                else:
                    redirect = redirect[1]
                template = self.templateDb.get(redirect, "")
                #sys.stderr.write("redirected to: %s %s\n" % (repr(redirect), repr(template)))

        if not template:
            sys.stderr.write("Template not found: %s\n" % (repr(parts)))
            return ""

        #sys.stderr.write("template: %s --> %s\n" % (repr(parts[0]), repr(template)))
        
        realArguments = {}
        n = 0
        for p in parts[1:]:
            p = p.split("=", 1)
            if len(p) == 2:
                realArguments[p[0]] = p[1]
            else:
                n += 1
                realArguments[str(n)] = p[0]
        template = self.parseBracketedElements(template, realArguments)
        return template
            
        
    def parseSquare(self, s, values={}):

        #self.stackLevel += 1
        #sys.stderr.write("ParseSquare: %s\n" % (repr(s)))
        
        r = self.parseBracketedElements(s[2:-2], values)

        r = r.replace('"', "&quot;")
                
        p = r.split("|")
                
        c = p[0].split(":", 1)

        if len(c) == 2 and c[0].lower() == "image":
            r = ''
        else:
            p[0] = p[0].replace("_", " ")
            r = '<a href="' + p[0] + '">' + p[-1] + '</a>'
        
        #self.stackLevel -= 1
        #sys.stderr.write("ParseSquare Replaced: %s --> %s\n" % (repr(s),repr(r)))

        return r

    def parseMiscellaneousMarkup(self, text):

        #sys.stderr.write("\n\nmisc markup in: %s\n" % (text))
        
        text = text.replace("\r", "")
        text = text.replace("\n\n", "\n<p>")
        text = self.reH4.sub(r"<h4>\1</h4>", text)
        text = self.reH3.sub(r"<h3>\1</h3>", text)
        text = self.reH2.sub(r"<h2>\1</h2>", text)
        text = self.reH1.sub(r"<h1>\1</h1>", text)
        text = self.reBI.sub(r"<b><i>\1</i></b>", text)
        text = self.reB.sub(r"<b>\1</b>", text)
        text = self.reI.sub(r"<i>\1</i>", text)
        text = self.reHr.sub(r"<hr />", text)

        text = text.replace("__NOEDITSECTION__", "")

        #sys.stderr.write("\n\nmisc markup out: %s\n" % (text))

        return text

    def parseLists(self, text):
        lines = text.splitlines()
        lines.append("")
        listStack = []
        for i in range(0, len(lines)):
            #sys.stderr.write("i: %i %s\n" % (i, lines[i]))
            m = self.reList.search(lines[i])
            if m:
                tag = m.group(1)
            else:
                tag = ""

            matchLevel = 0
            while matchLevel < len(tag) and matchLevel < len(listStack) and tag[matchLevel] == listStack[matchLevel][0]:
                matchLevel += 1

            while len(listStack) > matchLevel:
                lines[i-1] += "\n</" + listStack.pop()[1] + ">"

            if tag:
                lines[i] = "<li>" + lines[i][len(tag):].strip() + "</ul>"
                while len(tag) > len(listStack):
                    c = tag[len(listStack)]
                    if c == "*":
                        #sys.stderr.write("i3: %i\n" % (i))
                        lines[i] = "<ul>\n" + lines[i]
                        listStack.append(["*", "ul"])
                    else:
                        #sys.stderr.write("i4: %i\n" % (i))
                        lines[i] = "<ol>\n" + lines[i]
                        listStack.append(["#", "ol"])

        text = "\n".join(lines)

        return text


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

    templates = { "M": "masculin", "Good": "GOOD", "Infobox": "***{{{1}}}<br>{{{2}}}"}
    templates = shelve.open("/var/d3/wiktionary-fr.tpl", "r")

    collator = aarddict.pyuca.Collator("aarddict/allkeys.txt")    
    parser = MediaWikiParser(collator, {"index_language": "fr"}, templates, printDoc)
    parser.parseString(s)
    
    print "Done."

