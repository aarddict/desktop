import aar2html
import sys
from PyQt4 import QtGui
from PyQt4 import QtCore
from PyQt4 import QtWebKit

class View(QtWebKit.QWebView):

    def __init__(self, parent=None):

        QtWebKit.QWebView.__init__(self, parent)

        self.resize(640, 480)


if __name__=='__main__':
    from optparse import OptionParser
    optparser = OptionParser()
    opts, args = optparser.parse_args()
    from aarddict.dictionary import Dictionary
    d = Dictionary(args[0])
    title = args[1]
    articles  = list(d[title])
    html = aar2html.convert(articles[0]())

    print html

    app = QtGui.QApplication(sys.argv)
    view = View()
    def link_clicked(url):
        title = str(url.toString())
        print title
        if title.startswith('#'):
            result = view.page().mainFrame().evaluateJavaScript("document.getElementById('%s').scrollIntoView(true);" % title.strip('#'))
            print result.typeName(), result.toString()
        else:
            articles  = list(d[title])
            if articles:
                html = aar2html.convert(articles[0]())
                view.setHtml(html, QtCore.QUrl(title))


    view.linkClicked.connect(link_clicked)
    view.setWindowTitle(title)
    view.setHtml(html, QtCore.QUrl(title))    
    view.page().setLinkDelegationPolicy(QtWebKit.QWebPage.DelegateAllLinks)
    view.show()

    sys.exit(app.exec_())
