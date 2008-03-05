#!/usr/bin/python

"""
This file is part of Aarddict Dictionary Viewer
(http://code.google.com/p/aarddict)

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

# Note:  this is a crude translation to XDXF because all definitions
# are lumped together.

import sys
import optparse

usage = "usage: %prog [options] "
parser = optparse.OptionParser(version="%prog 1.0", usage=usage)

parser.add_option(
    '--lang-from',
    default='unknown',
    help='Language translated from (3 character ISO-639-2 code)'
    )
parser.add_option(
    '--lang-to',
    default='unknown',
    help='Language translated to (3 character ISO-639-2 code)'
    )
parser.add_option(
    '--full-name',
    default='Freedict dictionary',
    help='Full name of dictionary'
    )
parser.add_option(
    '--description',
    default='Obtained from http://www.freelang.net',
    help='Description'
    )

options, args = parser.parse_args()

sys.stdout.write('<xdxf lang_from="%s" lang_to="%s" format="visual">\n' % (options.lang_to, options.lang_from))
sys.stdout.write('<full_name>%s</full_name>\n' % options.full_name)
sys.stdout.write('<description>%s</description>\n' % options.description)

currTitle = ""
currArticle = ""

while True:
    title = sys.stdin.read(31)
    if not title:
        break
    article = sys.stdin.read(53)

    title = title.rstrip("\x00").decode("cp1252").encode("utf8")
    article = article.rstrip("\x00").decode("cp1252").encode("utf8")

    if title == currTitle:
        currArticle += "; " + article
    else:
        sys.stdout.write("<ar><k>%s</k>%s</ar>\n" % (currTitle, currArticle))
        currTitle = title
        currArticle = article

sys.stdout.write("<ar><k>%s</k>%s</ar>\n" % (currTitle, currArticle))
sys.stdout.write('</xdxf>\n')


