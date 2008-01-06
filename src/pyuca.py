#!/usr/bin/python

"""
pyuca - Unicode Collation Algorithm

Original author:
James Tauber
http://jtauber.com/

Enhancements made by Jeremy Mortis:
- allow specification of collation strengths
- handle elements missing from code table
- define CollationKey object type
- use similar interface as PyICU
- add test harness

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

    sorted_words = sorted(words, key=c.getCollationKey())

allkeys.txt (1 MB) is available at

    http://www.unicode.org/Public/UCA/latest/allkeys.txt

but you can always subset this for just the characters you are dealing with.
"""

import unicodedata
import types
import sys
import os
import array

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

    def __init__(self, filename, strength=4, normalize="NFC"):

        self.table = Trie()
        self.load(self.findfile(filename))
        self.strength = strength
        self.normalize = normalize

    def setStrength(self, strength):
        self.strength = strength
        
    def findfile(self, filename):

        for dirname in sys.path:
            candidate = os.path.join(dirname, filename)
            if os.path.isfile(candidate):
                return candidate
        sys.stderr.write("Can't find file %s in %s\n" % (filename, str(sys.path)))
        sys.exit()

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

    def getCollationKey(self, string, encoding="utf-8"):

        if type(string) is types.StringType:
            cstring = unicodedata.normalize(self.normalize, string.decode(encoding))
        else:
            cstring = unicodedata.normalize(self.normalize, string)
        
        lookup_key = [ord(ch) for ch in cstring]
        collation_elements = []
        while lookup_key:
            value, lookup_key = self.table.find_prefix(lookup_key)
            if not value:
                value =  [('.', ['0000', '0000', '0000', '0000'])]
            collation_elements.extend(value)
    
        collationKey = CollationKey()
        for level in range(self.strength):
            if level:
                collationKey.append(0)
                collationKey.append(0)
            for element in collation_elements:
                value = int(element[1][level], 16)
                if value != 0:
                    b0 = (value // 256)
                    b1 = (value % 256)
                    collationKey.append(b0)
                    collationKey.append(b1)
        return collationKey

class CollationKey:

    def __init__(self):
        self.key = array.array("B")
        
    def __eq__(self, other):
        return self.key.tostring() == other.key.tostring()
        
    def __cmp__(self, other):
        return cmp(self.key.tostring(), other.key.tostring())


    def __len__(self):
        return len(self.key.tostring())

    def append(self, i):
        self.key.append(i)

    def __str__(self):
        s = ""
        for c in self.key.tostring():
            s = s + ("%02x " % ord(c))
        return s[:-1]

    def getByteArray(self):
        return list(self.key.tostring())

    def getBinaryString(self):
        return self.key.tostring()

    def startswith(self, other):
        return self.key.tostring()[:len(other.key)] == other.key.tostring()

if __name__ == '__main__':

    import struct
    
    collator = Collator("allkeys.txt")

    cka = collator.getCollationKey("a")
    print "str(cka) = '" + str(cka) + "'"
    print "cka.getBinaryString() = '" + ''.join([(r"\x%02x" % ord(c)) for c in cka.getBinaryString()]) + "'"
    print "cka.getByteArray() =", map(ord, cka.getByteArray())
    

    ckb = collator.getCollationKey("b")
    print ""
    print "str(ckb) = '" + str(ckb) + "'"
    print "cmp(cka,ckb) =", cmp(cka, ckb)
        
    print "Done."
