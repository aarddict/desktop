#!/usr/bin/env python
from __future__ import with_statement
import sys
import os
import time
import functools
import webbrowser
import logging

from itertools import groupby

from PyQt4.QtCore import (QObject, Qt, QThread, SIGNAL, QMutex,
                          QTimer, QUrl, QVariant, pyqtProperty, pyqtSlot)
from PyQt4.QtGui import (QWidget, QIcon, QPixmap, QFileDialog,
                         QLineEdit, QHBoxLayout, QVBoxLayout, QAction,
                         QKeySequence, QToolButton,
                         QMainWindow, QListWidget, QListWidgetItem,
                         QTabWidget, QApplication, QStyle,
                         QGridLayout, QSplitter, QProgressDialog)

from PyQt4.QtWebKit import QWebView, QWebPage

import aar2html
import aarddict
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

connect = QObject.connect

log = logging.getLogger(__name__)

def load_file(name):
    path = os.path.join(aarddict.package_dir, name)
    with open(path) as f:
        return f.read()

app_dir = os.path.expanduser('~/.aarddict')
sources_file = os.path.join(app_dir, 'sources')
find_section_js = load_file('aar.js')

class WebPage(QWebPage):

    def javaScriptConsoleMessage (self, message, lineNumber, sourceID):
        log.debug('[js] %s (line %d): %s', sourceID, lineNumber, message)

    def javaScriptAlert (self, originatingFrame, msg):
        log.debug('[js] %s: %s', originatingFrame, msg)

class Matcher(QObject):

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self._result = None

    def _get_result(self):
        return self._result

    result = pyqtProperty(bool, _get_result)

    @pyqtSlot('QString', 'QString', int)
    def match(self, section, candidate, strength):
        if cmp_words(unicode(section),
                     unicode(candidate),
                     strength=strength) == 0:
            self._result = True
        else:
            self._result = False

matcher = Matcher()

dict_access_lock = QMutex()


class WordLookupStopRequested(Exception): pass


class WordLookupThread(QThread):

    def __init__(self, dictionaries, word, parent=None):
        QThread.__init__(self, parent)
        self.dictionaries = dictionaries
        self.word = word
        self.stop_requested = False

    def run(self):
        self.setPriority(QThread.LowestPriority)
        wordstr = unicode(self.word).encode('utf8')
        log.debug("Looking up %s", wordstr)
        articles = []
        dict_access_lock.lock()
        try:
            for article in self.dictionaries.lookup(wordstr):
                if self.stop_requested:
                    raise WordLookupStopRequested
                else:
                    articles.append(article)
                    self.emit(SIGNAL('match_found'), self.word, article)
            if self.stop_requested:
                raise WordLookupStopRequested
        except WordLookupStopRequested:
            self.emit(SIGNAL('stopped'), self.word)
        else:
            self.emit(SIGNAL('done'), self.word, articles)
        finally:
            dict_access_lock.unlock()

    def stop(self):
        self.stop_requested = True


class ArticleLoadStopRequested(Exception): pass


class ArticleLoadThread(QThread):

    def __init__(self, article_read_funcs, parent=None):
        QThread.__init__(self, parent)
        self.article_read_funcs = article_read_funcs
        self.stop_requested = False

    def run(self):
        self.setPriority(QThread.LowestPriority)
        self.emit(SIGNAL("article_load_started"), self.article_read_funcs)
        dict_access_lock.lock()
        try:
            for read_func in self.article_read_funcs:
                article = self._load_article(read_func)
                html = self._tohtml(article)
                title = read_func.title
                self.emit(SIGNAL("article_loaded"), title, article, html)
        except ArticleLoadStopRequested:
            self.emit(SIGNAL("article_load_stopped"), self)
        else:
            self.emit(SIGNAL("article_load_finished"), self, self.article_read_funcs)
        finally:
            dict_access_lock.unlock()
            del self.article_read_funcs

    def _load_article(self, read_func):
        t0 = time.time()
        if self.stop_requested:
            raise ArticleLoadStopRequested
        try:
            article = read_func()
        except RedirectResolveError, e:
            logging.exception()
            article = Article(e.article.title,
                              'Redirect to %s not found' % e.article.redirect,
                              dictionary=e.article.dictionary)
        log.debug('Read "%s" from %s in %ss',
                  article.title.encode('utf8'),
                  article.dictionary, time.time() - t0)
        return article

    def _tohtml(self, article):
        t0 = time.time()
        if self.stop_requested:
            raise ArticleLoadStopRequested
        result = [ '<script>',
                   find_section_js,
                   '</script>'
                   ]
        for c in aar2html.convert(article):
            if self.stop_requested:
                raise ArticleLoadStopRequested
            result.append(c)
        steps = [aar2html.fix_new_lines,
                 ''.join,
                 aar2html.remove_p_after_h,
                 aar2html.add_notebackrefs
                 ]
        for step in steps:
            if self.stop_requested:
                raise ArticleLoadStopRequested
            result = step(result)

        log.debug('Converted "%s" in %ss',
                  article.title.encode('utf8'), time.time() - t0)
        return result


    def stop(self):
        self.stop_requested = True


