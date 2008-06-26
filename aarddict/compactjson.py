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

Copyright (C) 2008  Jeremy Mortis, Igor Tkach
"""

import re
import types
import array

quotedCharsRe = re.compile(r"([ ,\[\]\{\}\(\)\"\\:])")

def dump_list(item):
    r = ""
    for element in item:
        if r: r += ","
        r += dumps(element)
    return "[%json]" % r    

def dump_tuple(item):
    r = ""
    for element in item:
        if r: r += ","
        r += dumps(element)
    return "(%json)" % r

def dump_dict(item):
    r = ""
    for k, v in item.iteritems():
        if r: r += ","
        r = "".join([r, dumps(k), ":", dumps(v)])
    return "{%json}" % r if r else ''   

def escape(item):
    if quotedCharsRe.search(item):
        item = '"' + item.replace("\\", "\\\\").replace('"', '\\\"') + '"'
    return item

type_map = {types.ListType : dump_list,
            types.DictType : dump_dict,
            types.TupleType : dump_tuple,
            types.IntType : str,
            types.LongType : str,
            types.StringType : escape,
            types.UnicodeType : escape
            }

def dumps(item):
    return type_map[type(item)](item)

def loads(item):
    global s, slen, offset
    if not item:
        return None
    return Parser(item).parse()

class Parser():
    
    def __init__(self, item):
        self.json = array.array("c", item)
        self.slen = len(self.json)
        self.offset = 0
        self.parse_map = {'"':  self.parseDoubleQuotedString,
                          "'":  self.parseSingleQuotedString,
                          '[':  self.parseList,
                          '{':  self.parseDict,
                          '(':  self.parseTuple             
                          }


    def parse(self):
        #print "parse:", offset, json[offset]
        while True:
            if self.offset >= self.slen:
                return ""
            if not self.json[self.offset].isspace():
                break
            self.offset +=1
        of = self.json[self.offset]
        value = self.parse_map.get(of, self.parseUnquotedString)()
        while self.offset < self.slen and of.isspace():
            self.offset +=1
        #print "value:", value
        return value

    def parseList(self):
        #print "parse list:", offset
        self.offset += 1
        if (self.offset >= self.slen) or (self.json[self.offset] == "]"):
            return []
        listValue = []
        while True:
            listValue.append(self.parse())
            if (self.offset >= self.slen) or (self.json[self.offset] == "]"):
                self.offset += 1
                return listValue
            self.offset += 1

    def parseTuple(self):
        #print "parse tuple:", offset
        self.offset += 1
        if (self.offset >= self.slen) or (self.json[self.offset] == ")"):
            return ()
        tupleValue = []
        while True:
            tupleValue.append(self.parse())
            if (self.offset >= self.slen) or (self.json[self.offset] == ")"):
                self.offset += 1
                return tuple(tupleValue)
            self.offset += 1

    def parseDict(self):
        #print "parse dict:", offset
        self.offset += 1
        if (self.offset >= self.slen) or (self.json[self.offset] == "}"):
            return {}
        dictValue = {}
        while True:
            key = self.parse()
            if self.json[self.offset] != ":":
                print self.json
                print str(self.json[self.offset-20:self.offset+20])
                print "                    ^"
                raise Exception("colon expected")
            self.offset += 1
            dictValue[key] = self.parse()
            if (self.offset >= self.slen) or (self.json[self.offset] == "}"):
                self.offset += 1
                return dictValue
            self.offset += 1

    def parseSingleQuotedString(self):
        #print "parse sqs:", offset
        start = self.offset
        while True:
            self.offset += 1
            if self.offset >= self.slen:
                break
            if self.json[self.offset] == "\\":
                self.json.pop(self.offset)
                self.slen -= 1
            elif self.json[self.offset] == "'":
                self.offset += 1
                break
        return self.json[start+1:self.offset-1].tostring()


    def parseDoubleQuotedString(self):
        #print "parse dqs:", offset
        start = self.offset
        while True:
            self.offset += 1
            if self.offset >= self.slen:
                break
            if self.json[self.offset] == "\\":
                self.json.pop(self.offset)
                self.slen -= 1
            elif self.json[self.offset] == '"':
                self.offset += 1
                break
        return self.json[start+1:self.offset-1].tostring()

    def parseUnquotedString(self):
        #print "parse uqs:", offset
        start = self.offset
        while True:
            if self.offset >= self.slen:
                break
            if self.json[self.offset] == "\\":
                self.json.pop(self.offset)
                self.slen -= 1
                self.offset += 1
            elif self.json[self.offset] in [",", ":", "]", ")", "}"]:
                break
            self.offset += 1
        t = self.json[start:self.offset].tostring()
        return int(t) if t.isdigit() else t 

               
if __name__ == '__main__':

    #import simplejson
    x = { "a" : "b", "départment\nof silly walks" : "the \"witch\" ain't [here]", "empty" : "", "n\\3" : 1 }
    item = [ '1', "\"\"boogy\"\"", "spa ace", ["4x", "5", 6], x, {}]

    #item = {1:2, 3:[4,5,(  6  ,7)]}

    #item = ['This is the d\xc3\xa9partment"json\n\nthis\nand that', 
    #[['h1', 0, 24, {}], ['i', 31, 34, {}], ['b', 35, 39, {}], ['a', 26, 39, {'href': 'the red'}]]]
    
    print item
    #print simplejson.dumps(item)
    s = dumps(item)
    print s
    print "0....+....0....+....0....+....0....+....0"
    
    newitem = loads(s)
    print newitem

    if item == newitem:
        print "Equals"
    else:
        print "Not equals"






