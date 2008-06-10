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

from aarddict import compactjson
from sortexternal import SortExternal
from htmlparser import HTMLParser
import sys, bz2, struct, os, tempfile, shelve, datetime, optparse
import aarddict.pyuca
from mwlib import cdbwiki

def getOptions():
    usage = "usage: %prog [options] "
    parser = optparse.OptionParser(version="%prog 1.0", usage=usage)

    parser.add_option(
        '-o', '--output-file',
        default='',
        help='Output file (mandatory)'
        )
    parser.add_option(
        '-i', '--input-file',
        default='',
        help='Input file (default stdin)'
        )
    parser.add_option(
        '-f', '--input-format',
        default='none',
        help='Input format:  mediawiki or xdxf'
        )
    parser.add_option(
        '-t', '--templates',
        default='none',
        help='Template definitions database'
        )

    return parser

def createArticleFile():
    global header
    global aarFile, aarFileLength
    global options

    if options.output_file[-3:] == "aar":
        extFilenamePrefix = options.output_file[:-2]
    else:
        extFilenamePrefix = options.output_file + ".a"

    aarFile.append(open(extFilenamePrefix + ("%02i" % len(aarFile)), "w+b", 4096))
    aarFileLength.append(0)
    sys.stderr.write("New article file: %s\n" % aarFile[-1].name)
    extHeader = {}
    extHeader["article_offset"] = "%012i" % 0
    extHeader["major_version"] = header["major_version"]
    extHeader["minor_version"] = header["minor_version"]
    extHeader["timestamp"] = header["timestamp"]
    extHeader["file_sequence"] = len(aarFile) - 1
    jsonText = compactjson.dumps(extHeader)
    extHeader["article_offset"] = "%012i" % (5 + 8 + len(jsonText))
    jsonText = compactjson.dumps(extHeader)
    aarFile[-1].write("aar%02i" % header["major_version"])
    aarFileLength[-1] += 5
    aarFile[-1].write("%08i" % len(jsonText))
    aarFileLength[-1] += 8
    aarFile[-1].write(jsonText)
    aarFileLength[-1] += len(jsonText)

def handleArticle(title, text):
    global header
    global articlePointer
    global aarFile, aarFileLength
    
    if (not title) or (not text):
        #sys.stderr.write("Skipped blank article: \"%s\" -> \"%s\"\n" % (title, text))
        return

    collationKeyString4 = collator4.getCollationKey(title).getBinaryString()

    if text.startswith("#REDIRECT"):
        redirectTitle = text[10:]
        sortex.put(collationKeyString4 + "___" + title + "___" + redirectTitle)
        sys.stderr.write("Redirect: %s %s\n" % (title, text))
        return
    
    #sys.stderr.write("Text: %s\n" % text)
    parser = HTMLParser()
    parser.parseString(text)

    jsonstring = compactjson.dumps([parser.text.rstrip(), parser.tags])
    jsonstring = bz2.compress(jsonstring)
    #sys.stderr.write("write article: %i %i %s\n" % (articleTempFile.tell(), len(jsonstring), title))    

    sortex.put(collationKeyString4 + "___" + title + "___")
    
    articleUnit = struct.pack(">L", len(jsonstring)) + jsonstring
    articleUnitLength = len(articleUnit)
    if aarFileLength[-1] + articleUnitLength > aarFileLengthMax:
        createArticleFile()
        articlePointer = 0L
        
    aarFile[-1].write(articleUnit)
    aarFileLength[-1] += articleUnitLength

    if indexDb.has_key(title):
        sys.stderr.write("Duplicate key: %s\n" % title)
    else:
        #sys.stderr.write("Real article: %s\n" % title)
        indexDb[title] = (len(aarFile) - 1, articlePointer)

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
            #sys.stderr.write("Redirect: %s %s\n" % (repr(title), repr(redirectTitle)))
            target = redirectTitle
        else:
            target = title
        try:
            fileno, articlePointer = indexDb[target]
            index1Unit = struct.pack('>LLL', long(index2Length), long(fileno), long(articlePointer))
            index1.write(index1Unit)
            index1Length += len(index1Unit)
            index2Unit = struct.pack(">L", long(len(title))) + title
            index2.write(index2Unit)
            index2Length += len(index2Unit)
            header["index_count"] += 1
            sys.stderr.write("sorted: %s %i %i\n" % (title, fileno, articlePointer))
        except KeyError:
            sys.stderr.write("Redirect not found: %s %s\n" % (repr(title), repr(redirectTitle)))
    
    sys.stderr.write("\r" + str(count) + "\n")

