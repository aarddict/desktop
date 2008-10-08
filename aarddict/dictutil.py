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

Copyright (C) 2006-2008 Igor Tkach
"""

from collections import defaultdict
from itertools import chain

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
                yield WordLookup(item.word, item.dictionary, item.article_location)
                count += 1
                if count >= max_from_one_dict: break