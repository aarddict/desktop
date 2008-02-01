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

from struct import unpack
import types
import compactjson
import article
import pyuca
import struct
import sys

class Word:
    def __init__(self, dictionary, word, collation_key = None):
        self.dictionary = dictionary
        self.encoding = dictionary.character_encoding
        self.collator = dictionary.collator
        self.article_ptr = None
        self.unicode = None
        self.word = None
        self.collation_key = collation_key
        self.word_lang = dictionary.index_language
        self.article_lang = dictionary.article_language
        
        if type(word) is types.UnicodeType:
            self.unicode = word
            self.word = self.unicode.encode(self.encoding)
        else:
            self.word = word
            try:
                self.unicode = self.word.decode(self.encoding)
            except UnicodeDecodeError:
                self.unicode = u"error"
                sys.stderr.write("Unable to decode: " + self.encoding + " " + word + "\n")

        if not self.collation_key: 
            self.collation_key = self.dictionary.collator.getCollationKey(self.unicode)

    def __str__(self):
        return self.word

    def __eq__(self, other):
        return self.collation_key == other.collation_key

    def __cmp__(self, other):
        return cmp(self.collation_key, other.collation_key)

    def __unicode__(self):
        return self.unicode
        
    def startswith(self, other):
        return self.collation_key.startswith(other.collation_key)
    
    def getArticle(self):
        return self.dictionary.read_article(self.article_ptr)

class Dictionary:         

    def __init__(self, file_name, collator):    
        self.file_name = file_name
        self.file = open(file_name, "rb");
        self.fileid = self.file.read(5);
        if self.fileid != "aar10":
            self.file.close()
            raise Exception(file_name + " is not a recognized aarddict dictionary file")
        self.metadataLength = int(self.file.read(8));
        self.metadataString = self.file.read(self.metadataLength)
        self.metadata = compactjson.loads(self.metadataString)
        self.collator = collator
        self.word_list = None
        self.index_start = self.metadata["index_offset"]
        self.index_end = self.index_start + self.metadata["index_length"]
        self.article_offset = self.metadata["article_offset"]
        
    title = property(lambda self: self.metadata.get("title", "unknown"))
    index_language = property(lambda self: self.metadata.get("index_language", "unknown"))
    article_language = property(lambda self: self.metadata.get("article_language", "unknown"))    
    version = property(lambda self: self.metadata.get("aarddict_version", "unknown"))
    character_encoding = property(lambda self: self.metadata.get("character_encoding", "utf-8"))

    def __eq__(self, other):
        return self.key() == other.key()
    
    def __str__(self):
        return self.file_name
    
    def __hash__(self):
        return self.key().__hash__()

    def key(self):
        return (self.title, self.version, self.file_name)
       
    def find_index_entry(self, word):
        low = self.index_start
        high = self.index_end
        probe = -1
        while True:
            prevprobe = probe
            probe = low + int((high-low)/2)
            probe = self.findword(probe)
            if (probe == prevprobe) or (probe == -1):
                return low
            next_offset, probeword = self.read_full_index_item(probe)
            if probeword == word:
                return probe
            if probeword > word:
                high = probe
            else:
                low = probe

    def findword(self, pos):
        self.file.seek(pos)
        b = ""
        while True:
            remaining = self.index_end - pos - len(b) - 35
            if not remaining:
                return -1
            b = ''.join([b, self.file.read(min(128, remaining))])
            start = b.find("\xFD\xFD\xFD\xFD")
            if start >= 0:
                return pos + start

    
    def get_word_list_iter(self, start_string):
        start_word = Word(self, start_string)
        next_ptr = self.find_index_entry(start_word)
        while True:
            if next_ptr >= self.index_end:
                raise StopIteration
            next_offset, word = self.read_full_index_item(next_ptr)
            #sys.stderr.write("Word: " + str(word) + "\n")
            if word.startswith(start_word):
                yield word
            else:
                #sys.stderr.write("Tossed: " + str(word) + "\n")
                if (word > start_word):
                    raise StopIteration
            next_ptr += next_offset

                
    def read_full_index_item(self, pointer):
        f = self.file
        f.seek(pointer)
        sep = f.read(4)
        headerpack = 'LLhL'
        header_length = struct.calcsize(headerpack)
        s = f.read(header_length)
        next_word_offset, prev_word_offset, fileno, article_ptr = struct.unpack(headerpack, s)
        s = f.read(next_word_offset - header_length - 4)
        key, word = s.split("___", 2)
        collation_key = pyuca.CollationKey()
        collation_key.set(key)
        word = Word(self, word, collation_key = collation_key)
        word.article_ptr = article_ptr + self.article_offset
        return next_word_offset, word
        
    def read_article(self, pointer):
        a = article.Article()
        a.fromFile(self.file, pointer)
        return a

    def close(self):
        self.file.close()        

if __name__ == '__main__':

        import sys

        if len(sys.argv) != 3:
            sys.stderr.write("Usage: " + sys.argv[0] + " aarfile word\n")
            sys.exit()
        
        collator1 = pyuca.Collator("allkeys.txt", strength = 1)
        d = Dictionary(sys.argv[1], collator1)

        print d.metadata
        
        i = d.get_word_list_iter(sys.argv[2])
        for word in i:
            print word, "==>",  word.getArticle()

        print "Done."
