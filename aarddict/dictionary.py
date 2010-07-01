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
import struct
import logging
import zlib
import bz2
import os
from functools import partial
from bisect import bisect_left
from itertools import islice, chain
from collections import defaultdict, deque
from uuid import UUID

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
        parts.append(u' (%s)' % lang)
    else:
        sitelang = d.metadata.get('sitelang')
        if sitelang:
            parts.append(u' (%s)' % sitelang)
    if with_vol_num and d.total_volumes > 1:
        parts.append(u' Vol. %s' % d.volume)
    return u''.join(parts)

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

cmp_word_start = cmp_words

def cmp_word_exact(word1, word2, strength):
    """
    >>> cmp_words_exact(u'a', u'b', PRIMARY)
    -1

    >>> cmp_words_exact(u'abc', u'a', PRIMARY)
    1

    >>> cmp_words_exact(u'A', u'a', PRIMARY)
    0

    >>> cmp_words_exact('á'.decode('utf8'), u'a', PRIMARY)
    0

    >>> cmp_words_exact('ábc'.decode('utf8'), u'a', SECONDARY)
    1

    >>> cmp_words_exact('á'.decode('utf8'), 'Á'.decode('utf8'), PRIMARY)
    0

    >>> cmp_words_exact('á'.decode('utf8'), 'Á'.decode('utf8'), SECONDARY)
    0

    >>> cmp_words_exact('á'.decode('utf8'), 'Á'.decode('utf8'), TERTIARY)
    -1

    >>> cmp_words_exact('á'.decode('utf8'), 'Á'.decode('utf8'), QUATERNARY)
    -1


    >>> cmp_words_exact('ábc'.decode('utf8'), u'a', PRIMARY)
    1

    >>> cmp_words_exact('ábc'.decode('utf8'), u'a', SECONDARY)
    1

    >>> cmp_words_exact('ábc'.decode('utf8'), 'Á'.decode('utf8'), PRIMARY)
    1

    >>> cmp_words_exact('ábc'.decode('utf8'), 'Á'.decode('utf8'), SECONDARY)
    1

    >>> cmp_words_exact('ábc'.decode('utf8'), 'Á'.decode('utf8'), TERTIARY)
    1

    >>> cmp_words_exact('ábc'.decode('utf8'), 'Á'.decode('utf8'), QUATERNARY)
    1

    """
    k1 = collation_key(word1, strength)
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
    article.position = pos
    return article


def _read_raw_article(dictionary, offset, len_fmt, pos):
    compressed_article = _readstr(dictionary.file, offset + pos, len_fmt)
    return decompress(compressed_article)


class CacheList(object):

    def __init__(self, alist, max_cache_size=100, name=''):
        self.alist = alist
        self.max_cache_size = max_cache_size
        self.cache = {}
        self.cache_list = deque()
        self.hit = 0
        self.miss = 0
        self.name = name

    def __len__(self):
        return len(self.alist)

    def __getitem__(self, i):
        if i in self.cache:
            result = self.cache[i]
            self.hit += 1
        else:
            self.cache[i] = result = self.alist[i]
            self.miss += 1
            self.cache_list.append(i)
            if len(self.cache_list) > self.max_cache_size:
                del self.cache[self.cache_list.popleft()]
        return result


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
            article_func = partial(self.read_article, article_unit_ptr)
            article_func.title = key.decode('utf8')
            article_func.source = self.dictionary
            return article_func
        else:
            raise IndexError


class Article(object):

    def __init__(self, title="", text="", meta=None, dictionary=None, position=None):
        self.title = title
        self.text = text
        self.meta = {} if meta is None else meta
        self.dictionary = dictionary
        self.section = None
        self.position = position

    def _redirect(self):
        redirect = self.meta.get(u'r',
                                 self.meta.get('redirect', u''))
        if redirect and self.section:
            redirect = u'#'.join((redirect, self.section))
        return redirect

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
        return 'Article(title=%r, text=%r, meta=%r)' % (self.title,
                                                        self.text,
                                                        self.meta)