class DictOpenThread(QThread):

    def __init__(self, sources, parent=None):
        QThread.__init__(self, parent)
        self.sources = sources
        self.stop_requested = False

    def run(self):
        ext = os.path.extsep + 'aar'
        files = []

        for source in self.sources:
            if os.path.isfile(source):
                files.append(source)
            if os.path.isdir(source):
                for f in os.listdir(source):
                    s = os.path.join(source, f)
                    if os.path.isfile(s) and f.lower().endswith(ext):
                        files.append(s)
        self.emit(SIGNAL("dict_open_started"), len(files))
        for candidate in files:
            if self.stop_requested:
                return
            try:
                d = Dictionary(candidate)
            except Exception, e:
                self.emit(SIGNAL("dict_open_failed"), source, str(e))
            else:
                self.emit(SIGNAL("dict_open_succeded"), d)

    def stop(self):
        self.stop_requested = True


class WordInput(QLineEdit):

    def __init__(self, parent=None):
        QLineEdit.__init__(self, parent)
        box = QHBoxLayout()
        action_new_lookup = QAction(self)
        action_new_lookup.setIcon(QIcon(QPixmap(':/trolltech/styles/commonstyle/images/standardbutton-clear-16.png')))
        action_new_lookup.setShortcut(QKeySequence('Ctrl+N'))
        action_new_lookup.setShortcutContext(Qt.WindowShortcut)
        btn_clear = QToolButton()
        btn_clear.setDefaultAction(action_new_lookup)
        btn_clear.setCursor(Qt.ArrowCursor)
        box.addStretch(1)
        box.addWidget(btn_clear, 0)
        box.setSpacing(0)
        box.setContentsMargins(0,0,0,0)
        s = btn_clear.sizeHint()
        self.setLayout(box)
        self.setTextMargins(0, 0, s.width(), 0)
        connect(action_new_lookup, SIGNAL('triggered()'), self.start_new)

    def start_new(self):
        self.setFocus()
        self.selectAll()

    def keyPressEvent (self, event):
        QLineEdit.keyPressEvent(self, event)
        if event.matches(QKeySequence.MoveToNextLine):
            self.emit(SIGNAL('word_input_down'))
        elif event.matches(QKeySequence.MoveToPreviousLine):
            self.emit(SIGNAL('word_input_up'))


def write_sources(sources):
    with open(sources_file, 'w') as f:
        seen = set()
        for source in sources:
            if source not in seen:
                f.write(source)
                f.write('\n')
                seen.add(source)
            else:
                log.debug('Source %s is already written, ignoring', source)

def read_sources():
    if os.path.exists(sources_file):
        return load_file(sources_file).splitlines()
    else:
        return []

