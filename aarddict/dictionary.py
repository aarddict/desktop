#!/usr/bin/python
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

import sys
import struct
import bz2
import compactjson 
from collections import defaultdict
from itertools import chain

RECORD_LEN_STRUCT_FORMAT = '>L'
RECORD_LEN_STRUCT_SIZE = struct.calcsize(RECORD_LEN_STRUCT_FORMAT)

from PyICU import Locale, Collator
ucollator =  Collator.createInstance(Locale(''))
ucollator.setStrength(Collator.PRIMARY)

def key(s):
    return ucollator.getCollationKey(s).getByteArray()

class Word:
    def __init__(self, word, article_location=(None, None)):
        self.article_location = article_location            
        self.word = word
        try:
            self.unicode = self.word.decode('utf-8')
        except UnicodeDecodeError:
            self.unicode = u"error"
            sys.stderr.write("Unable to decode: %s\n" % repr(self.word))

    def __str__(self):
        return self.word

    def __cmp__(self, other):
        return cmp(self._key(), other._key())
    
    def __unicode__(self):
        return self.unicode
    
    def _key(self):
        return key(self.unicode)    
        
    def startswith(self, other):
        k1 = key(self.unicode[:len(other.unicode)])
        k2 = key(other.unicode)
        return k1 == k2    

class Dictionary:         

    def __init__(self, file_name):    
        self.file_name = file_name
        self.file = []
        self.article_offset = []
        self.file.append(open(file_name, "rb"));
        self.metadata = self.get_file_metadata(self.file[0])
        self.word_list = None
        self.index1_offset = self.metadata["index1_offset"]
        self.index2_offset = self.metadata["index2_offset"]
        self.index_count = self.metadata["index_count"]
        self.article_count = self.metadata["article_count"]
        self.article_offset.append(self.metadata["article_offset"])
                
        self.index_language = self.metadata.get("index_language", "")    
        locale_index_language = Locale(self.index_language).getLanguage()
        if locale_index_language:
            self.index_language = locale_index_language
            
        self.article_language = self.metadata.get("article_language", "")
        locale_article_language = Locale(self.index_language).getLanguage()
        if locale_article_language:
            self.article_language = locale_article_language
        
        for i in range(1, self.metadata["file_count"]):
            self.file.append(open(file_name[:-2] + ("%02i" % i), "rb"))
            extMetadata = self.get_file_metadata(self.file[-1])
            self.article_offset.append(extMetadata["article_offset"])
            if extMetadata["timestamp"] != self.metadata["timestamp"]:
                raise Exception(self.file[-1].name() + " has a timestamp different from self.file[0].name()")
            
    title = property(lambda self: self.metadata.get("title", ""))
    version = property(lambda self: self.metadata.get("aarddict_version", ""))
    description = property(lambda self: self.metadata.get("description", ""))
    copyright = property(lambda self: self.metadata.get("copyright", ""))
    article_count = property(lambda self: self.metadata.get("article_count", 0))

    def __eq__(self, other):
        return self.key() == other.key()
    
    def __str__(self):
        return self.file_name
    
    def __hash__(self):
        return self.key().__hash__()

    def key(self):
        return (self.title, self.version, self.file_name)

    def get_file_metadata(self, f):
        if f.read(3) != "aar":
            f.close()
            raise Exception(f.name + " is not a recognized aarddict dictionary file")
        if f.read(2) != "01":
            f.close()
            raise Exception(f.name + " is not compatible with this viewer")
        metadataLength = int(f.read(8))
        metadataString = f.read(metadataLength)
        metadata = compactjson.loads(metadataString)
        return metadata
       
    def find_index_entry(self, word):
        low = 0
        high = self.index_count
        probe = -1
        while True:
            prevprobe = probe
            probe = low + int((high-low)/2)
            if (probe == prevprobe):
                return low 
            probeword = self.read_full_index_item(probe)
            #sys.stderr.write("Probeword: %i %i<->%i %s\n" % (probe, low, high, str(probeword)))
            if probeword == word:
                return probe
            elif probeword > word:
                high = probe
            else:
                low = probe

    def lookup(self, start_string):
        start_word = Word(start_string)
        next_ptr = self.find_index_entry(start_word)
        word = self.read_full_index_item(next_ptr)
        # the found word might not be the first with that collation key
        while word.startswith(start_word) and (next_ptr > 0):
            #sys.stderr.write("Back: " + str(word) + "\n")
            next_ptr -= 1
            word = self.read_full_index_item(next_ptr)
        while True:
            #sys.stderr.write("Word: " + str(word) + "\n")
            if word.startswith(start_word):
                yield word
            else:
                #sys.stderr.write("Tossed: " + str(word) + "\n")
                if (word > start_word):
                    raise StopIteration
            next_ptr += 1
            if next_ptr >= self.index_count:
                raise StopIteration
            word = self.read_full_index_item(next_ptr)

                
    def read_full_index_item(self, pos):
        self.file[0].seek(self.index1_offset + (pos * 12))
        keyPos, fileno, article_unit_ptr = struct.unpack(">LLL", self.file[0].read(12))
        self.file[0].seek(self.index2_offset + keyPos)
        keyLen = struct.unpack(">L", self.file[0].read(4))[0]
        key = self.file[0].read(keyLen)
        article_location = (fileno, 
                            self.article_offset[fileno] + article_unit_ptr)
        word = Word(key, article_location)
        return word
        
    def read_article(self, location):
        fileno, offset = location
        file = self.file[fileno]
        file.seek(offset)
        record_length = struct.unpack(RECORD_LEN_STRUCT_FORMAT, file.read(RECORD_LEN_STRUCT_SIZE))[0]
        raw_article = bz2.decompress(file.read(record_length))        
        return raw_article

    def close(self):
        for f in self.file:
            f.close()        
            
class DictFormatError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)      

class WordLookup:
    def __init__(self, word, dict=None, article_ptr=None):
        self.word = word
        self.lookup = {}
        if dict and article_ptr:
            self.add_article(dict, article_ptr)
        
    def add_article(self, dict, article_ptr):
        self.lookup[dict] = article_ptr
        
    def add_articles(self, other):
        self.lookup.update(other.lookup)        
        
    def __str__(self):
        return self.word

    def __repr__(self):
        return self.word
    
    def __unicode__(self):
        return self.word.decode('utf-8')
        
    def read_articles(self):
        return [(dict,dict.read_article(article_ptr)) 
                for dict, article_ptr in self.lookup.iteritems()]
        
class DictionaryCollection:
    
    def __init__(self):
        self.dictionaries = defaultdict(list)
    
    def add(self, dict):
        self.dictionaries[dict.index_language].append(dict)
        
    def has(self, dict):
        lang_dicts = self.dictionaries[dict.index_language]
        return lang_dicts.count(dict) == 1
    
    def remove(self, dict):     
        word_lang = dict.index_language   
        self.dictionaries[word_lang].remove(dict)
        if len(self.dictionaries[word_lang]) == 0:
            del self.dictionaries[word_lang]
    
    def __len__(self):
        lengths = [len(l) for l in self.dictionaries.itervalues()]
        return reduce(lambda x, y: x + y, lengths, 0)
        
    def all(self):
        return chain(*self.dictionaries.itervalues())
    
    def langs(self):
        return self.dictionaries.keys()
    
    def lookup(self, lang, start_word, max_from_one_dict=50):
        for dict in self.dictionaries[lang]:
            count = 0
            for item in dict.lookup(start_word):
                yield WordLookup(item.word, dict, item.article_location)
                count += 1
                if count >= max_from_one_dict: break            