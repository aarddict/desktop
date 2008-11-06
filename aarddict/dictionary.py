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
from __future__ import with_statement
import functools

import struct
import logging
from bisect import bisect_left

import simplejson
from PyICU import Locale, Collator

import aarddict 

ucollator =  Collator.createInstance(Locale(''))
ucollator.setStrength(Collator.PRIMARY)

from hashlib import sha1

def calcsha1(file_name, offset, chunksize=100000):    
    with open(file_name, 'rb') as f:    
        f.seek(offset)
        result = sha1()    
        while True:
            s = f.read(chunksize)
            result.update(s)
            if not s: break
        return result.hexdigest()

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
    
def _read(file, pos, fmt):
    file.seek(pos)
    s = file.read(struct.calcsize(fmt))
    return struct.unpack(fmt, s)

def _readstr(file, pos, len_fmt):
    strlen, = _read(file, pos, len_fmt)
    return file.read(strlen)

def _read_index_item(file, offset, itemfmt, itemno):
    return _read(file, offset + itemno * struct.calcsize(itemfmt), itemfmt)            

def _read_key(file, offset, len_fmt, pos):
    return _readstr(file, offset + pos, len_fmt)

def _read_article(dictionary, offset, len_fmt, pos):
    compressed_article = _readstr(dictionary.file, offset + pos, len_fmt)        
    decompressed_article = decompress(compressed_article)
    article = to_article(decompressed_article)
    article.source = dictionary
    return article 

class WordList(object):
    
    def __init__(self, length, read_index_item, read_key):
        self.length = length
        self.read_index_item = read_index_item
        self.read_key = read_key
    
    def __len__(self):
        return self.length
    
    def __getitem__(self, i):
        if 0 <= i < len(self):
            key_pos, article_unit_ptr = self.read_index_item(i)            
            key = self.read_key(key_pos)
            return Word(key)            
        else:
            raise IndexError
        
class ArticleList(object):
    
    def __init__(self, dictionary, read_index_item, read_key, read_article):
        self.dictionary = dictionary
        self.read_index_item = read_index_item
        self.read_key = read_key
        self.read_article = read_article
                
    def __len__(self):
        return len(self.dictionary)
    
    def __getitem__(self, i):
        if 0 <= i < len(self):
            key_pos, article_unit_ptr = self.read_index_item(i)            
            key = self.read_key(key_pos)
            article_func = functools.partial(self.read_article, article_unit_ptr)
            article_func.title = key.decode('utf-8')
            article_func.source = self.dictionary
            return article_func
        else:
            raise IndexError                

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

            
HEADER_SPEC = (('signature',                '>4s'), # string 'aard'
               ('sha1sum',                  '>40s'), #sha1 sum of dictionary file content following signature and sha1 bytes  
               ('version',                  '>H'), #format version, a number, current value 1
               ('uuid',                     '>16s'), # dictionary UUID, shared by all volumes of the same dictionary
               ('volume',                   '>H'), # volume number of this this file
               ('of',                       '>H'), # total number of volumes for the dictionary
               ('meta_length',              '>L'), #length of metadata compressed string
               ('index_count',              '>L'), #number of words in the dictionary
               ('article_count',            '>L'), #number of articles in the dictionary
               ('article_offset',           '>L'), #article offset 
               ('index1_item_format',       '>4s'), #'>LLL' - represents key pointer, file number and article pointer
               ('key_length_format',        '>2s'), ##'>H' - key length format in index2_item
               ('article_length_format',    '>2s'), ##'>L' - article length format                              
               )  

def spec_len(spec):
    result = 0
    for name, fmt in spec:
        result += struct.calcsize(fmt)
    return result
            
class Header(object):
    
    def __init__(self, file):    
        for name, fmt in HEADER_SPEC:
            s = file.read(struct.calcsize(fmt))
            value, = struct.unpack(fmt, s)
            setattr(self, name, value)
         
    index1_offset = property(lambda self: spec_len(HEADER_SPEC) + self.meta_length)
    index2_offset = property(lambda self: self.index1_offset + self.index_count*struct.calcsize(self.index1_item_format))
                            
class Dictionary(object):

    def __init__(self, file_name):    
        self.file_name = file_name
        self.file = open(file_name, "rb")
        
        header = Header(self.file)
        
        if header.signature != 'aard':
            file.close()
            raise Exception("%s is not a recognized aarddict dictionary file" % file_name)
        
        if header.version != 1:
            file.close()
            raise Exception("%s is not compatible with this viewer" % file_name)
        
        self.index_count = header.index_count        
        self.article_count = header.article_count
        self.sha1sum = header.sha1sum
        
        self.metadata = simplejson.loads(decompress(self.file.read(header.meta_length)))
                
        self.index_language = self.metadata.get("index_language", "")
        if isinstance(self.index_language, unicode):
            self.index_language = self.index_language.encode('utf8')
                        
        locale_index_language = Locale(self.index_language).getLanguage()
        if locale_index_language:
            self.index_language = locale_index_language
            
        self.article_language = self.metadata.get("article_language", "")
        if isinstance(self.article_language, unicode):
            self.article_language = self.index_language.encode('utf8')
        
        locale_article_language = Locale(self.index_language).getLanguage()
        if locale_article_language:
            self.article_language = locale_article_language

        read_index_item = functools.partial(_read_index_item, 
                                                 self.file, 
                                                 header.index1_offset, 
                                                 header.index1_item_format)
        read_key = functools.partial(_read_key,
                                     self.file,
                                     header.index2_offset,
                                     header.key_length_format)
        read_article = functools.partial(_read_article, 
                                         self, 
                                         header.article_offset,
                                         header.article_length_format)
        self.words = WordList(self.index_count, read_index_item, read_key)
        self.articles = ArticleList(self, 
                                    read_index_item, 
                                    read_key, 
                                    read_article)                                
            
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

    def verify(self):
        sha1sum = calcsha1(self.file_name, spec_len(HEADER_SPEC[:2]))
        return sha1sum == self.sha1sum

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
