# pyuca - Unicode Collation Algorithm
# Version: 2006-01-27
#
# Author:
# James Tauber
# http://jtauber.com/
#
# Enhancements:
# Jeremy Mortis
# mortis@ucalgary.ca


"""
Preliminary implementation of the Unicode Collation Algorithm.
http://www.unicode.org/reports/tr10/

This only implements the simple parts of the algorithm but I have successfully
tested it using the Default Unicode Collation Element Table (DUCET) to collate
Ancient Greek correctly.

'Non-ignorable' variable weighting is assumed.  See:
http://www.unicode.org/reports/tr10/#Variable_Weighting

Usage example:

    from pyuca import Collator
    c = Collator("allkeys.txt")

    sorted_words = sorted(words, key=c.sort_key)

allkeys.txt (1 MB) is available at

    http://www.unicode.org/Public/UCA/latest/allkeys.txt

but you can always subset this for just the characters you are dealing with.
"""

import unicodedata
import types
import sys
import os

class Trie:
    
    def __init__(self):
        self.root = [None, {}]

    def add(self, key, value):
        curr_node = self.root
        for part in key:
            curr_node = curr_node[1].setdefault(part, [None, {}])
        curr_node[0] = value

    def find_prefix(self, key):
        curr_node = self.root
        remainder = key
        for part in key:
            if part not in curr_node[1]:
                break
            curr_node = curr_node[1][part]
            remainder = remainder[1:]
        if remainder == key:
            return None, remainder[1:]
        return (curr_node[0], remainder)


class Collator:

    def __init__(self, filename, maxlevel=0, normalize="NFC"):

        self.table = Trie()
        self.load(self.findfile(filename))
        self.maxlevel = maxlevel
        self.normalize = normalize

    def findfile(self, filename):

        for dirname in sys.path:
            candidate = os.path.join(dirname, filename)
            if os.path.isfile(candidate):
                return candidate
        raise Exception("Can't find file " + filename + " in " + str(sys.path))

    def load(self, filename):

        for line in open(filename):
            if line.startswith("#") or line.startswith("%"):
                continue
            if line.strip() == "":
                continue
            line = line[:line.find("#")] + "\n"
            line = line[:line.find("%")] + "\n"
            line = line.strip()
        
            if line.startswith("@"):
                pass
            else:
                semicolon = line.find(";")
                charList = line[:semicolon].strip().split()
                x = line[semicolon:]
                collElements = []
                while True:
                    begin = x.find("[")
                    if begin == -1:
                        break                
                    end = x[begin:].find("]")
                    collElement = x[begin:begin+end+1]
                    x = x[begin + 1:]
                    
                    alt = collElement[1]
                    chars = collElement[2:-1].split(".")
                    
                    collElements.append((alt, chars))

                integer_points = [int(ch, 16) for ch in charList]
                self.table.add(integer_points, collElements)

    def sort_key(self, string, encoding="utf-8"):

        if type(string) is types.StringType:
            string = string.decode(encoding);

        string2 = unicodedata.normalize(self.normalize, string)
        
        lookup_key = [ord(ch) for ch in string]
        collation_elements = []
        while lookup_key:
            value, lookup_key = self.table.find_prefix(lookup_key)
            if not value:
                value =  [('.', ['0000', '0000', '0000', '0000'])]
            collation_elements.extend(value)
    
        sort_key = []
        for level in range(self.maxlevel + 1):
            if level:
                sort_key.append(0)
            for element in collation_elements:
                i = int(element[1][level], 16)
                if i:
                    sort_key.append(i)
        return tuple(sort_key)

