#!/usr/bin/env python
import sys
import os
import time
import functools
import webbrowser
import logging

from itertools import groupby

from PyQt4 import QtGui, QtCore
from PyQt4 import QtWebKit

import aar2html
from aarddict.dictionary import (Dictionary, format_title,
                                 DictionaryCollection,
                                 RedirectResolveError,
                                 collation_key,
                                 PRIMARY,
                                 SECONDARY,
                                 TERTIARY,
                                 Article,
                                 split_word,
                                 cmp_words)

dict_access_lock = QtCore.QMutex()

class ToHtmlThread(QtCore.QThread):

    def __init__(self, article, parent=None):
        QtCore.QThread.__init__(self, parent)
        self.article = article
        self.stop_requested = False

    def run(self):
        t0 = time.time()
        result = []
        for c in aar2html.convert(self.article):
            if self.stop_requested:
                return
            result.append(c)

        steps = [aar2html.fix_new_lines,
                 ''.join,
                 aar2html.remove_p_after_h,
                 aar2html.add_notebackrefs
                 ]
        for step in steps:
            if self.stop_requested:
                return
            result = step(result)

        if not self.stop_requested:
            print 'converted "%s" in %s' % (self.article.title.encode('utf8'), time.time() - t0)
            self.emit(QtCore.SIGNAL("html"), self.article, result)

    def stop(self):
        self.stop_requested = True

class ArticleLoadThread(QtCore.QThread):

    def __init__(self, article_read_funcs, parent=None):
        QtCore.QThread.__init__(self, parent)
        self.article_read_funcs = article_read_funcs
        self.stop_requested = False

    def run(self):
        dict_access_lock.lock()
        try:
            for read_func in self.article_read_funcs:
                if self.stop_requested:
                    print 'Stop requested for article load'
                    break
                t0 = time.time()
                try:
                    article = read_func()
                except RedirectResolveError, e:
                    logging.exception()
                    article = Article(e.article.title,
                                      'Redirect to %s not found' % e.article.redirect,
                                      dictionary=e.article.dictionary)
                print 'read "%s" from %s in %s' % (article.title.encode('utf8'), article.dictionary, time.time() - t0)
                self.emit(QtCore.SIGNAL("article_loaded"), read_func, article)
        finally:
            dict_access_lock.unlock()

    def stop(self):
        self.stop_requested = True

class WordInput(QtGui.QLineEdit):

    def keyPressEvent (self, event):
        QtGui.QLineEdit.keyPressEvent(self, event)
        if event.matches(QtGui.QKeySequence.MoveToNextLine):
            self.emit(QtCore.SIGNAL('word_input_down'))
        elif event.matches(QtGui.QKeySequence.MoveToPreviousLine):
            self.emit(QtCore.SIGNAL('word_input_up'))

class DictView(QtGui.QMainWindow):

    def __init__(self):
        QtGui.QMainWindow.__init__(self)

        self.setWindowTitle('Aard Dictionary')

        self.word_input = WordInput()

        # self.word_input.editTextChanged.connect(self.update_word_completion)
        self.connect(self.word_input, QtCore.SIGNAL('textEdited (const QString&)'),
                     self.word_input_text_edited)
        self.word_completion = QtGui.QListWidget()
        self.connect(self.word_input, QtCore.SIGNAL('word_input_down'), self.select_next_word)
        self.connect(self.word_input, QtCore.SIGNAL('word_input_up'), self.select_prev_word)
        self.connect(self.word_input, QtCore.SIGNAL('returnPressed ()'), self.word_completion.setFocus)        
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
        articles = list(self.dictionaries.lookup(wordstr))
        def key(article):
            return collation_key(article.title, TERTIARY).getByteArray()
        articles.sort(key=key)
        for k, g in groupby(articles, key):
            article_group = list(g)
            item = QtGui.QListWidgetItem()
            item.setText(article_group[0].title)
            item.setData(QtCore.Qt.UserRole, QtCore.QVariant(article_group))
            self.word_completion.addItem(item)
        self.select_word(wordstr)

    def select_next_word(self):
        count = self.word_completion.count()
        if not count:
            return
        row = self.word_completion.currentRow()
        if row + 1 < count:
            next_item = self.word_completion.item(row+1)
            self.word_completion.setCurrentItem(next_item)
            self.word_completion.scrollToItem(next_item)

    def select_prev_word(self):
        count = self.word_completion.count()
        if not count:
            return
        row = self.word_completion.currentRow()
        if row > 0:
            next_item = self.word_completion.item(row-1)
            self.word_completion.setCurrentItem(next_item)
            self.word_completion.scrollToItem(next_item)
            
    def word_selection_changed(self, selected, deselected):
        func = functools.partial(self.update_shown_article, selected)
        self.schedule(func, 200)

    def history_selection_changed(self, selected, deselected):
        func = functools.partial(self.update_shown_article, selected)
        self.schedule(func, 200)

    def update_shown_article(self, selected, add_to_history=True):
        self.emit(QtCore.SIGNAL("stop_article_load"))
        self.emit(QtCore.SIGNAL("stop_html"))
        self.tabs.clear()
        if selected:
            article_group = selected.data(QtCore.Qt.UserRole).toPyObject()
            load_thread = ArticleLoadThread(article_group, self)
            self.connect(load_thread, QtCore.SIGNAL("article_loaded"), self.article_loaded, QtCore.Qt.QueuedConnection)
            self.connect(self, QtCore.SIGNAL("stop_article_load"), load_thread.stop)
            load_thread.start()

    def article_loaded(self, article_read_func, article):
        tohtml = ToHtmlThread(article, self)
        self.connect(tohtml, QtCore.SIGNAL("html"), self.article_html_ready, QtCore.Qt.QueuedConnection)
        self.connect(self, QtCore.SIGNAL("stop_html"), tohtml.stop)
        tohtml.start()


    def article_html_ready(self, article, html):
        view = QtWebKit.QWebView()
        self.connect(view, QtCore.SIGNAL('linkClicked (const QUrl&)'),
                     self.link_clicked)
        view.setHtml(html, QtCore.QUrl(article.title))
        view.page().setLinkDelegationPolicy(QtWebKit.QWebPage.DelegateAllLinks)
        s = view.settings()
        s.setUserStyleSheetUrl(QtCore.QUrl(os.path.abspath('aar.css')))
        dict_title = format_title(article.dictionary)
        self.tabs.addTab(view, dict_title)
        self.tabs.setTabToolTip(self.tabs.count() - 1, u'\n'.join((dict_title, article.title)))

        # item = QtGui.QListWidgetItem()
        # item.setText(article_read_f.title)
        # item.setData(QtCore.Qt.UserRole, QtCore.QVariant(article_read_f))
        # self.history_view.addItem(item)

    def select_word(self, word):
        if word is None:
            return
        word, section = split_word(word)
        count = range(self.word_completion.count())
        for strength in (TERTIARY, SECONDARY, PRIMARY):
            for i in count:
                item = self.word_completion.item(i)
                if cmp_words(unicode(item.text()), word, strength=strength) == 0:
                    self.word_completion.setCurrentItem(item)
                    self.word_completion.scrollToItem(item)
                    return
        if count:
            item = self.word_completion.item(0)
            self.word_completion.setCurrentItem(item)
            self.word_completion.scrollToItem(item)


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
    dv.word_input.setFocus()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

