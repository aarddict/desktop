#!/usr/bin/python

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
# Copyright (C) 2008-2009  Igor Tkach

from __future__ import with_statement

import sys
import optparse
import logging

from pprint import pprint


logging.basicConfig(format='%(levelname)s: %(message)s')

__version__ = "0.9.2"
__appname__ = "Aard Dictionary"

from os import path
package_dir = path.abspath(path.dirname(__file__))


def main():

    usage = "usage: %prog [options] [FILE1] [FILE2] ..."
    parser = optparse.OptionParser(version="%%prog %s" % __version__, usage=usage)
    parser.add_option(
        '-i', '--identify',
        action='store_true',
        default=False,
        help='Print identity information for files specified'
        )
    parser.add_option(
        '-v', '--verify',
        action='store_true',
        default=False,
        help='Verify dictionary files specified'
        )
    parser.add_option(
        '-d', '--debug',
        action='store_true',
        default=False,
        help='Turn on debugging information'
        )
    parser.add_option(
        '-m', '--metadata',
        action='store_true',
        default=False,
        help='Print metadata for dictionary files specified'
        )
    parser.add_option(
        '-e', '--dev-extras',
        action='store_true',
        default=False,
        help='Enable WebKit development extras'
        )
    options, args = parser.parse_args()

    if options.debug:
        #if not set tries to import multiprocessing
        #which is excluded when built with py2exe
        logging.logMultiprocessing = 0
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        import warnings
        warnings.simplefilter('ignore', Warning)

    if options.identify:
        identify(args)


    if options.verify:
        verify(args)

    if options.metadata:
        metadata(args)

    if options.identify or options.verify or options.metadata:
        raise SystemExit

    import aarddict.qtui
    aarddict.qtui.main(args,
                       debug=options.debug,
                       dev_extras=options.dev_extras)


def identify(file_names):
    from .dictionary import Volume
    tmpl = '%16s: %s'
    for file_name in file_names:
        print '%s:' % file_name
        print '-'*(len(file_name)+1)
        volume = Volume(file_name)        
        print tmpl % ('Title', volume.title)
        print tmpl % ('Dictionary id', volume.uuid.hex)
        print tmpl % ('Volume id', volume.volume_id)
        print tmpl % ('Volume', '%s of %s' % (volume.volume, 
                                              volume.total_volumes))
        print tmpl % ('Version', volume.version)
        print tmpl % ('Articles', volume.article_count)


def verify(file_names):
    from .dictionary import Volume, VerifyError

    ERASE_LINE = '\033[2K'
    BOLD='\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    ENDC = '\033[0m'

    for file_name in file_names:
        volume = Volume(file_name)
        try:
            for progress in volume.verify():
                sys.stdout.write(ERASE_LINE+'\r')
                sys.stdout.write('Verifying %s: %.1f%%' % (file_name, 100*progress))
                sys.stdout.flush()
        except VerifyError:
            sys.stdout.write(ERASE_LINE+'\r')
            sys.stdout.write(file_name+' ')
            sys.stdout.write(BOLD+RED+'[CORRUPTED]'+ENDC)
            sys.stdout.write('\n')
            sys.stdout.flush()
        else:
            sys.stdout.write(ERASE_LINE+'\r')
            sys.stdout.write(file_name+' ')
            sys.stdout.write(BOLD+GREEN+'[OK]'+ENDC)
            sys.stdout.write('\n')
            sys.stdout.flush()


def metadata(file_names):
    from .dictionary import Volume
    for file_name in file_names:
        volume = Volume(file_name)
        print '%s metadata:' % file_name
        pprint(volume.metadata)


if __name__ == '__main__':
    main()
