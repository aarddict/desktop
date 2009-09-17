import gobject
gobject.threads_init()

import gtk
import webkit
import aar2html

def create_scrolled_window(widget):
    scrolled_window = gtk.ScrolledWindow()
    scrolled_window.set_shadow_type(gtk.SHADOW_IN)
    scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    scrolled_window.add(widget)
    return scrolled_window

class View(object):

    def __init__(self, html):

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect("event", self.window_event)
        self.window.set_border_width(2)
        self.window.resize(640, 480)
        self.window.set_position(gtk.WIN_POS_CENTER)

        webview = webkit.WebView()
        webview.connect('navigation-requested', self._navigation_policy_decision_requested_cb)

        webview.load_string(html, "text/html", "utf8", base_uri='file://')
        self.window.add(create_scrolled_window(webview))

        self.window.show_all()

    def _navigation_policy_decision_requested_cb(self, *args, **kwargs):
        return 2

    def window_event(self, window, event, data = None):
        if event.type == gtk.gdk.DELETE:
            gtk.main_quit()
            return True

if __name__=='__main__':
    from optparse import OptionParser
    optparser = OptionParser()
    opts, args = optparser.parse_args()
    from aarddict.dictionary import Dictionary
    d = Dictionary(args[0])
    articles  = list(d[args[1]])
    html = aar2html.convert(articles[0]())
    view = View(html)
    gtk.main()
