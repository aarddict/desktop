import threading
import gobject
import gtk
class BackgroundWorker(threading.Thread):
    def __init__(self, task, status_display, callback):
        super(BackgroundWorker, self).__init__()
        self.callback = callback
        self.status_display = status_display
        self.task = task
            
    def run(self):
        gobject.idle_add(self.status_display.show_start)
        result = None
        error = None
        try:
            result = self.task()
        except Exception, ex:
            print "Failed to execute task: ", ex
            error = ex
        gobject.idle_add(self.callback, result, error)
        gobject.idle_add(self.status_display.show_end)
        
def create_scrolled_window(widget):
    scrolled_window = gtk.ScrolledWindow()
    scrolled_window.set_shadow_type(gtk.SHADOW_IN)
    scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    scrolled_window.add(widget)                                
    return scrolled_window
    