from __future__ import with_statement
import zlib
import bz2
import optparse
import logging

logging.basicConfig(format='%(levelname)s: %(message)s')
    
compression = (zlib.compress,
               bz2.compress)

decompression = (zlib.decompress,
                 bz2.decompress)


def main():
    
    usage = "usage: %prog [options] [FILE1] [FILE2] ..."
    parser = optparse.OptionParser(version="%prog 0.7.0", usage=usage)
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