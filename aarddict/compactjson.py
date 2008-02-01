#!/usr/bin/python
# coding: utf-8

"""
compactjson.py:  Read/write a compact form of JSON

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2008  Jeremy Mortis
"""

import re
import types
import array

quotedCharsRe = re.compile(r"([ ,\[\]\{\}\(\)\"\\:])")

def dumps(item):
    if type(item) is types.ListType:
        r = ""
        for element in item:
            if r:
                r = r + ","
            r = r + dumps(element)
        return "[" + r + "]"
    if type(item) is types.TupleType:
        r = ""
        for element in item:
            if r:
                r = r + ","
            r = r + dumps(element)
        return "(" + r + ")"
    if type(item) is types.DictType:
        r = ""
        for element in item.iteritems():
            if r:
                r = r + ","
            r = "".join([r, dumps(element[0]), ":", dumps(element[1])])
        if r:
            return "{" + r + "}"
        else:
            return ""
    if type(item) is types.IntType:
        return str(item)
    if type(item) is types.LongType:
        return str(item)
    if type(item) is types.StringType:
        return escape(item)

def escape(item):
    if quotedCharsRe.search(item):
        item = '"' + item.replace("\\", "\\\\").replace('"', '\\\"') + '"'
    return item

def loads(item):
    global s, offset
    if not item:
        return ""
    s = array.array("c", item)
    offset = 0
    return parse()

def parse():
    global s, offset
    #print "parse:", offset, s[offset]
    while True:
        if offset >= len(s):
            return ""
        if not s[offset].isspace():
            break
        offset +=1
    if s[offset] == "[":
        value = parseList()
    elif s[offset] == "'":
        value = parseSingleQuotedString()
    elif s[offset] == '"':
        value = parseDoubleQuotedString()
    elif s[offset] == "(":
        value = parseTuple()
    elif s[offset] == "{":
        value = parseDict()
    else:
        value = parseUnquotedString()
    while offset < len(s) and s[offset].isspace():
        offset +=1
    #print "value:", value
    return value

def parseList():
    global s, offset
    #print "parse list:", offset
    offset += 1
    if (offset >= len(s)) or (s[offset] == "]"):
        return []
    listValue = []
    while True:
        listValue.append(parse())
        if (offset >= len(s)) or (s[offset] == "]"):
            offset += 1
            return listValue
        offset += 1

def parseTuple():
    global s, offset
    #print "parse tuple:", offset
    offset += 1
    if (offset >= len(s)) or (s[offset] == ")"):
        return ()
    tupleValue = []
    while True:
        tupleValue.append(parse())
        if (offset >= len(s)) or (s[offset] == ")"):
            offset += 1
            return tuple(tupleValue)
        offset += 1

def parseDict():
    global s, offset
    #print "parse dict:", offset
    offset += 1
    if (offset >= len(s)) or (s[offset] == "}"):
        return {}
    dictValue = {}
    while True:
        key = parse()
        if s[offset] != ":":
            print s
            print str(s[offset-20:offset+20])
            print "                    ^"
            raise Exception("colon expected")
        offset += 1
        dictValue[key] = parse()
        if (offset >= len(s)) or (s[offset] == "}"):
            offset += 1
            return dictValue
        offset += 1

def parseSingleQuotedString():
    global s, offset
    #print "parse sqs:", offset
    value = []
    while True:
        offset += 1
        if offset >= len(s):
            return "".join(value)
        if s[offset] == "\\":
            offset += 1
        elif s[offset] == "'":
            offset += 1
            return "".join(value)
        value.append(s[offset])

def parseDoubleQuotedString():
    global s, offset
    #print "parse dqs:", offset
    value = []
    while True:
        offset += 1
        if offset >= len(s):
            return "".join(value)
        if s[offset] == "\\":
            offset += 1
        elif s[offset] == '"':
            offset += 1
            return "".join(value)
        value.append(s[offset])

def parseUnquotedString():
    global s, offset
    #print "parse uqs:", offset
    value = []
    while True:
        if offset >= len(s):
            break
        if s[offset] == "\\":
            offset += 1
        elif s[offset] in [",", ":", "]", ")", "}"]:
            break
        value.append(s[offset])
        offset += 1
    t = "".join(value)
    if t.isdigit():
        return int(t)
    else:
        return t
               
if __name__ == '__main__':

    #import simplejson
    x = { "a" : "b", "départment\nof silly walks" : "the \"witch\" ain't [here]", "empty" : "", "n\\3" : 1 }
    item = [ '1', "boogy", "spa ace", ["4x", "5", 6], x, {}]

    #item = {1:2, 3:[4,5,(  6  ,7)]}

    item = ['This is the d\xc3\xa9partment"s\n\nthis\nand that', 
    [['h1', 0, 24, {}], ['i', 31, 34, {}], ['b', 35, 39, {}], ['a', 26, 39, {'href': 'the red'}]]]
    
    
    print item
    #print simplejson.dumps(item)
    s = dumps(item)
    print s
    print "0....+....0....+....0....+....0....+....0"
    
    f = open("junk")
    #s = f.read(100000)
    newitem = loads(s)
    print newitem
    #print len(newitem)
    if item == newitem:
        print "Equals"
    else:
        print "Not equals"






