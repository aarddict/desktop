#!/usr/bin/python
# coding: utf-8
"""
This file is part of AardDict (http://code.google.com/p/aarddict) - 
a dictionary for Nokia Internet Tablets. 

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

import compactjson
import bz2
import struct

RECORD_LEN_STRUCT_FORMAT = '>L'
RECORD_LEN_STRUCT_SIZE = struct.calcsize(RECORD_LEN_STRUCT_FORMAT)

class Article:

    def __init__(self, title = "", text = "", tags = None):
        self.title = title
        self.text = text
        self.tags = [] if tags is None else tags

    def __str__(self):
        s = "title: " + repr(self.title) + "\n"
        s = s + "text: " + repr(self.text) + "\n"
        for tag in self.tags:
            s = s + "tag: " + str(tag) + "\n"
        return s
        
    def fromFile(self, file, offset):
        file.seek(offset)
        record_length = struct.unpack(RECORD_LEN_STRUCT_FORMAT, file.read(RECORD_LEN_STRUCT_SIZE))[0]
        s = file.read(record_length)
        s = bz2.decompress(s)
        self.text, tagList = compactjson.loads(s)
        self.tags = [Tag(name, start, end, attrs) for name, start, end, attrs in tagList]


class Tag:

    def __init__(self, name = "", start = -1, end = -1, attributes = {}):
        self.name = name
        self.start = start
        self.end = end
        self.attributes = attributes

    def __str__(self):
        return self.name + " " + str(self.start) + " " +  str(self.end) + " " + repr(self.attributes)
    
    def toList(self):
        return [self.name, self.start, self.end, self.attributes]

    def fromList(self, list):
        self.name, self.start, self.end, self.attributes = list
        if self.attributes == "":
            self.attributes = {}
        






