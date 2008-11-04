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
import functools

import struct
import logging
from bisect import bisect_left

import simplejson
from PyICU import Locale, Collator

import aarddict 

ucollator =  Collator.createInstance(Locale(''))
ucollator.setStrength(Collator.PRIMARY)

def decompress(s):
    decompressed = s
    for decompress in aarddict.decompression:
        try:
            decompressed = decompress(s)
        except:
            pass
        else:
            break
    return decompressed
    

def key(s):
    return ucollator.getCollationKey(s).getByteArray()

class Word(object):
    def __init__(self, word):
        self.word = word
        self.unicode = self.word.decode('utf-8')

    def __str__(self):
        return self.word

    def __unicode__(self):
        return self.unicode
    
    def __repr__(self):
        return self.word

    def __cmp__(self, other):
        k1 = key(self.unicode[:len(other.unicode)])
        k2 = key(other.unicode)        
        return cmp(k1, k2)
    

class WordList(object):
    
    def __init__(self, file, offset1, offset2, length, key_len_fmt, index1_item_fmt):
        self.file = file
        self.offset1 = offset1
        self.offset2 = offset2
        self.length = length
        self.key_len_fmt = key_len_fmt
        self.key_len_fmt_size = struct.calcsize(key_len_fmt)
        self.index1_item_fmt = index1_item_fmt
        self.index1_item_fmt_size = struct.calcsize(index1_item_fmt)
    
    
    def __len__(self):
        return self.length
    
    def __getitem__(self, i):
        if 0 <= i < len(self):
            self.file.seek(self.offset1 + (i * self.index1_item_fmt_size))
            keyPos, article_unit_ptr = struct.unpack(self.index1_item_fmt, 
                                                             self.file.read(self.index1_item_fmt_size))
            
            self.file.seek(self.offset2 + keyPos)
            keyLen, = struct.unpack(self.key_len_fmt, 
                                    self.file.read(self.key_len_fmt_size))
            key = self.file.read(keyLen)
            word = Word(key)
            return word            
        else:
            raise IndexError        

class ArticleList(object):
    
    def __init__(self, dictionary, file, offset1, offset2, article_offset, length):
        self.file = file
        self.offset1 = offset1  
        self.offset2 = offset2
        self.article_offset = article_offset 
        self.length = length
        self.dictionary = dictionary
        self.key_len_fmt = dictionary.key_length_format
        self.key_len_fmt_size = struct.calcsize(self.key_len_fmt)
        self.index1_item_fmt = dictionary.index1_item_format
        self.index1_item_fmt_size = struct.calcsize(dictionary.index1_item_format)
        
        self.article_len_fmt =  dictionary.article_length_format
        self.article_len_fmt_size = struct.calcsize(dictionary.article_length_format)
        
    def __len__(self):
        return self.length
    
    def __getitem__(self, word_pos):
        if 0 <= word_pos < len(self):
            self.file.seek(self.offset1 + (word_pos * self.index1_item_fmt_size))
            keyPos, article_unit_ptr = struct.unpack(self.index1_item_fmt, 
                                                             self.file.read(self.index1_item_fmt_size))
            self.file.seek(self.offset2 + keyPos)
            
            keyLen, = struct.unpack(self.key_len_fmt, 
                                    self.file.read(self.key_len_fmt_size))
            key = self.file.read(keyLen)            
            article_pos = self.article_offset + article_unit_ptr            
            article_func = functools.partial(self.read_article, article_pos)
            article_func.title = key.decode('utf-8')
            article_func.source = self.dictionary
            return article_func
        else:
            raise IndexError        
        
    def read_article(self, article_pos):
        self.file.seek(article_pos)
        record_length, = struct.unpack(self.article_len_fmt, 
                                       self.file.read(self.article_len_fmt_size))
        compressed_article = self.file.read(record_length)
        decompressed_article = decompress(compressed_article)
        article = to_article(decompressed_article)
        article.source = self.dictionary
        return article 

class Article(object):

    def __init__(self, title="", text="", tags=None, dictionary=None):
        self.title = title
        self.text = text
        self.tags = [] if tags is None else tags
        self.dictionary = dictionary 

    def __repr__(self):        
        tags = '\n'.join([repr(t) for t in self.tags])
        return '%s\n%s\n%s\n%s\n%s' % (self.title.encode('utf-8'), 
                                       '-'*50, 
                                       self.text.encode('utf-8'), 
                                       '='*50, 
                                       tags) 
    