#__main__

tempDir = tempfile.mkdtemp()

collator4 = aarddict.pyuca.Collator("aarddict/allkeys.txt")
collator4.setStrength(4)

collator1 = aarddict.pyuca.Collator("aarddict/allkeys.txt")
collator1.setStrength(1)

sortex = SortExternal()

header = {
    "character_encoding": "utf-8",
    "compression_type": "bz2",
    "major_version": 1,
    "minor_version": 0,
    "timestamp": str(datetime.datetime.utcnow()),
    "file_sequence": 0,
    "article_language": "en",
    "index_language": "en"
    }

sys.stderr.write("Parsing input file...\n")

optionsParser = getOptions()
options, args = optionsParser.parse_args()

if options.input_file:
    inputFile = open(options.input_file, "rb", 4096)
else:
    inputFile = sys.stdin

aarFile = []
aarFileLength = []

if not options.output_file:
    optionsParser.print_help()
    sys.exit()
    
aarFile.append(open(options.output_file, "w+b", 4096))
aarFileLength.append(0)

createArticleFile()

aarFileLengthMax = 4000000000

indexDbFullname = os.path.join(tempDir, "index.db")
indexDb = shelve.open(indexDbFullname, 'n')

if options.templates:
    templateDb = cdbwiki.WikiDB(options.templates)
else:
    templateDb = None
    
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
    p = MediaWikiParser(collator1, header, templateDb, handleArticle)
    p.parseFile(inputFile)

sys.stderr.write("\r" + str(header["article_count"]) + "\n")

sys.stderr.write("Sorting index...\n")

sortex.sort()
	
sys.stderr.write("Writing temporary indexes...\n")

makeFullIndex()

sortex.cleanup()

indexDb.close()
os.remove(indexDbFullname)
os.rmdir(tempDir)

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

header["article_language"] = languageCodeDict.get(header["article_language"].lower(), header["article_language"])
header["index_language"] = languageCodeDict.get(header["index_language"].lower(), header["index_language"])

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

aarFile[0].write("aar%02i" % header["major_version"])
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
    index2ptr, fileno, offset = struct.unpack(">LLL", unit)
    if combineFiles and fileno == len(aarFile) - 1:
        fileno = 0L
    unit = struct.pack(">LLL", index2ptr, fileno, offset) 
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
    unitLength = struct.unpack(">L", unitLengthString)[0]
    unit = index2.read(unitLength)
    aarFile[0].write(unitLengthString + unit)
    aarFileLength[0] += 4 + unitLength
sys.stderr.write("\r" + str(writeCount) + "\n")
index2.close()

writeCount = 0L

if combineFiles:
    sys.stderr.write("Appending %s to %s\n" % (aarFile[-1].name, aarFile[0].name))
    aarFile[-1].flush()
    aarFile[-1].seek(0)
    aarFile[-1].read(5)
    headerLength = int(aarFile[-1].read(8))
    aarFile[-1].read(headerLength)

    while 1:
        if writeCount % 100 == 0:
            sys.stderr.write("\r" + str(writeCount))
        unitLengthString = aarFile[-1].read(4)
        if len(unitLengthString) == 0:
            break
        writeCount += 1
        unitLength = struct.unpack(">L", unitLengthString)[0]
        unit = aarFile[-1].read(unitLength)
        aarFile[0].write(unitLengthString + unit)
        aarFileLength[0] += 4 + unitLength
    sys.stderr.write("\r" + str(writeCount) + "\n")
    sys.stderr.write("Deleting %s\n" % aarFile[-1].name)
    os.remove(aarFile[-1].name)    
    aarFile.pop()

sys.stderr.write("Created %i output file(s)\n" % len(aarFile))
for f in aarFile:
    f.close
    
sys.stderr.write("Done.\n")




