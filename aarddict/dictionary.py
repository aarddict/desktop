# coding: utf-8
# This file is part of Aard Dictionary <http://aarddict.org>.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License <http://www.gnu.org/licenses/gpl-3.0.txt>
# for more details.
#
# Copyright (C) 2008-2009  Jeremy Mortis, Igor Tkach

from __future__ import with_statement
import functools

import struct
import logging
import zlib
import bz2
import os
from bisect import bisect_left
from itertools import islice, chain

import simplejson
from PyICU import Locale, Collator

PRIMARY = Collator.PRIMARY
SECONDARY = Collator.SECONDARY
TERTIARY = Collator.TERTIARY
QUATERNARY = Collator.QUATERNARY
IDENTICAL = Collator.IDENTICAL

from hashlib import sha1

compression = (zlib.compress,
               bz2.compress)

decompression = (zlib.decompress,
                 bz2.decompress)

max_redirect_levels = 5

def format_title(d, with_vol_num=True):
    parts = [d.title]
    lang = d.metadata.get('lang')
    if lang:
        parts.append(' (%s)' % lang)
    else:
        sitelang = d.metadata.get('sitelang')
        if sitelang:
            parts.append(' (%s)' % sitelang)
    if with_vol_num and d.total_volumes > 1:
        parts.append(' Vol. %s' % d.volume)
    return ''.join(parts)

def calcsha1(file_name, offset, chunksize=100000):
    with open(file_name, 'rb') as f:
        f.seek(offset)
        result = sha1()
        while True:
            s = f.read(chunksize)
            if not s: break
            result.update(s)
            yield (f.tell(), result)

def decompress(s):
    decompressed = s
    for decompress in decompression:
        try:
            decompressed = decompress(s)
        except:
            pass
        else:
            break
    return decompressed


def _collators():

    def create_collator(strength):
        c = Collator.createInstance(Locale(''))
        c.setStrength(strength)
        return c

    return dict([(strength, create_collator(strength).getCollationKey)
                 for strength in (PRIMARY, SECONDARY, TERTIARY,
                                  QUATERNARY, IDENTICAL)])

_collators = _collators()

def collation_key(word, strength):
    return _collators[strength](word)

def cmp_words(word1, word2, strength):
    """
    >>> cmp_words(u'a', u'b', PRIMARY)
    -1

    >>> cmp_words(u'abc', u'a', PRIMARY)
    0

    >>> cmp_words('ábc'.decode('utf8'), u'a', PRIMARY)
    0

    >>> cmp_words('ábc'.decode('utf8'), u'a', SECONDARY)
    1

    >>> cmp_words('ábc'.decode('utf8'), 'Á'.decode('utf8'), SECONDARY)
    0

    >>> cmp_words('ábc'.decode('utf8'), 'Á'.decode('utf8'), TERTIARY)
    -1

    """
    k1 = collation_key(word1[:len(word2)], strength)
    k2 = collation_key(word2, strength)
    return k1.compareTo(k2)


def split_word(word):
    """
    >>> split_word(u'a#b')
    (u'a', u'b')

    >>> split_word(u'a#')
    (u'a', u'')

    >>> split_word(u'a')
    (u'a', u'')

    >>> split_word(u'#')
    (u'#', u'')

    >>> split_word(u'#W')
    (u'', u'W')

    """
    if word.strip() == u'#':
        return (u'#', u'')
    parts = word.split('#', 1)
    section = u'' if len(parts) == 1 else parts[1]
    lookupword = parts[0] if (parts[0] or section) else word
    return lookupword, section


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
    decompressed_article = _read_raw_article(dictionary, offset, len_fmt, pos)
    article = to_article(decompressed_article)
    article.dictionary = dictionary
    return article


def _read_raw_article(dictionary, offset, len_fmt, pos):
    compressed_article = _readstr(dictionary.file, offset + pos, len_fmt)
    return decompress(compressed_article)


class WordList(object):
    """
    List of all words in the dictionary (unicode).

    """

    def __init__(self, length, read_index_item, read_key):
        self.length = length
        self.read_index_item = read_index_item
        self.read_key = read_key

    def __len__(self):
        return self.length

    def __getitem__(self, i):
        if 0 <= i < len(self):
            key_pos = self.read_index_item(i)[0]
            key = self.read_key(key_pos)
            return key.decode('utf8')
        else:
            raise IndexError


