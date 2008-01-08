import aarddict
from aarddict.formats import *

from pyuca import Collator
ucollator = Collator("aarddict/allkeys.txt")

def detect_format(file_name):
    fmt_names = [fmt for fmt in dir(aarddict.formats) if not (fmt.startswith('__') or fmt.endswith('__'))]
    fmts = [__import__("aarddict.formats."+fmt_name, globals(), locals(), [fmt_name]) for fmt_name in fmt_names]
    for fmt in fmts:
        if fmt.can_open(file_name):
            return fmt
    return None