def to_article(raw_article):
    try:
        articletuple = simplejson.loads(raw_article)
        if len(articletuple) == 3:
            text, _, meta = articletuple
        else:
            text, _ = articletuple
            meta = {}
    except:
        logging.exception('was trying to load article from string:\n%r', raw_article[:20])
        raise
    else:
        return Article(text=text, meta=meta)


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

        try:
            header = Header(self.file)
        except:
            logging.exception('Failed to read dictionary header from %s', self.file_name)
            raise DictFormatError(self.file_name,
                                  "Not a recognized aarddict dictionary file")

        if header.signature != 'aard':
            if close_on_error and self.file:
                self.file.close()
            raise DictFormatError(self.file_name,
                                  "Not a recognized aarddict dictionary file")

        if header.version != 1:
            if close_on_error and self.file:
                self.file.close()
            raise DictFormatError(self.file_name,
                                  "File format version is not compatible with this viewer")

        self.index_count = header.index_count
        self.sha1sum = header.sha1sum
        self.uuid = UUID(bytes=header.uuid)
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

        read_index_item = partial(_read_index_item,
                                                 self.file,
                                                 header.index1_offset,
                                                 header.index1_item_format)
        read_key = partial(_read_key,
                                     self.file,
                                     header.index2_offset,
                                     header.key_length_format)
        read_article_func = _read_raw_article if raw_articles else _read_article
        read_article = partial(read_article_func,
                                         self,
                                         header.article_offset,
                                         header.article_length_format)
        self.words = CacheList(WordList(self.index_count,
                                        read_index_item,
                                        read_key),
                               name='%s (w)' % format_title(self))
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
    language_links = property(lambda self: sorted(self.metadata.get("language_links", [])))

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
        if isinstance(self.file_name, unicode):
            return self.file_name.encode('utf8')
        else:
            return self.file_name

    def __repr__(self):
        return '<%s.%s %s %r>' % (self.__module__, self.__class__.__name__,
                               self.key(), self.file_name)

    def __hash__(self):
        return self.key().__hash__()

    def lookup(self, word, strength=PRIMARY, cmp_func=cmp_word_start):
        if not word:
            return
        if not isinstance(word, unicode):
            word = word.decode('utf8')
        lookupword, section = split_word(word)

        pos = bisect_left(CollationKeyList(self.words, strength),
                          collation_key(lookupword, strength).getByteArray())
        try:
            while True:
                matched_word = self.words[pos]
                cmp_result = cmp_func(matched_word, lookupword, strength)
                if cmp_result == 0:
                    article_func = self.articles[pos]
                    article_func.section = section
                    article_func.position = pos
                    yield article_func
                    pos += 1
                else:
                    break
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

    def __init__(self, file_name, reason):
        self.file_name = file_name
        self.reason = reason

    def __str__(self):
        return '%s: %s' % (self.file_name, self.reason)

class VerifyError(Exception): pass

class DictionaryCollection(list):

    def langs(self):
        return set((d.index_language for d in self))

    def uuids(self):
        return set((d.uuid for d in self))

    def volumes(self, uuid):
        return sorted((d for d in self if d.uuid == uuid),
                      key=lambda d: d.volume)

    def best_match(self, word, max_from_vol=50):
        counts = defaultdict(int)
        seen = set()
        for cmp_func in (cmp_word_exact, cmp_word_start):
            for strength in (TERTIARY, SECONDARY, PRIMARY):
                for vol in self:
                    count = counts[vol]
                    if count >= max_from_vol: continue
                    for article in vol.lookup(word, strength=strength,
                                              cmp_func=cmp_func):
                        article_key = (article.position, vol)
                        if article_key in seen:
                            continue
                        else:
                            yield self._wrap_redirect(article)
                            seen.add(article_key)
                            count += 1
                            if count >= max_from_vol: break
                    counts[vol] = count


    def _wrap_redirect(self, article):
        redirect_article = partial(self.redirect, article)
        redirect_article.title = article.title
        redirect_article.section = article.section
        redirect_article.source = article.source
        return redirect_article

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
                    yield self._wrap_redirect(article)
                else:
                    yield article

    def _redirect(self, article, level=0):
        redir = article.redirect

        if not redir:
            return article

        logging.debug('Redirect %r section %r ==> %r (level %d)',
                      article.title, article.section, redir, level)

        if level > max_redirect_levels:
            raise RedirectTooManyLevels(article)

        for strength in (TERTIARY, SECONDARY, PRIMARY):
            resulti = self.lookup(redir,
                                  uuid=article.dictionary.uuid,
                                  strength=strength,
                                  resolve_redirects=False)
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


