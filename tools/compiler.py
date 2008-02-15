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

def handleArticle(title, text):
    global header
    global articlePointer
    global aarFile, aarFileLength
    
    if (not title) or (not text):
        #sys.stderr.write("Skipped blank article: \"%s\" -> \"%s\"\n" % (title, text))
        return
    
    #debug.write(text)
    
    parser = HTMLParser()
    parser.parseString(text)

    jsonstring = compactjson.dumps([parser.text.rstrip(), parser.tags])
    if options.compress == "bz2":
        jsonstring = bz2.compress(jsonstring)
    #sys.stderr.write("write article: %i %i %s\n" % (articleTempFile.tell(), len(jsonstring), title))    
    
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
    else:
        if title in indexDb:
            sys.stderr.write("Duplicate key: %s\n" % title)
        else:
            #sys.stderr.write("Real article: %s\n" % title)
            indexDb[title] = str(articlePointer)
        
    sortex.put(collationKeyString4 + "___" + title)

    # index length calculated here because the header is written before we
    # actually write out the index
    header["index_length"] += 4 + struct.calcsize("LLhL") + len(collationKeyString4) + 3 + len(title)

    articleUnit = struct.pack("L", len(jsonstring)) + jsonstring
    articleUnitLength = len(articleUnit)
    if aarFileLength[-1] + articleUnitLength > aarFileLengthMax:
        aarFile.append(open(aarExtraFilenamePrefix + ("%02i" % len(aarFile)), "w+b", 4096))
        aarFileLength.append(0)
        sys.stderr.write("New temp article file: %s\n" % aarFile[-1].name)

    aarFile[-1].write(articleUnit)
    aarFileLength[-1] += articleUnitLength
    articlePointer += articleUnitLength

def makeFullIndex():
    global trailerLength
    global aarFile, aarFileLength
    
    iPrev = 0
    iNext = 0

    headerpack = "LLhL"
    headerlen = struct.calcsize(headerpack)

    sep = "\xFD\xFD\xFD\xFD"
    count = 0

    for item in sortex:
        if count % 100 == 0:
            sys.stderr.write("\r" + str(count))
        count = count + 1
        sortkey, title = item.split("___", 2)
        try:
            articlePointer = long(indexDb[title])
            if makeSingleFile:
                fileno = 0
            else:
                for fileno in range(1, len(aarFile)):
                    if articlePointer < aarFileLength[fileno]:
                        break
                    articlePointer -= aarFileLength[fileno]
        except KeyError:
            sys.stderr.write("Redirect not found: %s\n" % title)
            fileno = -1
            articlePointer = 0
        sys.stderr.write("sorted: %s %i %i\n" % (title, fileno, articlePointer))
        iNext = 4 + headerlen + len(sortkey) + 3 + len(title)
        wunit = sep + struct.pack(headerpack, long(iNext), long(iPrev), fileno, long(articlePointer)) + sortkey + "___" + title
        aarFile[0].write(wunit)
        aarFileLength[0] += len(wunit)
	
        iPrev = iNext
    
    sys.stderr.write("\r" + str(count) + "\n")

#__main__

#debug = open("debug.html", "w")

options, args = getOptions()
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

trailerLength = 4 + struct.calcsize("LLhL") + 1 + 3 + 7

sys.stderr.write("Parsing input file...\n")

if options.input_file:
    inputFile = open(options.input_file, "rb", 4096)
else:
    inputFile = sys.stdin

aarFile = []
aarFileLength = []

if options.output_file:
    aarFile.append(open(options.output_file, "w+b", 4096))
    if options.output_file[-3:] == "aar":
        aarExtraFilenamePrefix = options.output_file[:-2]
    else:
        aarExtraFilenamePrefix = options.output_file + ".a"
else:
    aarFile.append(sys.stdout)
aarFileLength.append(0)

aarFile.append(open(aarExtraFilenamePrefix + ("%02i" % len(aarFile)), "w+b", 4096))
aarFileLength.append(0)

aarFileLengthMax = 2000000000

indexDbTempdir = tempfile.mkdtemp()
indexDbFullname = os.path.join(indexDbTempdir, "index.db")
indexDb = anydbm.open(indexDbFullname, 'n')

articlePointer = 0L

header["article_count"] =  0
header["index_length"] =  0

if options.input_format == "xdxf" or inputFile.name[-5:] == ".xdxf":
    sys.stderr.write("Compiling %s as xdxf\n" % inputFile.name)
    from xdxfparser import XDXFParser
    p = XDXFParser(collator1, header, handleArticle)
    p.parseFile(inputFile)
else:  
    sys.stderr.write("Compiling %s as mediawiki\n" % inputFile.name)
    from mediawikiparser import MediaWikiParser
    p = MediaWikiParser(collator1, header, handleArticle)
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

makeSingleFile = (len(aarFile) == 2) and (aarFileLength[0] + aarFileLength[1] < aarFileLengthMax)
if makeSingleFile:
    header["file_count"] = 1
else:
    header["file_count"] = len(aarFile)

jsonText = compactjson.dumps(header)

header_length_1 = len(jsonText)

header["index_offset"] = 5 + 8 + header_length_1 + 60
header["article_offset"] = header["index_offset"] + header["index_length"]
	
aarFile[0].write("aar10")
aarFileLength[0] += 5

jsonText = compactjson.dumps(header)
aarFile[0].write("%08i" % len(jsonText))
aarFileLength[0] += 8
	
aarFile[0].write(jsonText)
aarFileLength[0] += len(jsonText)
	
filler = "-" * (header_length_1 + 60 - len(jsonText))
aarFile[0].write(filler)
aarFileLength[0] += len(filler)

sys.stderr.write("Writing index...\n")
makeFullIndex()

sortex.cleanup()

indexDb.close()
os.remove(indexDbFullname)
os.rmdir(indexDbTempdir)

sys.stderr.write("Writing articles...\n")

writeCount = 0L

if makeSingleFile:
    sys.stderr.write("Combining output files\n")
    aarFile[1].flush()
    aarFile[1].seek(0)
    while 1:
        if writeCount % 100 == 0:
            sys.stderr.write("\r" + str(writeCount))
        writeCount += 1
        articleLengthString = aarFile[1].read(4)
        if len(articleLengthString) == 0:
            break
        articleLength = struct.unpack("i", articleLengthString)[0]
        buffer = aarFile[1].read(articleLength)
        aarFile[0].write(articleLengthString + buffer)
        aarFileLength[0] += articleLength
    sys.stderr.write("\r" + str(writeCount) + "\n")
    aarFile[0].close()
    aarFile[1].close()
    os.remove(aarFile[1].name)    
else:
    sys.stderr.write("Created %i output files\n" % len(aarFile))
    for f in aarFile:
        f.close
    
sys.stderr.write("Done.\n")