class CollationKeyList(object):
    """
    List of collation keys (returned as byte array) of specified strength
    for the given word list.

    """

    def __init__(self, wordlist, strength):
        self.wordlist = wordlist
        self.key_func = _collators[strength]

    def __len__(self):
        return len(self.wordlist)

    def __getitem__(self, i):
        word = self.wordlist[i]
        key = self.key_func(word)
        return key.getByteArray()


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
            article_func.title = key.decode('utf8')
            article_func.source = self.dictionary
            return article_func
        else:
            raise IndexError


class Article(object):

    def __init__(self, title="", text="", tags=None, meta=None, dictionary=None):
        self.title = title
        self.text = text
        self.tags = [] if tags is None else tags
        self.meta = {} if meta is None else meta
        self.dictionary = dictionary
        self.section = None

    def _redirect(self):
        redirect = self.meta.get(u'r',
                                 self.meta.get('redirect', u''))
        if redirect and self.section:
            redirect = '#'.join((redirect, self.section))
        return redirect.encode('utf8')

    redirect = property(_redirect)

    def __repr__(self):
        """
        >>> a = Article(title=u'a', text=u'Article about a',
        ...             tags=[Tag(u'b', 1, 2)], meta={u'c': u'whatever'})
        >>> a1 = eval(repr(a))
        >>> a1.title
        u'a'
        >>> a1.text
        u'Article about a'
        >>> a1.tags
        [Tag(u'b', 1, 2, attributes={})]
        >>> a1.meta
        {u'c': u'whatever'}

        """
        return 'Article(title=%r, text=%r, tags=%r, meta=%r)' % (self.title,
                                                                 self.text,
                                                                 self.tags,
                                                                 self.meta)


class Tag(object):

    def __init__(self, name, start, end, attributes=None):
        self.name = name
        self.start = start
        self.end = end
        self.attributes = attributes if attributes is not None else {}

    def __repr__(self):
        """
        >>> t = Tag(u'a', 1, 5, attributes={u'href': u'abc'})
        >>> t1 = eval(repr(t))
        >>> t1.name
        u'a'
        >>> t1.start
        1
        >>> t1.end
        5
        >>> t1.attributes
        {u'href': u'abc'}

        """
        return 'Tag(%r, %r, %r, attributes=%r)'%(self.name, self.start,
                                                 self.end, self.attributes)


def to_tag(tagtuple):
    return Tag(tagtuple[0], tagtuple[1], tagtuple[2],
               {} if len(tagtuple) < 4 else tagtuple[3])

def to_article(raw_article):
    try:
        articletuple = simplejson.loads(raw_article)
        if len(articletuple) == 3:
            text, tag_list, meta = articletuple
        else:
            text, tag_list = articletuple
            meta = {}
    except:
        logging.exception('was trying to load article from string:\n%s', raw_article[:10])
        text = raw_article
        tags = []
    else:
        tags = [to_tag(tagtuple) for tagtuple in tag_list]
    return Article(text=text, tags=tags, meta=meta)


