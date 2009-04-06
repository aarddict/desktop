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

__version__ = "0.7.4"
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
    
    options, args = parser.parse_args()
    
    if options.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
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
        for file_name in args:
            sys.stdout.write('Verifying %s' % file_name) 
            d = dictionary.Dictionary(file_name)
            if d.verify():
                sys.stdout.write(': OK\n')
            else:
                sys.stdout.write(': CORRUPTED\n')
                
    if options.identify or options.verify:
        raise SystemExit             
    
    try:
        import hildon
    except:        
        import ui
        viewer = ui.DictViewer()
    else:
        import hildonui
        viewer = hildonui.HildonDictViewer()
    viewer.main()
    
if __name__ == '__main__':
    main()
