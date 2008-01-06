#!/usr/bin/python

# Process Wikipedia dump files
#
# Jeremy Mortis (mortis@ucalgary.ca)

import os
import sys
import re

import xml.sax
import xml.sax.handler

from article import Article
from article import Tag
import pyuca

class MediaWikiParser(xml.sax.handler.ContentHandler):

    def __init__(self, collator, metadata, consumer):
        self.databucket = ""
        self.collator = collator
        self.metadata = metadata
        self.consumer = consumer
        self.tagstack = []

    def startElement(self, tag, attrs):

        self.tagstack.append([tag, ""])


    def endElement(self, tag):
        entry = self.tagstack.pop()
        
        if entry[0] != tag:
            sys.stderr.write("mismatched tag: " + repr(entry) + "\n")
            return
        
        if tag == "title":
            self.title = self.clean(entry[1], oneline=True)
        
        if tag == "text":
            self.text = self.clean(entry[1])
                        
        if tag == "page":
            
            if self.weakRedirect(self.title, self.text):
                return
            
            self.text = self.translate_wiki_markup_to_html(self.text)

            self.consumer(self.title, self.text)
            return
            
    def characters(self, data):

        entry = self.tagstack.pop()
        entry[1] = entry[1] + data
        self.tagstack.append(entry)


    def clean(self, s, oneline = False):
        s = s.encode("utf-8")
        s = re.compile(r"^\s*", re.MULTILINE).sub("", s)
        s = re.compile(r"\s*$", re.MULTILINE).sub("", s)
        s = re.compile(r"\n\n*").sub(r"\n",s)
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
                    sys.stderr.write("Weak redirect: " + repr(title) + " " + repr(redirect) + "\n")
                    return True
        return False

    def translate_wiki_markup_to_html(self, text):
        
        text = re.compile(r"\n", re.DOTALL).sub("<br>", self.text)
        text = re.compile(r"\r").sub("", self.text)
        text = re.compile('^#REDIRECT', re.IGNORECASE).sub("See:", self.text)
        text = re.compile("===(.*?)===").sub(r"<h2>\1</h2>", self.text)
        text = re.compile("==(.*?)==").sub(r"<h1>\1</h1>", self.text)
        text = re.compile("'''''(.*?)'''''").sub(r"<b><i>\1</i></b>", self.text)
        text = re.compile("'''(.*?)'''").sub(r"<b>\1</b>", self.text)
        text = re.compile("''(.*?)''").sub(r"<i>\1</i>", self.text)
        text = parse_links(text)
        text = parse_curly(text)
        return text

def parse_links(s):
    
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
            print "Mismatched brackets:", str(left), str(right), str(nest)
            return
                        
        link = s[left:right]
        print "Link:", link.encode("utf-8")
            
        # recursively parse nested links
        link = parse_links(link[2:-2])

        p = link.split("|")

        c = p[0].find(":")

        if c >= 0:
            t = p[0][:c]
        else:
            t = ""

        if t == "Image":
            r = '<img href="' + p[0][c+1:] + '">' + p[-1] + '</img>'
        elif t == "Category":
            r = ""
        elif len(t) == 2:
            # link to other language wikipedia
            r = ""
        elif t == "":
            r = '<a href="' + p[0] + '">' + p[-1] + '</a>'
        else:
            r = ""
            print "Unhandled link:", link.encode("utf-8")

        s = s[:left] + r + s[right:] 
        
    return s

def parse_curly(s):
                                
    p = re.compile(r"\{([^\{]*?)\}")
    s = p.sub(r"\1", s)

    p = re.compile(r"\{([^\{]*?)\}")
    s = p.sub(r"\1", s)
    return s

def article_printer(title, article):
    print "=================================="
    print title
    print "=================================="
    print article

    
if __name__ == '__main__':

    collator = pyuca.Collator("allkeys.txt", strength = 1)    

    string = "<page><title>hiho</title><text>''blah'' [[Image:thing.png|right|See [[thing article|thing text]]]]</text></page>"
    metadata = {}
    
    xml.sax.parseString(string, MediaWikiParser(collator, metadata, article_printer))

    print "Done."