class Tag(object):

    def __init__(self, name = "", start = -1, end = -1, attributes = None):
        self.name = name
        self.start = start
        self.end = end
        self.attributes = attributes if attributes else {}

    def __repr__(self):
        attrs = ' '.join([ '%s = %s' % attr 
                          for attr in self.attributes.iteritems()])
        if attrs:
            attrs = ' ' + attrs 
        return '<%s%s> (start %d, end %d)' % (self.name, attrs, 
                                               self.start, self.end)        
        
def to_article(raw_article):
    try:
        text, tag_list = simplejson.loads(raw_article)
    except:
        logging.exception('was trying to load article from string:\n%s', raw_article[:10])
        text = raw_article
        tags = []
    else:
        tags = [Tag(name, start, end, attrs) 
                for name, start, end, attrs in tag_list]            
    return Article(text=text, tags=tags)

            
HEADER_SPEC = (('signature',    '>4s'), # string 'aard'
               ('version',      '>H'), #format version, a number, current value 1
               ('meta_length',  '>L'), #length of metadata compressed string
               ('index_count',  '>L'), #number of words in the dictionary
               ('article_count',  '>L'), #number of articles in the dictionary
               ('article_offset',  '>L'), #article offset 
               ('index1_item_format', '>4s'), #'>LLL' - represents key pointer, file number and article pointer
               ('key_length_format', '>2s'), ##'>H' - key length format in index2_item
               ('article_length_format', '>2s'), ##'>L' - article length format                              
               )  

def spec_len(spec):
    result = 0
    for name, fmt in spec:
        result += struct.calcsize(fmt)
    return result
            
class Dictionary(object):         

    def __init__(self, file_name):    
        self.file_name = file_name
        self.file = open(file_name, "rb")
        
        header = {}
        
        for name, fmt in HEADER_SPEC:
            s = self.file.read(struct.calcsize(fmt))
            header[name], = struct.unpack(fmt, s)
        
        if header['signature'] != 'aard':
            file.close()
            raise Exception("%s is not a recognized aarddict dictionary file" % file_name)
        if header['version'] != 1:
            file.close()
            raise Exception("%s is not compatible with this viewer" % file_name)
        
        meta_length = header['meta_length']
        index_count = header['index_count']
        article_count = header['article_count']
        article_offset = header['article_offset']
        self.key_length_format = header['key_length_format']
        self.index1_item_format = header['index1_item_format']
        self.article_length_format = header['article_length_format']
        self.metadata = simplejson.loads(decompress(self.file.read(meta_length)))        
        
        index1_offset = spec_len(HEADER_SPEC) + meta_length        
        index2_offset = index1_offset + index_count*struct.calcsize(header['index1_item_format'])
        
        self.index_count = index_count
        self.article_count = article_count
        self.index_language = self.metadata.get("index_language", "")    
        locale_index_language = Locale(self.index_language).getLanguage()
        if locale_index_language:
            self.index_language = locale_index_language
            
        self.article_language = self.metadata.get("article_language", "")
        locale_article_language = Locale(self.index_language).getLanguage()
        if locale_article_language:
            self.article_language = locale_article_language
                    
        self.words = WordList(self.file, 
                              index1_offset, 
                              index2_offset, 
                              self.index_count,
                              self.key_length_format,
                              self.index1_item_format)
        
        self.articles = ArticleList(self,
                                    self.file,
                                    index1_offset,
                                    index2_offset,
                                    article_offset,
                                    self.index_count)                                
            
    title = property(lambda self: self.metadata.get("title", ""))
    version = property(lambda self: self.metadata.get("aarddict_version", ""))
    description = property(lambda self: self.metadata.get("description", ""))
    copyright = property(lambda self: self.metadata.get("copyright", ""))    
    
    def __len__(self):
        return self.index_count
    
    def __getitem__(self, s):        
        startword = Word(s)
        pos = bisect_left(self.words, startword)
        try:
            while True:
                matched_word = self.words[pos]
                if matched_word != startword: break
                yield self.articles[pos]
                pos += 1
        except IndexError:
            raise StopIteration        

    def __contains__(self, s):
        for item in self[s]:
            return True
        return False
        
    def __eq__(self, other):
        return self.key() == other.key()
    
    def __str__(self):
        return self.file_name
    
    def __hash__(self):
        return self.key().__hash__()

    def key(self):
        return (self.title, self.version, self.file_name)

    def close(self):
        self.file.close()        
            
class DictFormatError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)      

        
class DictionaryCollection(list):
    
    def langs(self):
        return set([d.index_language for d in self])
    
    def lookup(self, start_word, max_from_one_dict=50):
        for dictionary in self:
            count = 0
            for article in dictionary[start_word]:
                yield article
                count += 1
                if count >= max_from_one_dict: break            
