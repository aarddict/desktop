#!/usr/bin/env python
#coding:utf-8

from __future__ import with_statement
import optparse
import sys
'''
This script extracts template pages from a Wiki xml dump and stores them in a
shelve object (persisted to the output file specified). This enables template processing
during actual Wiki conversion. Template pages are pages with names in the template namespace. 
Template namespaces are different in different languages. Language is specified as input 
parameter with two-letter language code and defaults to "en"
'''
usage = "usage: %prog [options] "
parser = optparse.OptionParser(version="%prog 1.0", usage=usage)

parser.add_option(
    '-o', '--output-file',
    help='Output file',
    required = True
    )
parser.add_option(
    '-i', '--input-file',
    help='Input file'
    )

parser.add_option(
    '-l', '--lang',
    help='Language',
    default = 'en'
    )

options, args = parser.parse_args()

import xml.parsers.expat
import shelve

prefix_map = {"en" : "Template:", "ru" : "Шаблон:"}

class TemplateHandler:
    
    intitle = False 
    intext = False   
    templates = shelve.open(options.output_file)
    prefix = prefix_map[options.lang].decode('utf-8')
    current_title = None
    current_char_data = u""
    
    def start_element(self, name, attrs):
        if name == "title":
            self.intitle = True
        if name == "text":
            self.intext = True
            
    def end_element(self, name):
        if name == "title":
            self.intitle = False
        if name == "text":
            self.intext = False
            if self.current_title:
                self.templates[self.current_title.encode('utf-8')] = self.current_char_data.encode('utf-8')
                self.current_title = None
                self.current_char_data = u""
            
    def char_data(self, data):
        if self.intitle and data.startswith(self.prefix):
            self.current_title = data[len(self.prefix):]
        if self.intext and self.current_title:
            self.current_char_data += data
            

p = xml.parsers.expat.ParserCreate('UTF-8')
t = TemplateHandler()
p.StartElementHandler = t.start_element
p.EndElementHandler = t.end_element
p.CharacterDataHandler = t.char_data

with open(options.input_file) as f:
    p.ParseFile(f)

print "total found:", len(t.templates)

t.templates.close()
