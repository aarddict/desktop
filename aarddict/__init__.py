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
import optparse
import logging

logging.basicConfig(format='%(levelname)s: %(message)s')

__version__ = "0.8.0.dev"
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
    parser.add_option('--ui',
        help='Choose ui version to run, gtk or qt'
        )
    options, args = parser.parse_args()

    if options.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        import warnings
        warnings.simplefilter('ignore', Warning)

    if options.identify:
        from aarddict import dictionary
        import uuid
        for file_name in args:
            print '%s:' % file_name
            with open(file_name) as f:
                header = dictionary.Header(f)
                for name, fmt in dictionary.HEADER_SPEC:
                    value = getattr(header, name)
                    if name == 'uuid':
                        value = uuid.UUID(bytes=value)
                    print '\t%s: %s' % (name, value)

    if options.verify:
        from aarddict import dictionary
        import sys
        ERASE_LINE = '\033[2K'
        BOLD='\033[1m'
        RED = '\033[91m'
        GREEN = '\033[92m'
        ENDC = '\033[0m'

        for file_name in args:
            d = dictionary.Dictionary(file_name)
            try:
                for progress in d.verify():
                    sys.stdout.write(ERASE_LINE+'\r')
                    sys.stdout.write('Verifying %s: %.1f%%' % (file_name, 100*progress))
                    sys.stdout.flush()
            except dictionary.VerifyError:
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

    if options.metadata:
        from aarddict import dictionary
        for file_name in args:
            d = dictionary.Dictionary(file_name)
            print '%s metadata:' % file_name
            print '\n'.join(('\t%s: %s' % item) for item in d.metadata.iteritems())

    if options.identify or options.verify or options.metadata:
        raise SystemExit

    if options.ui and options.ui.lower() == 'qt':
        import qtui
        qtui.main(args)
    else:
        try:
            import hildon
        except:
            import ui
            viewer = ui.DictViewer()
        else:
            import hildonui
            viewer = hildonui.HildonDictViewer()
        viewer.main()


type_stats = {}

def _dump_type_count_diff():
    try:
        import objgraph
    except:
        pass
    else:
        import gc
        from operator import itemgetter
        print 'gc', gc.collect()
        typestats = objgraph.typestats()
        diff = {}
        for key, val in typestats.iteritems():
            countdiff = val - type_stats.get(key, 0)
            if countdiff:
                diff[key] = countdiff
        print '='*40, '\n',\
               '\n'.join(('%s: %d' % item) for item in
                         sorted(diff.iteritems(), key=itemgetter(1))), \
               '\n', '='*40
        global type_stats
        type_stats = typestats


if __name__ == '__main__':
    main()
