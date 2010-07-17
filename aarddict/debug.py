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
# Copyright (C) 2010 Igor Tkach

import gc
from operator import itemgetter
from datetime import datetime

import dictionary

last_type_stats = {}

def dump_type_count_diff():
    import objgraph
    global last_type_stats
    type_stats = objgraph.typestats()
    diff = {}
    for key, val in type_stats.iteritems():
        countdiff = val - last_type_stats.get(key, 0)
        if countdiff:
            diff[key] = countdiff
    print '====>\t', 'diff', datetime.strftime(datetime.now(), '%X')
    print '\n'.join(('\t%s: %d' % item) for item in
                     reversed(sorted(diff.iteritems(), key=itemgetter(1)))), \
           '\n', '-'*40
    last_type_stats = type_stats


checkpoint_type_stats = {}

def set_type_count_checkpoint():
    import objgraph
    global checkpoint_type_stats
    checkpoint_type_stats = objgraph.typestats()
    print '====>\t', 'checkpoint', datetime.strftime(datetime.now(), '%X')
    print '\n'.join(('\t%s: %d' % item) for item in
                     reversed(sorted(checkpoint_type_stats.iteritems(), key=itemgetter(1)))), \
           '\n', '-'*40


def dump_type_count_checkpoint_diff():
    import objgraph
    type_stats = objgraph.typestats()
    diff = {}
    for key, val in type_stats.iteritems():
        countdiff = val - checkpoint_type_stats.get(key, 0)
        if countdiff:
            diff[key] = countdiff

    print '====>\t', 'checkpoint diff', datetime.strftime(datetime.now(), '%X')
    print '\n'.join(('\t%s: %d' % item) for item in
                     reversed(sorted(diff.iteritems(), key=itemgetter(1)))), \
           '\n', '-'*40

def rungc():    
    collected = gc.collect()
    print "GC collected %d" % collected

def dump_cache_stats():
    print '====>\t', 'cache stats', datetime.strftime(datetime.now(), '%X')
    for obj in gc.get_objects():
        if isinstance(obj, dictionary.CacheList):
            ratio_str = '%.2f' % (float(obj.hit)/obj.miss) if obj.miss else ''
            print '\t', obj.name, ('\thit/miss: %s\thit: %5d\tmiss: %5d\tsize: %3d' 
                                   % (ratio_str, obj.hit, obj.miss, len(obj.cache)))
    
