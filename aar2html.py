# coding: utf8
from aarddict.dictionary import Article, Tag
from collections import defaultdict
import gobject
gobject.threads_init()

html_tags=set(['b',
               'strong',
               'small',
               'big',
               'h1',
               'h2',
               'h3',
               'h4',
               'h5',
               'h6',
               'i',
               'em',
               'u',
               'tt',
               'p',
               'div',
               'sup',
               'sub',
               'a'
               ])

def convert(article):
    """
    Convert aarddict.dictionary.Article into HTML.

    >>> convert(Article(text=u'abbrev\\n    Common abbreviation for \u2018abbreviation\u2019.\\n\\n\\n  ', tags=[Tag('k', 0, 6), Tag('ar', 0, 52)]))
    u'<span class="ar"><span class="k">abbrev</span><br>    Common abbreviation for \u2018abbreviation\u2019.<p></span><br>  '

    >>> text = '''Ä
    ... Ä or ä is not a letter used in English, but is used in some other languages.
    ... German 
    ... Germany and Austria
    ... Ä or ä is one of the 4 extra letters used in German.  It can be replaced by using the letters Ae or ae.  In English language newspapers it is often written as A or a but this is not correct. 
    ... Internet addresses are written as "ae" because the internet address system can only understand ordinary English letters. 
    ... Switzerland
    ... German is one of the official languages of Switzerland, but people from Switzerland who speak German do not use the extra letter, they always use ae.'''.decode('utf8')
    >>> tags = [Tag('h1', 0, 1),
    ... Tag('strong', 2, 3),
    ... Tag('strong', 7, 8),
    ... Tag('a', 33, 40, {'href': u'English language'}),
    ... Tag('p', 2, 78),
    ... Tag('h2', 79, 86),
    ... Tag('a', 87, 94, {'href': u'Germany'}),
    ... Tag('a', 99, 106, {'href': u'Austria'}),
    ... Tag('h3', 87, 106),
    ... Tag('a', 152, 158, {'href': u'German language'}),
    ... Tag('p', 107, 298),
    ... Tag('a', 403, 410, {'href': u'English language'}),
    ... Tag('p', 299, 420),
    ... Tag('a', 421, 432, {'href': u'Switzerland'}),
    ... Tag('h2', 421, 432),
    ... Tag('p', 433, 584),
    ... Tag('p', 585, 585),
    ... Tag('p', 585, 605),
    ... ]
    >>> convert(Article(text=text,tags=tags))


<h1> (start 0, end 1)
<strong> (start 2, end 3)
<strong> (start 7, end 8)
<a href = English language> (start 33, end 40)
<p> (start 2, end 78)
<h2> (start 79, end 86)
<a href = Germany> (start 87, end 94)
<a href = Austria> (start 99, end 106)
<h3> (start 87, end 106)
<a href = German language> (start 152, end 158)
<p> (start 107, end 298)
<a href = English language> (start 403, end 410)
<p> (start 299, end 420)
<a href = Switzerland> (start 421, end 432)
<h2> (start 421, end 432)
<p> (start 433, end 584)
<p> (start 585, end 585)
<p> (start 585, end 605)


    """
    tagstarts = defaultdict(list)
    tagends = defaultdict(list)

    for t in article.tags:
        tagstarts[t.start].append(t)
        tagends[t.end].append(t)

    for value in tagstarts.itervalues():
        value.sort(key=lambda x: -x.end)

    for value in tagends.itervalues():
        value.sort(key=lambda x: x.end)

    result=[]
    text_len = len(article.text)

    i = 0

    while i < text_len:

        c = article.text[i]

        for tag_end in tagends[i]:
            if tag_end.name in html_tags:
                result.append('</'+tag_end.name+'>')
            else:
                result.append('</span>')

        for tag_start in tagstarts[i]:
            if tag_start.name in html_tags:
                result.append('<')
                result.append(tag_start.name)
                if tag_start.attributes:
                    attrs = ' '.join(['%s="%s"' % item 
                                      for item in tag_start.attributes.iteritems()])
                    result.append(' ')
                    result.append(attrs)
                result.append('>')
            else:
                result.append('<span class="'+tag_start.name+'">')

        if c == '\n':
            #result.append('<br>')
            pass
        elif c.decode('utf8') == u'\u2022':
            result.append('<li>')
        else:
            result.append(c)

        i += 1

    return ''.join(result)


import gtk
import webkit

def create_scrolled_window(widget):
    scrolled_window = gtk.ScrolledWindow()
    scrolled_window.set_shadow_type(gtk.SHADOW_IN)
    scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    scrolled_window.add(widget)
    return scrolled_window


# html = """
# <b>hello</b>
# <img src="/usr/share/sane/xsane/doc/xsane-gimp.jpg">
# <table width="100%">
# <tr>
# <td>a1</td>
# <td>a2</td>
# </tr>
# <tr>
# <td>b1</td>
# <td>b2</td>
# </tr>

# </table>
# """

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
    html = convert(articles[0]())
    view = View(html)
    gtk.main()