HEADER_SPEC = (('signature',                '>4s'), # string 'aard'
               ('sha1sum',                  '>40s'), #sha1 sum of dictionary file content following signature and sha1 bytes
               ('version',                  '>H'), #format version, a number, current value 1
               ('uuid',                     '>16s'), # dictionary UUID, shared by all volumes of the same dictionary
               ('volume',                   '>H'), # volume number of this this file
               ('of',                       '>H'), # total number of volumes for the dictionary
               ('meta_length',              '>L'), #length of metadata compressed string
               ('index_count',              '>L'), #number of words in the dictionary
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

    def __init__(self, file_or_filename, raw_articles=False):
        if isinstance(file_or_filename, file):
            self.file_name = file_or_filename.name
            close_on_error = False
            self.file = file_or_filename
        else:
            self.file_name = file_or_filename
            close_on_error = True
            self.file = open(file_or_filename, "rb")

        header = Header(self.file)

        if header.signature != 'aard':
            if close_on_error and self.file:
                self.file.close()
            raise DictFormatError("%s is not a recognized aarddict dictionary file" % self.file_name)

        if header.version != 1:
            if close_on_error and self.file:
                self.file.close()
            raise DictFormatError("%s is not compatible with this viewer" % self.file_name)

        self.index_count = header.index_count
        self.sha1sum = header.sha1sum
        self.uuid = header.uuid
        self.volume = header.volume
        self.total_volumes = header.of

        raw_meta = self.file.read(header.meta_length)
        self.metadata = simplejson.loads(decompress(raw_meta))

        self.article_count = self.metadata.get('article_count',
                                               self.index_count)

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
        read_article_func = _read_raw_article if raw_articles else _read_article
        read_article = functools.partial(read_article_func,
                                         self,
                                         header.article_offset,
                                         header.article_length_format)
        self.words = WordList(self.index_count, read_index_item, read_key)
        self.articles = ArticleList(self,
                                    read_index_item,
                                    read_key,
                                    read_article)

    title = property(lambda self: self.metadata.get("title", ""))
    version = property(lambda self: self.metadata.get("version", ""))
    description = property(lambda self: self.metadata.get("description", ""))
    copyright = property(lambda self: self.metadata.get("copyright", ""))
    license = property(lambda self: self.metadata.get("license", ""))
    source = property(lambda self: self.metadata.get("source", ""))

    def __len__(self):
        return self.index_count

    def __getitem__(self, s):
        return self.lookup(s)

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

    def lookup(self, word, strength=PRIMARY):

        lookupword, section = split_word(word.decode('utf8'))

        pos = bisect_left(CollationKeyList(self.words, strength),
                          collation_key(lookupword, strength).getByteArray())
        try:
            while True:
                matched_word = self.words[pos]
                if cmp_words(matched_word, lookupword, PRIMARY) != 0:
                    break
                elif strength != PRIMARY and cmp_words(matched_word, lookupword, strength) != 0:
                    pos += 1
                    continue
                article_func = self.articles[pos]
                article_func.section = section
                yield article_func
                pos += 1
        except IndexError:
            raise StopIteration

    def key(self):
        return self.sha1sum

    def verify(self):
        st_size = os.stat(self.file_name).st_size
        offset = spec_len(HEADER_SPEC[:2])
        size = float(st_size - offset)
        result = None
        for pos, result in calcsha1(self.file_name, offset):
            yield pos/size
        if not result or result.hexdigest() != self.sha1sum:
            raise VerifyError()

    def close(self):
        self.file.close()

class DictFormatError(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class VerifyError(Exception): pass

class DictionaryCollection(list):

    def langs(self):
        return set((d.index_language for d in self))

    def uuids(self):
        return set((d.uuid for d in self))

    def volumes(self, uuid):
        return sorted((d for d in self if d.uuid == uuid), key=lambda d: d.volume)

    def lookup(self, start_word, max_from_one_dict=50,
               uuid=None, strength=PRIMARY, resolve_redirects=True):

        uuids = self.uuids() if uuid is None else (uuid,)

        for uuid in uuids:
            vols = self.volumes(uuid)
            for article in islice(chain(*[islice(vol.lookup(start_word, strength=strength),
                                                 max_from_one_dict) 
                                          for vol in vols]), 
                                  max_from_one_dict):
                if resolve_redirects:
                    redirect_article =  functools.partial(self.redirect, article)
                    redirect_article.title = article.title
                    redirect_article.section = article.section
                    redirect_article.source = article.source                
                    yield redirect_article
                else:
                    yield article

    def _redirect(self, article, level=0):
        redirect = article.redirect

        if not redirect:
            return article

        logging.debug('Redirect "%r" section "%r" ==> "%r" (level %d)',
                      article.title, article.section, redirect, level)

        if level > max_redirect_levels:
            raise RedirectTooManyLevels(article)

        for strength in (IDENTICAL, QUATERNARY, TERTIARY,
                         SECONDARY, PRIMARY):

            resulti = self.lookup(redirect,
                                  uuid=article.dictionary.uuid,
                                  strength=strength)
            try:
                result = resulti.next()
            except StopIteration:
                pass
            else:
                a = result()
                a.title = result.title
                a.section = result.section
                return self._redirect(a, level=level+1)

    def redirect(self, read_func):
        article = read_func()
        article.title = read_func.title
        article.section = read_func.section
        rarticle = self._redirect(article)    
        if rarticle:
            return rarticle
        else:
            raise RedirectNotFound(article)


class RedirectResolveError(Exception): 
    
    def __init__(self, article):
        self.article = article

class RedirectNotFound(RedirectResolveError): pass
class RedirectTooManyLevels(RedirectResolveError): pass