class DictView(QMainWindow):

    def __init__(self):
        QMainWindow.__init__(self)

        self.setWindowTitle('Aard Dictionary')

        self.word_input = WordInput()

        connect(self.word_input, SIGNAL('textEdited (const QString&)'),
                     self.word_input_text_edited)
        self.word_completion = QListWidget()
        connect(self.word_input, SIGNAL('word_input_down'), self.select_next_word)
        connect(self.word_input, SIGNAL('word_input_up'), self.select_prev_word)
        connect(self.word_input, SIGNAL('returnPressed ()'),
                     self.word_completion.setFocus)

        box = QVBoxLayout()
        box.setSpacing(2)
        #we want right margin set to 0 since it borders with splitter
        #(left widget)
        box.setContentsMargins(2, 2, 0, 2)
        box.addWidget(self.word_input)
        box.addWidget(self.word_completion)
        lookup_pane = QWidget()
        lookup_pane.setLayout(box)

        self.sidebar = QTabWidget()
        self.sidebar.setTabPosition(QTabWidget.South)
        self.sidebar.addTab(lookup_pane, 'Lookup')
        self.history_view = QListWidget()
        self.sidebar.addTab(self.history_view, 'History')

        style = QApplication.instance().style()
        arrow_back = style.standardIcon(QStyle.SP_ArrowBack)
        arrow_fwd = style.standardIcon(QStyle.SP_ArrowForward)

        action_history_back = QAction(arrow_back, 'Back', self)
        action_history_back.setShortcut('Alt+Left')
        connect(action_history_back, SIGNAL('triggered()'), self.history_back)
        action_history_fwd = QAction(arrow_fwd, 'Forward', self)
        action_history_fwd.setShortcut('Alt+Right')
        connect(action_history_fwd, SIGNAL('triggered()'), self.history_fwd)
        btn_history_back = QToolButton()
        btn_history_back.setDefaultAction(action_history_back)
        btn_history_fwd = QToolButton()
        btn_history_fwd.setDefaultAction(action_history_fwd)
        history_bar_box = QGridLayout()
        history_bar_box.setSpacing(0)
        history_bar_box.setContentsMargins(0,0,0,0)
        history_bar_box.setRowMinimumHeight(0, 16)
        history_bar_box.addWidget(btn_history_back, 0, 0)
        history_bar_box.addWidget(btn_history_fwd, 0, 1)
        history_bar = QWidget()
        history_bar.setLayout(history_bar_box)
        self.sidebar.setCornerWidget(history_bar)

        connect(self.history_view,
                     SIGNAL('currentItemChanged (QListWidgetItem *,QListWidgetItem *)'),
                     self.history_selection_changed)

        connect(self.word_completion,
                     SIGNAL('currentItemChanged (QListWidgetItem *,QListWidgetItem *)'),
                     self.word_selection_changed)

        splitter = QSplitter()
        splitter.addWidget(self.sidebar)
        self.tabs = QTabWidget()
        splitter.addWidget(self.tabs)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([100, 300])

        menubar = self.menuBar()
        mn_file = menubar.addMenu('&Dictionary')

        fileIcon = style.standardIcon(QStyle.SP_FileIcon)

        exit = QAction(fileIcon, 'Exit', self)
        exit.setShortcut('Ctrl+Q')
        exit.setStatusTip('Exit application')
        connect(exit, SIGNAL('triggered()'), self.close)

        mn_file.addAction(exit)

        mn_navigate = menubar.addMenu('&Navigate')
        mn_navigate.addAction(action_history_back)
        mn_navigate.addAction(action_history_fwd)

        self.setCentralWidget(splitter)
        self.resize(640, 480)

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.scheduled_func = None

        self.dictionaries = DictionaryCollection()

        self.preferred_dicts = {}

        connect(self.tabs, SIGNAL('currentChanged (int)'),
                self.article_tab_switched)

        self.current_lookup_thread = None

        openIcon = QIcon(QPixmap(":/trolltech/styles/commonstyle/images/standardbutton-open-16.png"))
        add_dicts = QAction(openIcon, 'Add Dictionaries...', self)
        add_dicts.setShortcut('Ctrl+O')
        add_dicts.setStatusTip('Add dictionaries')
        connect(add_dicts, SIGNAL('triggered()'), self.action_add_dict)

        add_dict_dir = QAction('Add Directory...', self)
        add_dict_dir.setStatusTip('Add dictionary directory')
        connect(add_dict_dir, SIGNAL('triggered()'), self.action_add_dict_dir)

        mn_file.addAction(add_dicts)
        mn_file.addAction(add_dict_dir)
        mn_file.addAction(exit)

        self.sources = []

    def action_add_dict(self):
        self.open_dicts(self.select_files())

    def action_add_dict_dir(self):
        self.open_dicts(self.select_dir())

    def open_dicts(self, sources):

        self.sources += sources
        write_sources(self.sources)

        dict_open_thread = DictOpenThread(sources, self)

        progress = QProgressDialog(self)
        progress.setLabelText("Opening dictionaries...")
        progress.setCancelButtonText("Stop")
        progress.setMinimum(0)
        progress.setMinimumDuration(800)

        def show_loading_dicts_dialog(num):
            progress.setMaximum(num)
            progress.setValue(0)

        connect(dict_open_thread, SIGNAL('dict_open_started'),
                show_loading_dicts_dialog)

        def dict_opened(d):
            progress.setValue(progress.value() + 1)
            log.debug('Opened %s' % d.file_name)
            if d not in self.dictionaries:
                self.dictionaries.append(d)

        def dict_failed(source, error):
            progress.setValue(progress.value() + 1)
            log.error('Failed to open %s: %s', source, error)

        def canceled():
            dict_open_thread.stop()

        connect(progress, SIGNAL('canceled ()'), canceled)
        connect(dict_open_thread, SIGNAL('dict_open_succeded'), dict_opened,
                Qt.QueuedConnection)
        connect(dict_open_thread, SIGNAL('dict_open_failed'), dict_failed,
                Qt.QueuedConnection)
        connect(dict_open_thread, SIGNAL('finished()'),
                lambda: dict_open_thread.setParent(None),
                Qt.QueuedConnection)
        dict_open_thread.start()


    def select_files(self):
        file_names = QFileDialog.getOpenFileNames(self, 'Add Dictionary',
                                                  os.path.expanduser('~'),
                                                  'Aard Dictionary Files (*.aar)')
        return [unicode(name).encode('utf8') for name in file_names]


    def select_dir(self):
        name = QFileDialog.getExistingDirectory (self, 'Add Dictionary Directory',
                                                      os.path.expanduser('~'),
                                                      QFileDialog.ShowDirsOnly)
        return [unicode(name).encode('utf8')]


    def article_tab_switched(self, current_tab_index):
        if current_tab_index > -1:
            web_view = self.tabs.widget(current_tab_index)
            dict_uuid = str(web_view.property('dictionary').toByteArray())
            self.preferred_dicts[dict_uuid] = time.time()

    def schedule(self, func, delay=500):
        if self.scheduled_func:
            self.disconnect(self.timer, SIGNAL('timeout()'), self.scheduled_func)
        connect(self.timer, SIGNAL('timeout()'), func)
        self.scheduled_func = func
        self.timer.start(delay)

    def word_input_text_edited(self, word):
        func = functools.partial(self.update_word_completion, word)
        self.schedule(func)

    def update_word_completion(self, word):
        self.sidebar.setTabText(0, 'Loading...')
        self.word_completion.clear()
        if self.current_lookup_thread:
            self.current_lookup_thread.stop()
            self.current_lookup_thread = None

        word_lookup_thread = WordLookupThread(self.dictionaries, word, self)
        connect(word_lookup_thread, SIGNAL("done"),
                self.word_lookup_finished, Qt.QueuedConnection)
        connect(word_lookup_thread, SIGNAL("finished ()"),
                functools.partial(word_lookup_thread.setParent, None),
                Qt.QueuedConnection)
        self.current_lookup_thread = word_lookup_thread
        word_lookup_thread.start()

    def word_lookup_finished(self, word, articles):
        log.debug('Lookup for %r finished, got %d article(s)', word, len(articles))
        def key(article):
            return collation_key(article.title, TERTIARY).getByteArray()
        articles.sort(key=key)
        for k, g in groupby(articles, key):
            article_group = list(g)
            item = QListWidgetItem()
            item.setText(article_group[0].title)
            item.setData(Qt.UserRole, QVariant(article_group))
            self.word_completion.addItem(item)
        self.select_word(unicode(word))
        self.sidebar.setTabText(0, 'Lookup')
        self.current_lookup_thread = None

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
        title = unicode(selected.text()) if selected else u''
        func = functools.partial(self.set_word_input, title)
        self.schedule(func, 200)

    def update_shown_article(self, selected):
        self.emit(SIGNAL("stop_article_load"))
        self.clear_current_articles()
        if selected:
            self.add_to_history(unicode(selected.text()))
            article_group = selected.data(Qt.UserRole).toPyObject()
            load_thread = ArticleLoadThread(article_group, self)
            connect(load_thread, SIGNAL("article_loaded"),
                    self.article_loaded, Qt.QueuedConnection)
            connect(load_thread, SIGNAL("finished ()"),
                    functools.partial(load_thread.setParent, None),
                    Qt.QueuedConnection)
            connect(load_thread, SIGNAL("article_load_started"),
                    self.article_load_started, Qt.QueuedConnection)
            connect(self, SIGNAL("stop_article_load"),
                    load_thread.stop, Qt.QueuedConnection)
            load_thread.start()

    def clear_current_articles(self):
        self.tabs.blockSignals(True)
        for i in reversed(range(self.tabs.count())):
            w = self.tabs.widget(i)
            self.tabs.removeTab(i)
            p = w.page()
            w.setPage(None)
            w.deleteLater()
            p.deleteLater()
        self.tabs.blockSignals(False)

    def article_loaded(self, title, article, html):
        log.debug('Loaded article "%s" (original title "%s") (section "%s")',
                  article.title, title, article.section)
        for i in range(self.tabs.count()):
            view = self.tabs.widget(i)
            if view.property('loading').toBool():
                view.setProperty('loading', QVariant(False))
                break
        connect(view, SIGNAL('linkClicked (const QUrl&)'),
                     self.link_clicked)

        def loadFinished(ok):
            if ok:
                self.go_to_section(view, article.section)

        if article.section:
            connect(view, SIGNAL('loadFinished (bool)'),
                    loadFinished, Qt.QueuedConnection)

        view.setHtml(html, QUrl(title))
        view.page().setLinkDelegationPolicy(QWebPage.DelegateAllLinks)
        s = view.settings()
        s.setUserStyleSheetUrl(QUrl(os.path.join(aarddict.package_dir,
                                                 'aar.css')))


    def article_load_started(self, read_funcs):
        log.debug('Loading %d article(s)', len(read_funcs))
        self.tabs.blockSignals(True)
        for read_func in read_funcs:
            view = QWebView()
            view.setPage(WebPage(self))
            view.setHtml('Loading...')
            view.setProperty('loading', QVariant(True))
            dictionary = read_func.source
            dict_title = format_title(dictionary)
            view.setProperty('dictionary', QVariant(dictionary.uuid))
            self.tabs.addTab(view, dict_title)
            self.tabs.setTabToolTip(self.tabs.count() - 1,
                                    u'\n'.join((dict_title, read_func.title)))
        self.select_preferred_dict()
        self.tabs.blockSignals(False)

    def select_preferred_dict(self):
        preferred_dict_keys = [item[0] for item
                               in sorted(self.preferred_dicts.iteritems(),
                                         key=lambda x: -x[1])]
        try:
            for i, dict_key in enumerate(preferred_dict_keys):
                for page_num in range(self.tabs.count()):
                    web_view = self.tabs.widget(page_num)
                    dict_uuid = str(web_view.property('dictionary').toByteArray())
                    if dict_uuid == dict_key:
                        self.tabs.setCurrentIndex(page_num)
                        raise StopIteration()
        except StopIteration:
            pass

    def go_to_section(self, view, section):
        mainFrame = view.page().mainFrame()
        mainFrame.addToJavaScriptWindowObject('matcher', matcher)
        js_template = 'scrollToMatch("%s", %%s)' % section
        for strength in (TERTIARY, SECONDARY, PRIMARY):
            js = js_template % strength
            result = mainFrame.evaluateJavaScript(js)
            if result.toBool():
                break

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
            self.set_word_input(title)

    def set_word_input(self, text):
        self.word_input.setText(text)
        #don't call directly to make sure previous update is unscheduled
        func = functools.partial(self.update_word_completion, text)
        self.schedule(func, 0)

    def history_back(self):
        count = self.history_view.count()
        if not count:
            return
        row = self.history_view.currentRow()
        if row + 1 < count:
            next_item = self.history_view.item(row+1)
            self.history_view.setCurrentItem(next_item)
            self.history_view.scrollToItem(next_item)

    def history_fwd(self):
        count = self.history_view.count()
        if not count:
            return
        row = self.history_view.currentRow()
        if row > 0:
            next_item = self.history_view.item(row-1)
            self.history_view.setCurrentItem(next_item)
            self.history_view.scrollToItem(next_item)

    def add_to_history(self, title):
        current_hist_item = self.history_view.currentItem()
        if (not current_hist_item or
            unicode(current_hist_item.text()) != title):
            self.history_view.blockSignals(True)
            if current_hist_item:
                while (self.history_view.count() and
                       self.history_view.item(0) != current_hist_item):
                    self.history_view.takeItem(0)

            item = QListWidgetItem()
            item.setText(title)
            self.history_view.insertItem(0, item)
            self.history_view.setCurrentItem(item)
            self.history_view.blockSignals(False)


def main(args):
    if not os.path.exists(app_dir):
        os.makedirs(app_dir)
    app = QApplication(sys.argv)
    dv = DictView()
    dv.show()
    dv.word_input.setFocus()
    dv.open_dicts(read_sources()+args)
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

