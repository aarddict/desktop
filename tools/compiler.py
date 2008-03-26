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
		
#    if len(title) > TITLE_MAX_SIZE:
#        sys.stderr.write("Truncated title: " + title + "\n")

#        title = title[:TITLE_MAX_SIZE]

    # todo:  don't use field separators, or at least use final 3 underscores in a group

    collationKeyString4 = collator4.getCollationKey(title).getBinaryString()

    #sys.stderr.write("Text: %s\n" % parser.text[:40])
    if parser.text.startswith("See:"):
        #sys.stderr.write("See: %s\n" % parser.text)
        try:
            redirectTitle = parser.tags[0][3]["href"]
            sortex.put(collationKeyString4 + "___" + title + "___" + redirectTitle)
        except:
            #sys.stderr.write("Missing redirect target: %s\n" % title)
            pass
        return


    if indexDb.has_key(title):
        sys.stderr.write("Duplicate key: %s\n" % title)
    else:
        #sys.stderr.write("Real article: %s\n" % title)
        indexDb[title] = str(articlePointer)

    sortex.put(collationKeyString4 + "___" + title + "___")

    articleUnit = struct.pack("L", len(jsonstring)) + jsonstring
    articleUnitLength = len(articleUnit)
    if aarFileLength[-1] + articleUnitLength > aarFileLengthMax:
        aarFile.append(open(aarExtraFilenamePrefix + ("%02i" % len(aarFile)), "w+b", 4096))
        aarFileLength.append(0)
        sys.stderr.write("New article file: %s\n" % aarFile[-1].name)

    aarFile[-1].write(articleUnit)
    aarFileLength[-1] += articleUnitLength
    articlePointer += articleUnitLength
    
    if header["article_count"] % 100 == 0:
        sys.stderr.write("\r" + str(header["article_count"]))
    header["article_count"] += 1

def makeFullIndex():
    global trailerLength
    global aarFile, aarFileLength
    global index1Length, index2Length
    global header
    
    count = 0

    for item in sortex:
        if count % 100 == 0:
            sys.stderr.write("\r" + str(count))
        count = count + 1
        sortkey, title, redirectTitle = item.split("___", 3)
        if redirectTitle:
            sys.stderr.write("Redirect: %s %s\n" % (repr(title), repr(redirectTitle)))
            target = redirectTitle
        else:
            target = title
        try:
            articlePointer = long(indexDb[target])
            for fileno in range(1, len(aarFile)):
                if articlePointer < aarFileLength[fileno]:
                    break
                articlePointer -= aarFileLength[fileno]
            index1Unit = struct.pack('LLL', long(index2Length), long(fileno), long(articlePointer))
            index1.write(index1Unit)
            index1Length += len(index1Unit)
            index2Unit = struct.pack("L", long(len(title))) + title
            index2.write(index2Unit)
            index2Length += len(index2Unit)
            header["index_count"] += 1
            sys.stderr.write("sorted: %s %i %i\n" % (title, fileno, articlePointer))
            #sys.stderr.write("count: %i\n" % header["index_count"])
        except KeyError:
            sys.stderr.write("Redirect not found: %s %s\n" % (repr(title), repr(redirectTitle)))
    
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
#aarFileLengthMax = 10000

indexDbTempdir = tempfile.mkdtemp()
indexDbFullname = os.path.join(indexDbTempdir, "index.db")
indexDb = anydbm.open(indexDbFullname, 'n')

index1 = tempfile.NamedTemporaryFile()
index2 = tempfile.NamedTemporaryFile()
index1Length = 0
index2Length = 0

articlePointer = 0L

header["article_count"] =  0
header["index_count"] =  0

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
sys.stderr.write("count x: %s\n" % repr(header["index_count"]))

sys.stderr.write("Sorting index...\n")

sortex.sort()
	
sys.stderr.write("Writing temporary indexes...\n")

makeFullIndex()

sortex.cleanup()

indexDb.close()
os.remove(indexDbFullname)
os.rmdir(indexDbTempdir)

combineFiles = False
header["file_count"] = len(aarFile)
if 100 + index1Length + index2Length + aarFileLength[-1] < aarFileLengthMax:
    header["file_count"] -= 1
    combineFiles = True
header["file_count"] = "%06i" % header["file_count"]

sys.stderr.write("Composing header...\n")

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

header["index1_length"] = index1Length
header["index2_length"] = index2Length

header["index1_offset"] = "%012i" % 0
header["index2_offset"] = "%012i" % 0
header["article_offset"] = "%012i" % 0

jsonText = compactjson.dumps(header)

header["index1_offset"] = "%012i" % (5 + 8 + len(jsonText))
header["index2_offset"] = "%012i" % (5 + 8 + len(jsonText) + index1Length)
header["article_offset"] = "%012i" % (5 + 8 + len(jsonText) + index1Length + index2Length)

sys.stderr.write("Writing header...\n")

jsonText = compactjson.dumps(header)

aarFile[0].write("aar10")
aarFileLength[0] += 5

aarFile[0].write("%08i" % len(jsonText))
aarFileLength[0] += 8
	
aarFile[0].write(jsonText)
aarFileLength[0] += len(jsonText)

sys.stderr.write("Writing index 1...\n")

index1.flush()
index1.seek(0)
writeCount = 0
while 1:
    if writeCount % 100 == 0:
        sys.stderr.write("\r" + str(writeCount))
    unit = index1.read(12)
    if len(unit) == 0:
        break
    index2ptr, fileno, offset = struct.unpack("LLL", unit)
    if combineFiles and fileno == len(aarFile) - 1:
        fileno = 0L
    unit = struct.pack("LLL", index2ptr, fileno, offset) 
    writeCount += 1
    aarFile[0].write(unit)
    aarFileLength[0] += 12
sys.stderr.write("\r" + str(writeCount) + "\n")
index1.close()

sys.stderr.write("Writing index 2...\n")

index2.flush()
index2.seek(0)
writeCount = 0
while 1:
    if writeCount % 100 == 0:
        sys.stderr.write("\r" + str(writeCount))
    unitLengthString = index2.read(4)
    if len(unitLengthString) == 0:
        break
    writeCount += 1
    unitLength = struct.unpack("L", unitLengthString)[0]
    unit = index2.read(unitLength)
    aarFile[0].write(unitLengthString + unit)
    aarFileLength[0] += 4 + unitLength
sys.stderr.write("\r" + str(writeCount) + "\n")
index2.close()

writeCount = 0L

if combineFiles:
    sys.stderr.write("Combining output files\n")
    aarFile[-1].flush()
    aarFile[-1].seek(0)
    while 1:
        if writeCount % 100 == 0:
            sys.stderr.write("\r" + str(writeCount))
        unitLengthString = aarFile[-1].read(4)
        if len(unitLengthString) == 0:
            break
        writeCount += 1
        unitLength = struct.unpack("i", unitLengthString)[0]
        unit = aarFile[-1].read(unitLength)
        aarFile[0].write(unitLengthString + unit)
        aarFileLength[0] += 4 + unitLength
    sys.stderr.write("\r" + str(writeCount) + "\n")
    os.remove(aarFile[-1].name)    
    aarFile.pop()

sys.stderr.write("Created %i output files\n" % len(aarFile))
for f in aarFile:
    f.close
    
sys.stderr.write("Done.\n")




