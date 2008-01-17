#!/usr/bin/python

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

import simplejson
from sortexternal import SortExternal
from htmlparser import HTMLParser
import optparse
import sys
import struct
import aarddict.pyuca
import re
import binascii
import os
import array
from aarddict.article import *

TITLE_MAX_SIZE = 255

def getOptions():
    usage = "usage: %prog [options] "
    parser = optparse.OptionParser(version="%prog 1.0", usage=usage)

    parser.add_option(
        '-o', '--output-file',
        default='',
        help='Output file (default stdout)'
        )
    parser.add_option(
        '-i', '--input-file',
        default='',
        help='Input file (default stdin)'
        )
    parser.add_option(
        '-c', '--compress',
        default='bz2',
        help='Article compression method: bz2 (default) or none'
        )
    parser.add_option(
        '-f', '--input-format',
        default='none',
        help='Input format:  mediawiki or xdxf'
        )

    return parser.parse_args()

def handle_article(title, text):
    global header
    global article_pointer
    if header["article_count"] % 100 == 0:
        sys.stderr.write("\r" + str(header["article_count"]))
    header["article_count"] = header["article_count"] + 1
	
    if (not title) or (not text):
        sys.stderr.write("Skipped blank article: %s -> %s\n" % (repr(title), repr(text)))
        return
		
    if len(title) > TITLE_MAX_SIZE:
        sys.stderr.write("Truncated title: " + title + "\n")
        title = title[:TITLEMAX_SIZE]

    collationKeyString = collator4.getCollationKey(title).getBinaryString()

    # todo:  don't use field separators, or at least use final 3 underscores in a group

    sortex.put(collationKeyString + "___" + title + "___" + str(article_pointer))

    # index length calculated here because the header is written before we
    # actually write out the index
    header["index_length"] = header["index_length"] + 4 + struct.calcsize("LLhL") + len(collationKeyString) + 3 + len(title)

    parser = HTMLParser()
    parser.parseString(text)
    jsonstring = simplejson.dumps([parser.text, parser.tags])
    if options.compress == "bz2":
        jsonstring = bz2.compress(jsonstring)
    #sys.stderr.write("write article: %i %i %s\n" % (article_file.tell(), len(jsonstring), title))
    article_file.write(struct.pack("L", len(jsonstring)) + jsonstring)
    article_pointer = article_pointer + struct.calcsize("L") + len(jsonstring)

def make_full_index():
    global trailer_length
    
    i_prev = 0
    i_next = 0

    headerpack = "LLhL"
    headerlen = struct.calcsize(headerpack)

    sep = "\xFD\xFD\xFD\xFD"
    count = 0

    for item in sortex:
        if count % 100 == 0:
            sys.stderr.write("\r" + str(count))
        count = count + 1
        sortkey, title, article_pointer = item.split("___", 3)
        sys.stderr.write("sorted: " + title + "\n")
        i_next = 4 + headerlen + len(sortkey) + 3 + len(title)
        wunit = sep + struct.pack(headerpack, long(i_next), long(i_prev), 0, long(article_pointer)) + sortkey + "___" + title
        outputFile.write(wunit)
	
        i_prev = i_next
    
    sys.stderr.write("\r" + str(count) + "\n")

#__main__

options, args = getOptions()

if options.output_file:
    outputFile = open(options.output_file, "wb")
else:
    outputFile = sys.stdout

if options.input_file:
    inputFile = open(options.input_file, "rb")
else:
    inputFile = sys.stdin

collator4 = aarddict.pyuca.Collator("aarddict/allkeys.txt")
collator4.setStrength(4)

collator1 = aarddict.pyuca.Collator("aarddict/allkeys.txt")
collator1.setStrength(1)

sortex = SortExternal()

header = {
    "aarddict_version": "1.0",
    "character_encoding": "utf-8",
    "compression_type": options.compress
    }

trailer_length = 4 + struct.calcsize("LLhL") + 1 + 3 + 7

sys.stderr.write("Parsing input file...\n")

article_filename = "compile.tmp"
article_file = open(article_filename, "wb")
article_pointer = 0

header["article_count"] =  0
header["index_length"] =  0

if options.input_format == "xdxf" or inputFile.name[-5:] == ".xdxf":
    sys.stderr.write("Compiling %s as xdxf\n" % inputFile.name)
    from xdxfparser import XDXFParser
    p = XDXFParser(collator1, header, handle_article)
    p.parseFile(inputFile)
else:  
    sys.stderr.write("Compiling %s as mediawiki\n" % inputFile.name)
    from mediawikiparser import MediaWikiParser
    p = MediaWikiParser(collator1, header, handle_article)
    p.parseFile(inputFile)


sys.stderr.write("\r" + str(header["article_count"]) + "\n")
article_file.close()

sys.stderr.write("Sorting index...\n")

sortex.sort()

sys.stderr.write("Writing header...\n")

json_text = simplejson.dumps(header)

header_length_1 = len(json_text)

header["index_offset"] = 5 + 8 + header_length_1 + 60
header["article_offset"] = header["index_offset"] + header["index_length"]
	
outputFile.write("aar10")
json_text = simplejson.dumps(header)
outputFile.write("%08i" % len(json_text))
	
outputFile.write(json_text)
	
outputFile.write("-" * (header_length_1 + 60 - len(json_text)))

sys.stderr.write("Writing index...\n")
make_full_index()

sys.stderr.write("Writing articles...\n")
article_file = open(article_filename, "rb")

write_count = 0
while 1:
    article_len = article_file.read(4)
    if len(article_len) < 2:
        break
    if write_count % 100 == 0:
        sys.stderr.write("\r" + str(write_count))
    buffer = article_file.read(struct.unpack("i", article_len)[0])
    outputFile.write(article_len + buffer)
    write_count = write_count + 1
sys.stderr.write("\r" + str(write_count) + "\n")
article_file.close()

sys.stderr.write("Done.\n")




