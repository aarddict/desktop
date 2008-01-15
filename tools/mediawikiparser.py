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
        self.databucket = ""
        self.collator = collator
        self.metadata = metadata
        self.consumer = consumer
        self.tagstack = []
        self.StartElementHandler = self.handleStartElement
        self.EndElementHandler = self.handleEndElement
        self.CharacterDataHandler = self.handleCharacterData

    def handleStartElement(self, tag, attrs):

        self.tagstack.append([tag, ""])


    def handleEndElement(self, tag):

        if not self.tagstack:
            return
        
        entry = self.tagstack.pop()
        
        if entry[0] != tag:
            sys.stderr.write("mismatched tag: " + tag + " " + repr(entry) + "\n")
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
            data = self.clean(data, oneline=True)
            if data:
                sys.stderr.write("orphan data: '%s'\n" % data)
            return
        entry = self.tagstack.pop()
        entry[1] = entry[1] + data
        self.tagstack.append(entry)


    def clean(self, s, oneline = False):
        s = re.compile(r"^\s*", re.MULTILINE).sub("", s)
        s = re.compile(r"\s*$", re.MULTILINE).sub("", s)
        s = s.strip(" \n")
        if oneline:
            s = s.replace("\n", "")
        return s
    
    def weakRedirect(self, title, text):
        p = re.compile(r"#REDIRECT", re.IGNORECASE)
        if p.search(text):
            p = re.compile(r"\[\[(.*?)\]\]")
            m = p.search(text)
            if m:
                redirect = m.group(1)
                redirectKey = self.collator.getCollationKey(redirect)
                titleKey = self.collator.getCollationKey(title)
                if redirectKey == titleKey:
                    #sys.stderr.write("Weak redirect: " + repr(title) + " " + repr(redirect) + "\n")
                    return True
        return False

    def translateWikiMarkupToHTML(self, text):
        
        text = re.compile(r"\n", re.DOTALL).sub("<br>", text)
        text = re.compile(r"\r").sub("", text)
        text = re.compile(r"^#REDIRECT", re.IGNORECASE).sub("See:", text)
        text = re.compile(r"=====(.{,80}?)=====").sub(r"<h4>\1</h4>", text)
        text = re.compile(r"====(.{,80}?)====").sub(r"<h3>\1</h3>", text)
        text = re.compile(r"===(.{,80}?)===").sub(r"<h2>\1</h2>", text)
        text = re.compile(r"==(.{,80}?)==").sub(r"<h1>\1</h1>", text)
        text = re.compile(r"'''''(.{,80}?)'''''").sub(r"<b><i>\1</i></b>", text)
        text = re.compile(r"'''(.{,80}?)'''").sub(r"<b>\1</b>", text)
        text = re.compile(r"''(.{,80}?)''").sub(r"<i>\1</i>", text)
        text = re.compile(r"\{\{.*?\}\}").sub(r"", text)
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

    string = "<mediawiki><siteinfo><sitename>Wikipedia</sitename><base>http://fr.wikipedia.org/boogy</base></siteinfo><page><title>hiho</title><text>''blah'' [[Image:thing.png|right|See [[thing article|thing text]]]] cows {{go}} bong</text></page></mediawiki>"

    print string
    print ""

    metadata = {}

    parser = MediaWikiParser(collator, metadata, printArticle)
    parser.parseString(string)

    print metadata
    print "Done."


