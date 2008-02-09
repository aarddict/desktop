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

import aarddict.compactjson
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
import tempfile
import anydbm

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
	
    if (not title) or (not text):
        sys.stderr.write("Skipped blank article: \"%s\" -> \"%s\"\n" % (title, text))
        return
    
    #debug.write(text)
    
    parser = HTMLParser()
    parser.parseString(text)

    jsonstring = compactjson.dumps([parser.text.rstrip(), parser.tags])
    if options.compress == "bz2":
        jsonstring = bz2.compress(jsonstring)
    #sys.stderr.write("write article: %i %i %s\n" % (article_file.tell(), len(jsonstring), title))    
    
    if header["article_count"] % 100 == 0:
        sys.stderr.write("\r" + str(header["article_count"]))
    header["article_count"] = header["article_count"] + 1
		
#    if len(title) > TITLE_MAX_SIZE:
#        sys.stderr.write("Truncated title: " + title + "\n")
#        title = title[:TITLE_MAX_SIZE]

    # todo:  don't use field separators, or at least use final 3 underscores in a group

    collationKeyString4 = collator4.getCollationKey(title).getBinaryString()

    #sys.stderr.write("Text: %s\n" % parser.text[:40])
    if parser.text.lstrip().startswith("See:"):
        #sys.stderr.write("See: %s\n" % parser.text)
        try:
            redirectTitle = parser.tags[0][3]["href"]
        except:
            sys.stderr.write("Missing redirect target: %s\n" % title)
            return
        collationKeyString1 = collator1.getCollationKey(redirectTitle).getBinaryString()
    else:
        collationKeyString1 = collator1.getCollationKey(title).getBinaryString()
        if collationKeyString1 in index_db:
            sys.stderr.write("Duplicate key: %s\n" % title)
        else:
            #sys.stderr.write("Real article: %s\n" % title)
            index_db[collationKeyString1] = str(article_pointer)
        
    sortex.put(collationKeyString4 + "___" + title + "___" + collationKeyString1)

    # index length calculated here because the header is written before we
    # actually write out the index
    header["index_length"] = header["index_length"] + 4 + struct.calcsize("LLhL") + len(collationKeyString4) + 3 + len(title)

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
        sortkey, title, articleCollationKey1 = item.split("___", 3)
        try:
            article_file = 0
            article_pointer = index_db[articleCollationKey1]
        except KeyError:
            sys.stderr.write("Redirect not found: %s\n" % title)
            article_file = -1
            article_pointer = 0
        sys.stderr.write("sorted: " + title + "\n")
        i_next = 4 + headerlen + len(sortkey) + 3 + len(title)
        wunit = sep + struct.pack(headerpack, long(i_next), long(i_prev), article_file, long(article_pointer)) + sortkey + "___" + title
        outputFile.write(wunit)
	
        i_prev = i_next
    
    sys.stderr.write("\r" + str(count) + "\n")

#__main__

#debug = open("debug.html", "w")

options, args = getOptions()

if options.output_file:
    outputFile = open(options.output_file, "wb", 4096)
else:
    outputFile = sys.stdout

if options.input_file:
    inputFile = open(options.input_file, "rb", 4096)
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


article_file = tempfile.NamedTemporaryFile('w+b')
article_pointer = 0

index_db_tempdir = tempfile.mkdtemp()
index_db_fullname = os.path.join(index_db_tempdir, "index.db")
index_db = anydbm.open(index_db_fullname, 'n')

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

sys.stderr.write("Sorting index...\n")

sortex.sort()

sys.stderr.write("Writing header...\n")

f = open("ISO-639-2.txt", "r")
languageCodeDict = {}
for line in f:
    codes = line.split('|')
    languageCodeDict[codes[0]] = codes[2]
f.close()

if header["article_language"].lower() in  languageCodeDict:
    header["article_language"] = languageCodeDict[header["article_language"].lower()]
if header["index_language"].lower() in  languageCodeDict:
    header["index_language"] = languageCodeDict[header["index_language"].lower()]

json_text = compactjson.dumps(header)

header_length_1 = len(json_text)

header["index_offset"] = 5 + 8 + header_length_1 + 60
header["article_offset"] = header["index_offset"] + header["index_length"]
	
outputFile.write("aar10")
json_text = compactjson.dumps(header)
outputFile.write("%08i" % len(json_text))
	
outputFile.write(json_text)
	
outputFile.write("-" * (header_length_1 + 60 - len(json_text)))

sys.stderr.write("Writing index...\n")
make_full_index()

sortex.cleanup()

index_db.close()
os.remove(index_db_fullname)
os.rmdir(index_db_tempdir)

sys.stderr.write("Writing articles...\n")
article_file.flush()
article_file.seek(0)

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




