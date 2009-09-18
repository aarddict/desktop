#!/usr/bin/env python
import sys
import os
from itertools import islice
import webbrowser

from PyQt4 import QtGui, QtCore
from PyQt4 import QtWebKit

import aar2html

class DictView(QtGui.QMainWindow):

    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self.dictionary = None
        self.setWindowTitle('Aard Dictionary')

        self.word_input = QtGui.QLineEdit()
        # self.word_input.editTextChanged.connect(self.update_word_completion)
        self.connect(self.word_input, QtCore.SIGNAL('textChanged (const QString&)'), 
                     self.update_word_completion)
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

    def update_word_completion(self, word, to_select=None):
        wordstr = unicode(word).encode('utf8')
        self.word_completion.clear()
        for result in islice(self.dictionary.lookup(wordstr), 10):
            item = QtGui.QListWidgetItem()
            item.setText(result.title)
            item.setData(QtCore.Qt.UserRole, QtCore.QVariant(result))
            self.word_completion.addItem(item)
            if result.title == word:
                self.word_completion.setCurrentItem(item)

    def word_selection_changed(self, selected, deselected):
        self.tabs.clear()
        if selected:
            title = unicode(selected.text())
            article_read_f = selected.data(QtCore.Qt.UserRole).toPyObject()
            view = QtWebKit.QWebView()
            #view.linkClicked.connect(self.link_clicked)
            self.connect(view, QtCore.SIGNAL('linkClicked (const QUrl&)'), 
                         self.link_clicked)
            article = article_read_f()
            article.title = title
            html = aar2html.convert(article)
            view.setHtml(html, QtCore.QUrl(title))
            view.page().setLinkDelegationPolicy(QtWebKit.QWebPage.DelegateAllLinks)
            s = view.settings()
            s.setUserStyleSheetUrl(QtCore.QUrl(os.path.abspath('aar.css')))
            self.tabs.addTab(view, title)
            item = QtGui.QListWidgetItem(selected)
            self.history_view.addItem(item)

    def link_clicked(self, url):
        scheme = url.scheme()
        title = unicode(url.toString())
        if scheme in ('http', 'https', 'ftp', 'sftp'):
            webbrowser.open(title)
        else:            
            self.connect(self.word_completion, QtCore.SIGNAL('currentItemChanged (QListWidgetItem *,QListWidgetItem *)'), 
                     self.word_selection_changed)

            # self.word_completion.currentItemChanged.disconnect(self.word_selection_changed)
            self.word_input.setText(title)
            # self.word_completion.currentItemChanged.connect(self.word_selection_changed)
            self.disconnect(self.word_completion, QtCore.SIGNAL('currentItemChanged (QListWidgetItem *,QListWidgetItem *)'), 
                     self.word_selection_changed)

            self.update_word_completion(title, title)

def main():
    app = QtGui.QApplication(sys.argv)
    dv = DictView()

    from optparse import OptionParser
    optparser = OptionParser()
    opts, args = optparser.parse_args()
    from aarddict.dictionary import Dictionary
    d = Dictionary(args[0])
    dv.dictionary = d
    dv.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

