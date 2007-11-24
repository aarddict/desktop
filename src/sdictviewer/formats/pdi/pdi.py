"""
This file is part of SDict Viewer (http://sdictviewer.sf.net) - 
a dictionary application that allows to use data bases 
in AXMASoft's open dictionary format. 

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Portions Copyright (C) 2006-2007 Igor Tkach
Portions Copyright (C) 2007      Jeremy Mortis (mortis@ucalgary.ca)

"""
import zlib
import bz2
from struct import unpack
import types
import sdictviewer
from sdictviewer.dictutil import *


class GzipCompression:
    
    def __str__(self):
        return "gzip"
    
    def decompress(self, string):
        return zlib.decompress(string)
    
class Bzip2Compression:    
    
    def __str__(self):
        return "bzip2"
    
    def decompress(self, string):
        return bz2.decompress(string)
    
class NoCompression:
    
    def __str__(self):
        return "no compression"
        
    def decompress(self, string):
        return string
    
def read_raw(s, fe):
    return s[fe.offset:fe.offset + fe.length]

def read_str(s, fe):
    raw = read_raw(s, fe)
    return raw.replace('\x00', '');

def read_int(s, fe = None):      
    raw = read_raw(s, fe) if fe else s
    return unpack('<I', raw)[0]    

def read_short(raw):  
    return unpack('<H', raw)[0]    

def read_byte(raw):  
    return unpack('<B', raw)[0]    

class FormatElement:
    def __init__(self, offset, length, elementType = None):
        self.offset = offset
        self.length = length
        self.elementType = elementType

class Header:
                    
    f_signature = FormatElement(0x0, 4)
    f_input_lang = FormatElement(0x4, 3)
    f_output_lang = FormatElement(0x7, 3)
    f_compression = FormatElement(0xa, 1)
    f_num_of_words = FormatElement(0xb, 4)
    f_length_of_short_index=FormatElement(0xf, 4)
    f_title=FormatElement(0x13, 4)
    f_copyright=FormatElement(0x17, 4)
    f_version=FormatElement(0x1b, 4)
    f_short_index=FormatElement(0x1f, 4)
    f_full_index=FormatElement(0x23, 4)
    f_articles=FormatElement(0x27, 4)
                        
    def parse(self, str):
        self.signature = read_str(str, self.f_signature)
        if self.signature != 'pdi!':
            raise DictFormatError, "Not a valid pdi dictionary"
        self.word_lang = read_str(str, self.f_input_lang)
        self.article_lang = read_str(str, self.f_output_lang)
        self.short_index_length = read_int(str, self.f_length_of_short_index)
        comp_and_index_levels_byte = read_byte(read_raw(str, self.f_compression)) 
        self.compressionType = comp_and_index_levels_byte & int("00001111", 2)
        self.short_index_depth = comp_and_index_levels_byte >> 4        
        self.num_of_words = read_int(str, self.f_num_of_words)
        self.title_offset = read_int(str, self.f_title)
        self.copyright_offset = read_int(str, self.f_copyright)
        self.version_offset = read_int(str, self.f_version)
        self.articles_offset = read_int(str, self.f_articles)
        self.short_index_offset = read_int(str, self.f_short_index)
        self.full_index_offset = read_int(str, self.f_full_index)
    
compressions = {0:NoCompression(), 1:GzipCompression(), 2:Bzip2Compression()}
        
class Word:
    def __init__(self, dictionary, word):
        self.dictionary = dictionary
        self.encoding = dictionary.encoding
        self.collator = dictionary.collator
        self.article_ptr = None
        self.unicode = None
        self.word = None
        self.sortkey = None
        self.word_lang = dictionary.header.word_lang
        self.article_lang = dictionary.header.article_lang
        
        if type(word) is types.UnicodeType:
            self.unicode = word
            self.word = self.unicode.encode(self.encoding)
        else:
            self.word = word
            try:
                self.unicode = self.word.decode(self.encoding)
            except UnicodeDecodeError:
                self.unicode = "error".decode(self.encoding)
                print "Unable to decode:", self.encoding, word

        if self.collator == None:
            self.sortkey = str(self)
        else:
            self.sortkey = self.collator.sort_key(self.unicode)

    def __str__(self):
        return self.word

    def __eq__(self, other):
        return self.sortkey == other.sortkey

    def __cmp__(self, other):
        return cmp(self.sortkey, other.sortkey)

    def __unicode__(self):
        return self.unicode
        
    def startswith(self, s):
        ssk = s.sortkey
        return self.sortkey[0:len(ssk)] == ssk
    
    def get_article(self):
        return self.dictionary.read_article(self.article_ptr)

    
class Dictionary:         
    
    def __init__(self, file_name):    
        self.file_name = file_name
        self.file = open(file_name, "rb");
        self.header = Header()
        self.header.parse(self.file.read(43))  
        self.compression = compressions[self.header.compressionType]    
        self.title = self.read_unit(self.header.title_offset)  
        self.version = self.read_unit(self.header.version_offset)  
        self.copyright = self.read_unit(self.header.copyright_offset)
        self.encoding = "utf-8"
        self.collator = sdictviewer.ucollator
        self.word_list = None

    def __eq__(self, other):
        return self.key() == other.key()
    
    def __str__(self):
        return self.file_name
    
    def __hash__(self):
        return self.key().__hash__()

    def key(self):
        return (self.title, self.version, self.file_name)
        
    def read_unit(self, pos):
        f = self.file
        f.seek(pos);
        record_length= read_int(f.read(4))
        s = f.read(record_length)
        s = self.compression.decompress(s)
        return s
       
    def find_index_entry(self, word):
        low = self.header.full_index_offset
        high = self.header.articles_offset - 1
        probe = -1
        while True:
            prevprobe = probe
            probe = low + int((high-low)/2)
            probe = self.findword(probe)
            if probe == prevprobe:
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
        start = -1
        while (start == -1) and (pos + len(b) < self.header.articles_offset):
            b = ''.join([b, self.file.read(128)])
            start = b.find("\xFE\xFE\xFE\xFE")
        if start == -1:
            raise Exception("could not find start position in long index: " + str(pos))
        return pos + start

    
    def get_word_list_iter(self, start_string):
        start_word = Word(self, start_string)
        next_ptr = self.find_index_entry(start_word)
        found = False 
        while True:
            if next_ptr < 0:
                raise StopIteration
            next_offset, word = self.read_full_index_item(next_ptr)
            if word.startswith(start_word):
                found = True
                yield WordLookup(str(word), word.dictionary, word.article_ptr)
            else:
                if word > start_word:
                    raise StopIteration
            next_ptr += next_offset

                
    def read_full_index_item(self, pointer):
        f = self.file
        f.seek(pointer)
        s = f.read(16)
        next_word_offset = unpack('<I', s[4:8])[0]
        article_ptr = unpack('<I', s[12:16])[0]
        word = f.read(next_word_offset - 16)
        word = Word(self, word)
        word.article_ptr = article_ptr
        return next_word_offset, word
        
    def read_article(self, pointer):
        return self.read_unit(self.header.articles_offset + pointer)        
    
    def load(self):
        return
    
    def index(self, items):
        return

    def close(self, save_index = True):
        self.file.close()        


