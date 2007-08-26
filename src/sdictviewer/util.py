"""
This file is part of SDict Viewer (http://sdictviewer.sf.net) - 
a dictionary application that allows to use data bases 
in AXMASoft's open dictionary format. 

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2006-2007 Igor Tkach
"""
import threading
import gobject
import gtk

class ListMap(dict):
    def __missing__ (self, key):
        value = []
        self.__setitem__(key, value)
        return value

class BackgroundWorker(threading.Thread):
    def __init__(self, task, task_listener, callback, data = None):
        super(BackgroundWorker, self).__init__()
        self.callback = callback
        self.task_listener = task_listener
        self.task = task
        self.data = data
            
    def run(self):
        if self.task_listener:
            gobject.idle_add(self.task_listener.before_task_start)
        result = None
        error = None
        try:
            result = self.task()
        except Exception, ex:
            print "Failed to execute task: ", ex
            error = ex
        gobject.idle_add(self.callback, result, error, self.data)
        if self.task_listener:
            gobject.idle_add(self.task_listener.after_task_end)
        
def create_scrolled_window(widget):
    scrolled_window = gtk.ScrolledWindow()
    scrolled_window.set_shadow_type(gtk.SHADOW_IN)
    scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    scrolled_window.add(widget)                                
    return scrolled_window
    