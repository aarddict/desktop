import logging
import time
import sys
import threading

class AutoIndent(object):
        
    def __init__(self):
        self.offset = 0
        self.frame_cache = {}

    def indent_level(self):
        i = 0
        base = sys._getframe(3)
        f = base.f_back
        while f:
            if id(f) in self.frame_cache:
                i += 1
            f = f.f_back
        if i == 0:
            # clear out the frame cache
            self.frame_cache = {id(base): True}
        else:
            self.frame_cache[id(base)] = True
        return i

    def write(self, stuff):
        indentation = '  ' * self.indent_level()
        def indent(l):
            if l:
                return indentation + l
            else:
                return l
        stuff = '\n'.join([indent(line) for line in stuff.split('\n')])
        logging.debug(stuff)

auto_indent = AutoIndent()

def timef(f):
    
    def new_func(*args, **kw):
        t0 = time.time()
        result = f(*args, **kw)
        auto_indent.write('%s took %s ms in thread %s' % (f.__name__, (time.time() - t0)*1000, threading.currentThread()))
        return result
    new_func.__name__ = f.__name__
    return new_func
