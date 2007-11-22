import sdictviewer
from sdictviewer.formats import *

def detect_format(file_name):
    fmt_names = [fmt for fmt in dir(sdictviewer.formats) if not (fmt.startswith('__') or fmt.endswith('__'))]
    print "sdictviewer.formats", fmt_names
    fmts = [__import__("sdictviewer.formats."+fmt_name, globals(), locals(), [fmt_name]) for fmt_name in fmt_names]
    print fmts
    for fmt in fmts:
        if fmt.can_open(file_name):
            return fmt
    return None
