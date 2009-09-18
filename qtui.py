#!/usr/bin/env python
import sys
import os
import time
import functools
import webbrowser

from PyQt4 import QtGui, QtCore
from PyQt4 import QtWebKit

import aar2html
from aarddict.dictionary import Dictionary, format_title, DictionaryCollection

class ToHtmlThread(QtCore.QThread):

    def __init__(self, article_read_f, add_to_history, parent=None):
        QtCore.QThread.__init__(self, parent)
        self.article_read_f = article_read_f
        self.stop_requested = False
        self.add_to_history = add_to_history

    def run(self):
        t0 = time.time()
        article = self.article_read_f()
        title = self.article_read_f.title
        article.title = title
        print 'read "%s" in %s' % (title.encode('utf8'), time.time() - t0)
        t0 = time.time()
        result = []
        for c in aar2html.convert(article):
            if self.stop_requested:
                print 'conversion of "%s" stopped' % title
                return
            result.append(c)
        result = aar2html.fix_new_lines(result)
        if self.stop_requested:
            print 'conversion of "%s" stopped' % title
            return

        html = ''.join(result)
        if self.stop_requested:
            print 'conversion of "%s" stopped' % title
            return

        html = aar2html.remove_p_after_h(html)
        if self.stop_requested:
            print 'conversion of "%s" stopped' % title
            return

        html = aar2html.add_notebackrefs(html)
        if self.stop_requested:
            print 'conversion of "%s" stopped' % title
            return
        else:
            print 'converted "%s" in %s' % (article.title.encode('utf8'), time.time() - t0)
            self.emit(QtCore.SIGNAL("html"), self.article_read_f, html, self.add_to_history)

    def stop(self):
        self.stop_requested = True


class DictView(QtGui.QMainWindow):

    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        
        self.setWindowTitle('Aard Dictionary')

        self.word_input = QtGui.QLineEdit()
        # self.word_input.editTextChanged.connect(self.update_word_completion)
        self.connect(self.word_input, QtCore.SIGNAL('textEdited (const QString&)'),
                     self.word_input_text_edited)
        self.word_completion = QtGui.QListWidget()

        box = QtGui.QVBoxLayout()
        box.setSpacing(2)
        #we want right margin set to 0 since it borders with splitter
        #(left widget)
        box.setContentsMargins(2, 2, 0, 2)
        box.addWidget(self.word_input)
        box.addWidget(self.word_completion)
        lookup_pane = QtGui.QWidget()
        lookup_pane.setLayout(box)

        self.sidebar = QtGui.QTabWidget()
        self.sidebar.setTabPosition(QtGui.QTabWidget.South)
        self.sidebar.addTab(lookup_pane, 'Lookup')

        self.history_view = QtGui.QListWidget()
        self.sidebar.addTab(self.history_view, 'History')


        self.connect(self.history_view, QtCore.SIGNAL('currentItemChanged (QListWidgetItem *,QListWidgetItem *)'),
                     self.history_selection_changed)

        #self.word_completion.currentItemChanged.connect(self.word_selection_changed)
        self.connect(self.word_completion, QtCore.SIGNAL('currentItemChanged (QListWidgetItem *,QListWidgetItem *)'),
                     self.word_selection_changed)


        splitter = QtGui.QSplitter()
        splitter.addWidget(self.sidebar)
        self.tabs = QtGui.QTabWidget()
        splitter.addWidget(self.tabs)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([100, 300])

        menubar = self.menuBar()
        mn_file = menubar.addMenu('&File')

        style = QtGui.QApplication.instance().style()
        fileIcon = style.standardIcon(QtGui.QStyle.SP_FileIcon)

        exit = QtGui.QAction(fileIcon, 'Exit', self)
        exit.setShortcut('Ctrl+Q')
        exit.setStatusTip('Exit application')
        #exit.triggered.connect(self.close)
        self.connect(exit, QtCore.SIGNAL('triggered()'), self.close)

        mn_file.addAction(exit)

        self.setCentralWidget(splitter)
        self.resize(640, 480)

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.scheduled_func = None

        self.dictionaries = DictionaryCollection()

    def schedule(self, func, delay=500):
        if self.scheduled_func:
            self.disconnect(self.timer, QtCore.SIGNAL('timeout()'), self.scheduled_func)
        self.connect(self.timer, QtCore.SIGNAL('timeout()'), func)
        self.scheduled_func = func
        self.timer.start(delay)

    def word_input_text_edited(self, word):
        func = functools.partial(self.update_word_completion, word)
        self.schedule(func)

    def update_word_completion(self, word, to_select=None):
        wordstr = unicode(word).encode('utf8')
        self.word_completion.clear()
        for result in self.dictionaries.lookup(wordstr):
            item = QtGui.QListWidgetItem()
            item.setText(result.title)
            item.setData(QtCore.Qt.UserRole, QtCore.QVariant(result))
            self.word_completion.addItem(item)
            if result.title == word:
                self.word_completion.setCurrentItem(item)

    def word_selection_changed(self, selected, deselected):
        func = functools.partial(self.update_shown_article, selected)
        self.schedule(func, 200)

    def history_selection_changed(self, selected, deselected):
        func = functools.partial(self.update_shown_article, selected, add_to_history=False)
        self.schedule(func, 200)

    def update_shown_article(self, selected, add_to_history=True):
        self.tabs.clear()
        if selected:
            article_read_f = selected.data(QtCore.Qt.UserRole).toPyObject()
            self.emit(QtCore.SIGNAL("stop_article_load"))
            tohtml = ToHtmlThread(article_read_f, add_to_history, self)
            self.connect(tohtml, QtCore.SIGNAL("html"), self.article_loaded, QtCore.Qt.QueuedConnection)
            self.connect(self, QtCore.SIGNAL("stop_article_load"), tohtml.stop)
            tohtml.start()

    def article_loaded(self, article_read_f, html, add_to_history=True):
        view = QtWebKit.QWebView()
        #view.linkClicked.connect(self.link_clicked)
        self.connect(view, QtCore.SIGNAL('linkClicked (const QUrl&)'),
                     self.link_clicked)
        view.setHtml(html, QtCore.QUrl(article_read_f.title))
        view.page().setLinkDelegationPolicy(QtWebKit.QWebPage.DelegateAllLinks)
        s = view.settings()
        s.setUserStyleSheetUrl(QtCore.QUrl(os.path.abspath('aar.css')))
        self.tabs.addTab(view, format_title(article_read_f.source))

        if add_to_history:
            item = QtGui.QListWidgetItem()
            item.setText(article_read_f.title)
            item.setData(QtCore.Qt.UserRole, QtCore.QVariant(article_read_f))
            self.history_view.addItem(item)

    def link_clicked(self, url):
        scheme = url.scheme()
        title = unicode(url.toString())
        if scheme in ('http', 'https', 'ftp', 'sftp'):
            webbrowser.open(title)
        else:
            self.word_input.setText(title)
            #don't call directly to make sure previous update is unscheduled
            func = functools.partial(self.update_word_completion, title)
            self.schedule(func, 0)


def main():
    app = QtGui.QApplication(sys.argv)
    dv = DictView()
    from optparse import OptionParser
    optparser = OptionParser()
    opts, args = optparser.parse_args()
    dv.dictionaries += [Dictionary(name) for name in args]
    dv.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

