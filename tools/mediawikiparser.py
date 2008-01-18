#!/usr/bin/python

# Process Wikipedia dump files
#
# Jeremy Mortis (mortis@ucalgary.ca)

import os
import sys
import re
from simplexmlparser import SimpleXMLParser

from aarddict.article import Article
from aarddict.article import Tag
import aarddict.pyuca

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
        self.reH4 = re.compile(r"=====(.{,80}?)=====")
        self.reH3 = re.compile(r"====(.{,80}?)====")
        self.reH2 = re.compile(r"===(.{,80}?)===")
        self.reH1 = re.compile(r"==(.{,80}?)==")
        self.reBI = re.compile(r"'''''(.{,200}?)'''''")
        self.reB = re.compile(r"'''(.{,200}?)'''")
        self.reI = re.compile(r"''(.{,200}?)''")
        self.reCurly2 = re.compile(r"\{\{.*?\}\}")
        self.reSquare2 = re.compile(r"\[\[(.*?)\]\]")
        self.reLeadingSpaces = re.compile(r"^\s*", re.MULTILINE)
        self.reTrailingSpaces = re.compile(r"\s*$", re.MULTILINE)


    def handleStartElement(self, tag, attrs):

        self.tagstack.append([tag, ""])


    def handleEndElement(self, tag):

        if not self.tagstack:
            return
        
        entry = self.tagstack.pop()
        
        if entry[0] != tag:
            sys.stderr.write("mismatched tag: %s in %s at %s\n" % (repr(tag), repr(self.title), repr(entry)))
            return

        if tag == "sitename":
            self.metadata["title"] = self.clean(entry[1], oneline=True)

        elif tag == "base":
            m = re.compile(r"http://(.*?)\.wikipedia").match(entry[1])
            if m:
                self.metadata["index_language"] = m.group(1)
                self.metadata["article_language"] = m.group(1)
        
        elif tag == "title":
            self.title = self.clean(entry[1], oneline=True)
        
        elif tag == "text":
            self.text = self.clean(entry[1])
                        
        elif tag == "page":
            
            if self.weakRedirect(self.title, self.text):
                return
            
            self.text = self.translateWikiMarkupToHTML(self.text)

            self.consumer(self.title, self.text)
            return
            
    def handleCharacterData(self, data):

        if not self.tagstack:
            if data.strip():
                sys.stderr.write("orphan data: '%s'\n" % data)
            return
        entry = self.tagstack.pop()
        entry[1] = entry[1] + data
        self.tagstack.append(entry)


    def clean(self, s, oneline = False):
        s = self.reLeadingSpaces.sub("", s)
        s = self.reTrailingSpaces.sub("", s)
        if oneline:
            s = s.replace("\n", "")
        return s
    
    def weakRedirect(self, title, text):
        if self.reRedirect.search(text):
            m = self.reSquare2.search(text)
            if m:
                redirect = m.group(1)
                redirectKey = self.collator.getCollationKey(redirect)
                titleKey = self.collator.getCollationKey(title)
                if redirectKey == titleKey:
                    #sys.stderr.write("Weak redirect: " + repr(title) + " " + repr(redirect) + "\n")
                    return True
        return False

    def translateWikiMarkupToHTML(self, text):
        
        text = text.replace("\n", "<br>")
        text = text.replace("\r", "")
        text = self.reRedirect.sub("See:", text)
        text = self.reH4.sub(r"<h4>\1</h4>", text)
        text = self.reH3.sub(r"<h3>\1</h3>", text)
        text = self.reH2.sub(r"<h2>\1</h2>", text)
        text = self.reH1.sub(r"<h1>\1</h1>", text)
        text = self.reBI.sub(r"<b><i>\1</i></b>", text)
        text = self.reB.sub(r"<b>\1</b>", text)
        text = self.reI.sub(r"<i>\1</i>", text)
        text = self.reCurly2.sub(r"", text)
        text = parseLinks(text)

        return text

def parseLinks(s):
    
    while 1:
        left = s.find("[[")
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
            sys.stderr.write("Mismatched brackets: %s %s %s\n" % (str(left), str(right), str(nest)))
            return ""
                        
        link = s[left:right]
        #print "Link:", link.encode("utf-8")
            
        # recursively parse nested links
        link = parseLinks(link[2:-2])
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
            

        s = s[:left] + r + s[right:] 
        
    return s


def printArticle(title, article):
    print "=================================="
    print title
    print "=================================="
    print article

    
if __name__ == '__main__':

    collator = aarddict.pyuca.Collator("aarddict/allkeys.txt", strength = 1)    

    string = "<mediawiki><siteinfo><sitename>Wikipedia</sitename><base>http://fr.wikipedia.org/boogy</base></siteinfo><page><title>hi&amp;ho</title><text>''blah'' [[Image:thing.png|right|See [[thing article|thing text]]]] cows {{go}} bong</text></page></x></mediawiki>\n \n \n"

    print string
    print ""

    metadata = {}

    parser = MediaWikiParser(collator, metadata, printArticle)
    parser.parseString(string)

    print metadata
    print "Done."


