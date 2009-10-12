#!/usr/bin/env python
from __future__ import with_statement
import sys
import os
import time
import functools
import webbrowser
import logging
import string
import locale
import re

from uuid import UUID

from itertools import groupby
from collections import defaultdict

from PyQt4.QtCore import (QObject, Qt, QThread, SIGNAL, QMutex,
                          QTimer, QUrl, QVariant, pyqtProperty, pyqtSlot,
                          QModelIndex, QSize)

from PyQt4.QtGui import (QWidget, QIcon, QPixmap, QFileDialog,
                         QLineEdit, QHBoxLayout, QVBoxLayout, QAction,
                         QKeySequence, QToolButton,
                         QMainWindow, QListWidget, QListWidgetItem,
                         QTabWidget, QApplication, QStyle,
                         QGridLayout, QSplitter, QProgressDialog,
                         QMessageBox, QDialog, QDialogButtonBox, QPushButton,
                         QTableWidget, QTableWidgetItem, QItemSelectionModel)

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
                                 cmp_words,
                                 VerifyError)

connect = QObject.connect

log = logging.getLogger(__name__)

def load_file(name):
    path = os.path.join(aarddict.package_dir, name)
    with open(path) as f:
        return f.read()

app_dir = os.path.expanduser('~/.aarddict')
sources_file = os.path.join(app_dir, 'sources')
history_file = os.path.join(app_dir, 'history')
find_section_js = load_file('aar.js')

max_history = 100

dict_detail_tmpl= string.Template("""
<html>
<body>
<h1>$title $version</h1>
<div style="margin-left:20px;marging-right:20px;">
<p><strong>Volumes: $total_volumes</strong></p>
$volumes
<p><strong>Number of articles:</strong> <em>$num_of_articles</em></p>
</div>
$description
$source
$copyright
$license
</body>
</html>
""")

about_tmpl = string.Template("""
<div align="center">
<h1>$appname $version</h1>
<p>$copyright</p>
<p><a href="$website">$website</a></p>
</div>
<p style="font-size: small;">Distributed under terms and conditions
of <a href="http://www.gnu.org/licenses/gpl-3.0.html">GNU Public License Version 3</a>
</p>
""")

about_html = about_tmpl.substitute(dict(appname=aarddict.__appname__,
                                        version=aarddict.__version__,
                                        website='http://aarddict.org',
                                        copyright='(C) 2006-2009 Igor Tkach, Jeremy Mortis'))

http_link_re = re.compile("http[s]?://[^\s\)]+", re.UNICODE)

iconset = 'gnome'

icon_dir = os.path.join(aarddict.package_dir, 'icons/%s/%%s' % iconset)
print icon_dir

def mkicon(name):
    icon = QIcon()
    for size in ('16x16', '32x32'):
        icon.addFile(os.path.join(icon_dir%size, name+'.png'))
    icon.addFile(os.path.join(icon_dir%'scalable', name+'.svg'))
    return icon

icons = {}

def load_icons():
    icons['edit-find'] = mkicon('actions/edit-find')
    icons['system-search'] = mkicon('actions/system-search')
    icons['list-add'] = mkicon('actions/list-add')
    icons['list-remove'] = mkicon('actions/list-remove')
    icons['go-next'] = mkicon('actions/go-next')
    icons['go-previous'] = mkicon('actions/go-previous')
    icons['view-fullscreen'] = mkicon('actions/view-fullscreen')
    icons['application-exit'] = mkicon('actions/application-exit')
    icons['zoom-in'] = mkicon('actions/zoom-in')
    icons['zoom-out'] = mkicon('actions/zoom-out')
    icons['zoom-original'] = mkicon('actions/zoom-original')
    icons['help-about'] = mkicon('actions/help-about')
    icons['system-run'] = mkicon('actions/system-run')
    icons['document-open-recent'] = mkicon('actions/document-open-recent')
    icons['document-properties'] = mkicon('actions/document-properties')

    icons['folder'] = mkicon('places/folder')
    icons['file'] = mkicon('mimetypes/gtk-file')

    icons['emblem-web'] = mkicon('emblems/emblem-web')
    icons['emblem-default'] = mkicon('emblems/emblem-default')
    icons['emblem-unreadable'] = mkicon('emblems/emblem-unreadable')

    icons['info'] = mkicon('status/info')
    icons['question'] = mkicon('status/dialog-question')
    icons['warning'] = mkicon('status/dialog-warning')


def linkify(text):
    return http_link_re.sub(lambda m: '<a href="%(target)s">%(target)s</a>'
                            % dict(target=m.group(0)), text)

class WebPage(QWebPage):

    def __init__(self, parent=None):
        QWebPage.__init__(self, parent)
        self.setLinkDelegationPolicy(QWebPage.DelegateAllLinks)

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

class VolumeVerifyThread(QThread):

    def __init__(self, volume, parent=None):
        QThread.__init__(self, parent)
        self.volume = volume
        self.stop_requested = False

    def run(self):
        try:
            for progress in self.volume.verify():
                if self.stop_requested:
                    return
                if progress > 1.0:
                    progress = 1.0
                self.emit(SIGNAL("progress"), progress)
        except VerifyError:
            self.emit(SIGNAL("verified"), False)
        else:
            self.emit(SIGNAL("verified"),  True)

    def stop(self):
        self.stop_requested = True


class WordInput(QLineEdit):

    def __init__(self, action, parent=None):
        QLineEdit.__init__(self, parent)
        box = QHBoxLayout()
        btn_clear = QToolButton()
        btn_clear.setDefaultAction(action)
        btn_clear.setCursor(Qt.ArrowCursor)
        box.addStretch(1)
        box.addWidget(btn_clear, 0)
        box.setSpacing(0)
        box.setContentsMargins(0,0,0,0)
        s = btn_clear.sizeHint()
        self.setLayout(box)
        self.setTextMargins(0, 0, s.width(), 0)

    def keyPressEvent (self, event):
        QLineEdit.keyPressEvent(self, event)
        if event.matches(QKeySequence.MoveToNextLine):
            self.emit(SIGNAL('word_input_down'))
        elif event.matches(QKeySequence.MoveToPreviousLine):
            self.emit(SIGNAL('word_input_up'))


class SingleRowItemSelectionModel(QItemSelectionModel):

    def select(self, arg1, arg2):
        super(SingleRowItemSelectionModel, self).select(arg1,
                                                        QItemSelectionModel.Rows |
                                                        QItemSelectionModel.Select |
                                                        QItemSelectionModel.Clear)


def write_sources(sources):
    with open(sources_file, 'w') as f:
        written = list()
        for source in sources:
            if source not in written:
                f.write(source)
                f.write('\n')
                written.append(source)
            else:
                log.debug('Source %s is already written, ignoring', source)
    return written

def read_sources():
    if os.path.exists(sources_file):
        return [source for source
                in load_file(sources_file).splitlines() if source]
    else:
        return []

def write_history(history):
    with open(history_file, 'w') as f:
        f.write('\n'.join(item.encode('utf8') for item in history))

def read_history():
    if os.path.exists(history_file):
        with open(history_file) as f:
            return (line.decode('utf8') for line in f.read().splitlines())
    else:
        return []

class DictView(QMainWindow):

    def __init__(self):
        QMainWindow.__init__(self)

        self.setWindowTitle('Aard Dictionary')


        action_lookup_box = QAction('&Lookup Box', self)
        action_lookup_box.setIcon(icons['edit-find'])
        # action_lookup_box.setIcon(QIcon(QPixmap(':/trolltech/styles/commonstyle/images/standardbutton-clear-16.png')))


        action_lookup_box.setShortcut('Ctrl+L')
        action_lookup_box.setStatusTip('Move focus to word input and select its content')
        connect(action_lookup_box, SIGNAL('triggered()'), self.go_to_lookup_box)

        self.word_input = WordInput(action_lookup_box)

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
        self.sidebar.addTab(lookup_pane, icons['system-search'], '&Lookup')
        self.history_view = QListWidget()
        self.sidebar.addTab(self.history_view, icons['document-open-recent'], '&History')

        action_history_back = QAction(icons['go-previous'], '&Back', self)
        action_history_back.setShortcut('Alt+Left')
        connect(action_history_back, SIGNAL('triggered()'), self.history_back)
        action_history_fwd = QAction(icons['go-next'], '&Forward', self)
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
        splitter.setSizes([100, 500])

        menubar = self.menuBar()
        mn_dictionary = menubar.addMenu('&Dictionary')

        action_add_dicts = QAction(icons['list-add'], '&Add Dictionaries...', self)
        action_add_dicts.setShortcut('Ctrl+O')
        action_add_dicts.setStatusTip('Add dictionaries')
        connect(action_add_dicts, SIGNAL('triggered()'), self.add_dicts)
        mn_dictionary.addAction(action_add_dicts)

        action_add_dict_dir = QAction(icons['folder'], 'Add &Directory...', self)
        action_add_dict_dir.setStatusTip('Add dictionary directory')
        connect(action_add_dict_dir, SIGNAL('triggered()'), self.add_dict_dir)
        mn_dictionary.addAction(action_add_dict_dir)

        action_verify = QAction(icons['system-run'], '&Verify...', self)
        action_verify.setShortcut('Ctrl+Y')
        action_verify.setStatusTip('Verify volume data integrity')
        connect(action_verify, SIGNAL('triggered()'), self.verify)
        mn_dictionary.addAction(action_verify)

        action_remove_dict_source = QAction(icons['list-remove'], '&Remove...', self)
        action_remove_dict_source.setShortcut('Ctrl+R')
        action_remove_dict_source.setStatusTip('Remove dictionary or dictionary directory')
        connect(action_remove_dict_source, SIGNAL('triggered()'), self.remove_dict_source)
        mn_dictionary.addAction(action_remove_dict_source)

        action_info = QAction(icons['document-properties'], '&Info...', self)
        action_info.setShortcut('Ctrl+I')
        action_info.setStatusTip('Information about open dictionaries')
        connect(action_info, SIGNAL('triggered()'), self.show_info)
        mn_dictionary.addAction(action_info)

        action_quit = QAction(icons['application-exit'], '&Quit', self)
        action_quit.setShortcut('Ctrl+Q')
        action_quit.setStatusTip('Exit application')
        connect(action_quit, SIGNAL('triggered()'), self.close)
        mn_dictionary.addAction(action_quit)

        mn_navigate = menubar.addMenu('&Navigate')

        mn_navigate.addAction(action_lookup_box)

        mn_navigate.addAction(action_history_back)
        mn_navigate.addAction(action_history_fwd)

        action_next_article = QAction('&Next Article', self)
        action_next_article.setShortcut('Ctrl+.')
        action_next_article.setStatusTip('Show next article')
        connect(action_next_article, SIGNAL('triggered()'), self.show_next_article)
        mn_navigate.addAction(action_next_article)

        action_prev_article = QAction('&Previous Article', self)
        action_prev_article.setShortcut('Ctrl+,')
        action_prev_article.setStatusTip('Show previous article')
        connect(action_prev_article, SIGNAL('triggered()'), self.show_prev_article)
        mn_navigate.addAction(action_prev_article)


        action_online_article = QAction(icons['emblem-web'], '&Online Article', self)
        action_online_article.setShortcut('Ctrl+T')
        action_online_article.setStatusTip('Open online version of this article in a web browser')
        connect(action_online_article, SIGNAL('triggered()'), self.show_article_online)
        mn_navigate.addAction(action_online_article)

        mn_view = menubar.addMenu('&View')

        mn_text_size = mn_view.addMenu('Text &Size')

        action_increase_text = QAction(icons['zoom-in'], '&Increase', self)
        action_increase_text.setShortcut('Ctrl+=')
        connect(action_increase_text, SIGNAL('triggered()'), self.increase_text_size)
        mn_text_size.addAction(action_increase_text)

        action_decrease_text = QAction(icons['zoom-out'], '&Decrease', self)
        action_decrease_text.setShortcut('Ctrl+-')
        connect(action_decrease_text, SIGNAL('triggered()'), self.decrease_text_size)
        mn_text_size.addAction(action_decrease_text)

        action_reset_text = QAction(icons['zoom-original'], '&Reset', self)
        action_reset_text.setShortcut('Ctrl+0')
        connect(action_reset_text, SIGNAL('triggered()'), self.reset_text_size)
        mn_text_size.addAction(action_reset_text)

        action_full_screen = QAction(icons['view-fullscreen'], '&Full Screen', self)
        action_full_screen.setShortcut('F11')
        action_full_screen.setStatusTip('Toggle full screen mode')
        action_full_screen.setCheckable(True)
        connect(action_full_screen, SIGNAL('triggered(bool)'), self.toggle_full_screen)
        mn_view.addAction(action_full_screen)

        mn_help = menubar.addMenu('H&elp')

        action_about = QAction(icons['help-about'], '&About...', self)
        connect(action_about, SIGNAL('triggered(bool)'), self.about)
        mn_help.addAction(action_about)


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

        self.sources = []
        self.zoom_factor = 1.0

    def add_dicts(self):
        self.open_dicts(self.select_files())

    def add_dict_dir(self):
        self.open_dicts(self.select_dir())

    def open_dicts(self, sources):

        self.sources = write_sources(self.sources + sources)

        dict_open_thread = DictOpenThread(sources, self)

        progress = QProgressDialog(self)
        progress.setLabelText("Opening dictionaries...")
        progress.setCancelButtonText("Stop")
        progress.setMinimum(0)
        progress.setMinimumDuration(800)

        errors = []

        def show_loading_dicts_dialog(num):
            progress.setMaximum(num)
            progress.setValue(0)

        connect(dict_open_thread, SIGNAL('dict_open_started'),
                show_loading_dicts_dialog)

        def dict_opened(d):
            progress.setValue(progress.value() + 1)
            log.debug('Opened %s' % d.file_name)
            count = 0
            if d not in self.dictionaries:
                self.dictionaries.append(d)
                count += 1
            if count:
                func = functools.partial(self.update_word_completion,
                                         self.word_input.text())
                self.schedule(func, 0)

        def dict_failed(source, error):
            errors.append((source, error))
            progress.setValue(progress.value() + 1)
            log.error('Failed to open %s: %s', source, error)

        def canceled():
            dict_open_thread.stop()

        def finished():
            dict_open_thread.setParent(None)
            if errors:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle('Open Failed')
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setInformativeText('Failed to open some dictionaries')
                msg_box.setDetailedText('\n'.join('%s: %s' % error for error in errors))
                msg_box.setStandardButtons(QMessageBox.Ok)
                msg_box.open()

        connect(progress, SIGNAL('canceled ()'), canceled)
        connect(dict_open_thread, SIGNAL('dict_open_succeded'), dict_opened,
                Qt.QueuedConnection)
        connect(dict_open_thread, SIGNAL('dict_open_failed'), dict_failed,
                Qt.QueuedConnection)
        connect(dict_open_thread, SIGNAL('finished()'),
                finished,
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

    def remove_dict_source(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Remove Dictionaries')
        content = QVBoxLayout()

        item_list = QListWidget()
        item_list.setSelectionMode(QListWidget.MultiSelection)

        for source in self.sources:
            item = QListWidgetItem(source)
            if os.path.exists(source):
                if os.path.isfile(source):
                    item.setData(Qt.DecorationRole, icons['file'])
                elif os.path.isdir(source):
                    item.setData(Qt.DecorationRole, icons['folder'])
                else:
                    item.setData(Qt.DecorationRole, icons['question'])
            else:
                item.setData(Qt.DecorationRole, icons['warning'])
            item_list.addItem(item)

        content.addWidget(item_list)

        dialog.setLayout(content)
        button_box = QDialogButtonBox()

        btn_select_all = QPushButton('Select &All')
        button_box.addButton(btn_select_all, QDialogButtonBox.ActionRole)

        connect(btn_select_all, SIGNAL('clicked()'), item_list.selectAll)

        btn_remove = QPushButton('&Remove')

        def remove():
            rows = [index.row() for index in item_list.selectedIndexes()]
            for row in reversed(sorted(rows)):
                item_list.takeItem(row)
            if rows:
                remaining = [unicode(item_list.item(i).text()).encode('utf8')
                             for i in range(item_list.count())]
                self.cleanup_sources(remaining)

        connect(btn_remove, SIGNAL('clicked()'), remove)

        button_box.addButton(btn_remove, QDialogButtonBox.ApplyRole)
        button_box.setStandardButtons(QDialogButtonBox.Close)

        content.addWidget(button_box)

        connect(button_box, SIGNAL('rejected()'), dialog.reject)

        dialog.exec_()

    def cleanup_sources(self, remaining):
        to_be_removed = []

        for dictionary in self.dictionaries:
            f = dictionary.file_name
            if f in remaining or os.path.dirname(f) in remaining:
                continue
            else:
                to_be_removed.append(dictionary)

        for dictionary in to_be_removed:
            self.dictionaries.remove(dictionary)
            dictionary.close()

        self.sources = write_sources(remaining)

        if to_be_removed:
            func = functools.partial(self.update_word_completion, self.word_input.text())
            self.schedule(func, 0)

    def article_tab_switched(self, current_tab_index):
        if current_tab_index > -1:
            web_view = self.tabs.widget(current_tab_index)
            dict_uuid = str(web_view.property('aard:dictionary').toByteArray())
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
        self.sidebar.setTabText(0, '&Lookup')
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
            if view.property('aard:loading').toBool():
                view.setProperty('aard:loading', QVariant(False))
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
        view.setZoomFactor(self.zoom_factor)
        view.setProperty('aard:title', QVariant(article.title))
        s = view.settings()
        s.setUserStyleSheetUrl(QUrl(os.path.join(aarddict.package_dir,
                                                 'aar.css')))


    def article_load_started(self, read_funcs):
        log.debug('Loading %d article(s)', len(read_funcs))
        self.tabs.blockSignals(True)
        for i, read_func in enumerate(read_funcs):
            view = QWebView()
            view.setPage(WebPage(self))
            view.setHtml('Loading...')
            view.setZoomFactor(self.zoom_factor)
            view.setProperty('aard:loading', QVariant(True))
            dictionary = read_func.source
            dict_title = format_title(dictionary)
            view.setProperty('aard:dictionary', QVariant(dictionary.uuid))
            view.setProperty('aard:volume', QVariant(dictionary.key()))
            if i < 9:
                tab_label = ('&%d ' % (i+1))+dict_title
            else:
                tab_label = dict_title
            self.tabs.addTab(view, tab_label)
            self.tabs.setTabToolTip(self.tabs.count() - 1,
                                    u'\n'.join((dict_title, read_func.title)))
        self.select_preferred_dict()
        self.tabs.blockSignals(False)

    def show_next_article(self):
        current = self.tabs.currentIndex()
        count = self.tabs.count()
        new_current = current + 1
        if new_current < count:
            self.tabs.setCurrentIndex(new_current)

    def show_prev_article(self):
        current = self.tabs.currentIndex()
        count = self.tabs.count()
        new_current = current - 1
        if new_current > -1:
            self.tabs.setCurrentIndex(new_current)

    def show_article_online(self):
        url = self.get_current_article_url()
        if url is not None:
            logging.debug('Opening url %r', url)
            webbrowser.open(url)

    def get_current_article_url(self):
        count = self.tabs.count()
        if count:
            current_tab = self.tabs.currentWidget()
            article_title = unicode(current_tab.property('aard:title').toString())
            if not article_title:
                return None
            dictionary_key = unicode(current_tab.property('aard:volume').toString())
            dictionary_list = [d for d in self.dictionaries if d.key() == dictionary_key]
            if len(dictionary_list) == 0:
                return None
            dictionary = dictionary_list[0]
            try:
                siteinfo = dictionary.metadata['siteinfo']
            except KeyError:
                logging.debug('No site info in dictionary %s', dictionary_key)
                if 'lang' in dictionary.metadata and 'sitelang' in dictionary.metadata:
                    url = u'http://%s.wikipedia.org/wiki/%s' % (dictionary.metadata['lang'],
                                                                article_title)
                    return url
            else:
                try:
                    general = siteinfo['general']
                    server = general['server']
                    articlepath = general['articlepath']
                except KeyError:
                    logging.debug('Site info for %s is incomplete', dictionary_key)
                else:
                    url = ''.join((server, articlepath.replace(u'$1', article_title)))
                    return url

    def select_preferred_dict(self):
        preferred_dict_keys = [item[0] for item
                               in sorted(self.preferred_dicts.iteritems(),
                                         key=lambda x: -x[1])]
        try:
            for i, dict_key in enumerate(preferred_dict_keys):
                for page_num in range(self.tabs.count()):
                    web_view = self.tabs.widget(page_num)
                    dict_uuid = str(web_view.property('aard:dictionary').toByteArray())
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
            while self.history_view.count() > max_history:
                self.history_view.takeItem(self.history_view.count() - 1)
            self.history_view.blockSignals(False)

    def toggle_full_screen(self, full_screen):
        if full_screen:
            self.showFullScreen()
        else:
             self.showNormal()

    def increase_text_size(self):
        self.set_zoom_factor(self.zoom_factor*1.1)

    def decrease_text_size(self):
        self.set_zoom_factor(self.zoom_factor*0.9)

    def reset_text_size(self):
        self.set_zoom_factor(1.0)

    def set_zoom_factor(self, zoom_factor):
        self.zoom_factor = zoom_factor
        for i in range(self.tabs.count()):
            web_view = self.tabs.widget(i)
            web_view.setZoomFactor(self.zoom_factor)

    def go_to_lookup_box(self):
        self.word_input.setFocus()
        self.word_input.selectAll()

    def verify(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Verify')
        content = QVBoxLayout()

        item_list = QTableWidget()
        item_list.setRowCount(len(self.dictionaries))
        item_list.setColumnCount(2)
        item_list.setHorizontalHeaderLabels(['Status', 'Volume'])
        item_list.setSelectionMode(QTableWidget.SingleSelection)
        item_list.setEditTriggers(QTableWidget.NoEditTriggers)
        item_list.verticalHeader().setVisible(False)
        item_list.setSelectionModel(SingleRowItemSelectionModel(item_list.model()))

        for i, dictionary in enumerate(self.dictionaries):
            text = format_title(dictionary)
            item = QTableWidgetItem(text)
            item.setData(Qt.UserRole, QVariant(dictionary.key()))
            item_list.setItem(i, 1, item)
            item = QTableWidgetItem('Unverified')
            item.setData(Qt.DecorationRole, icons['question'])
            item_list.setItem(i, 0, item)

        item_list.horizontalHeader().setStretchLastSection(True)
        item_list.resizeColumnToContents(0)

        content.addWidget(item_list)

        dialog.setLayout(content)
        button_box = QDialogButtonBox()

        btn_verify = QPushButton('&Verify')

        def verify():
            current_row = item_list.currentRow()
            item = item_list.item(current_row, 1)
            dict_key = str(item.data(Qt.UserRole).toString())
            volume = [d for d in self.dictionaries if d.key() == dict_key][0]
            verify_thread = VolumeVerifyThread(volume)
            progress = QProgressDialog(dialog)
            progress.setWindowTitle('Verifying...')
            progress.setLabelText(format_title(volume))
            progress.setValue(0)
            progress.forceShow()

            def update_progress(num):
                progress.setValue(100*num)

            def verified(isvalid):
                status_item = item_list.item(current_row, 0)
                if isvalid:
                    status_item.setText('Ok')
                    status_item.setData(Qt.DecorationRole, icons['emblem-default'])
                else:
                    status_item.setText('Corrupt')
                    status_item.setData(Qt.DecorationRole, icons['emblem-unreadable'])

            def finished():
                verify_thread.volume = None
                verify_thread.setParent(None)

            connect(progress, SIGNAL('canceled ()'), verify_thread.stop, Qt.QueuedConnection)
            connect(verify_thread, SIGNAL('progress'), update_progress,
                    Qt.QueuedConnection)
            connect(verify_thread, SIGNAL('verified'), verified,
                    Qt.QueuedConnection)
            connect(verify_thread, SIGNAL('finished()'), finished,
                    Qt.QueuedConnection)
            verify_thread.start()


        connect(btn_verify, SIGNAL('clicked()'), verify)

        button_box.addButton(btn_verify, QDialogButtonBox.ApplyRole)
        button_box.setStandardButtons(QDialogButtonBox.Close)

        content.addWidget(button_box)

        connect(button_box, SIGNAL('rejected()'), dialog.reject)

        dialog.exec_()

    def show_info(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Dictionary Info')
        content = QVBoxLayout()

        item_list = QListWidget()

        dictmap = defaultdict(list)

        for dictionary in self.dictionaries:
            dictmap[UUID(bytes=dictionary.uuid).hex].append(dictionary)

        for uuid_hex, dicts in dictmap.iteritems():
            text = format_title(dicts[0], with_vol_num=False)
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, QVariant(uuid_hex))
            item_list.addItem(item)

        splitter = QSplitter()
        splitter.addWidget(item_list)
        detail_view = QWebView()
        detail_view.setPage(WebPage(self))

        connect(detail_view, SIGNAL('linkClicked (const QUrl&)'),
                     self.link_clicked)

        splitter.addWidget(detail_view)
        splitter.setSizes([100, 300])

        content.addWidget(splitter)

        dialog.setLayout(content)
        button_box = QDialogButtonBox()

        button_box.setStandardButtons(QDialogButtonBox.Close)

        content.addWidget(button_box)

        def current_changed(current, old_current):
            uuid_hex = str(current.data(Qt.UserRole).toString())
            volumes = dictmap[uuid_hex]

            if volumes:
                volumes = sorted(volumes, key=lambda v: v.volume)
                d = volumes[0]
                volumes_str = '<br>'.join(('<strong>Volume %s:</strong> <em>%s</em>' %
                                           (v.volume, v.file_name))
                                          for v in volumes)

                params = dict(title=d.title, version=d.version,
                              total_volumes=d.total_volumes,
                              volumes=volumes_str,
                              num_of_articles=locale.format("%u", d.article_count, True)
                              )

                if d.description:
                    params['description'] = '<p>%s</p>' % linkify(d.description)
                if d.source:
                    params['source'] = '<h2>Source</h2>%s' % linkify(d.source)
                if d.copyright:
                    params['copyright'] = '<h2>Copyright Notice</h2>%s' % linkify(d.copyright)
                if d.license:
                    params['license'] = '<h2>License</h2><pre>%s</pre>' % d.license

                html = dict_detail_tmpl.safe_substitute(params)
            else:
                html = ''
            detail_view.setHtml(html)

        connect(item_list,
                SIGNAL('currentItemChanged (QListWidgetItem *,QListWidgetItem *)'),
                current_changed)


        connect(button_box, SIGNAL('rejected()'), dialog.reject)

        dialog.setSizeGripEnabled(True)
        dialog.exec_()

    def about(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('About')
        content = QVBoxLayout()

        class WebView(QWebView):

            def sizeHint(self):
                return QSize(300, 200)

        detail_view = WebView()
        detail_view.setPage(WebPage(self))

        detail_view.setHtml(about_html)

        connect(detail_view, SIGNAL('linkClicked (const QUrl&)'),
                     self.link_clicked)

        content.addWidget(detail_view)

        dialog.setLayout(content)
        button_box = QDialogButtonBox()

        button_box.setStandardButtons(QDialogButtonBox.Close)

        content.addWidget(button_box)

        connect(button_box, SIGNAL('rejected()'), dialog.reject)

        dialog.setSizeGripEnabled(True)
        dialog.exec_()

    def close(self):
        history = []
        for i in reversed(range(self.history_view.count())):
            item = self.history_view.item(i)
            history.append(unicode(item.text()))
        write_history(history)
        QMainWindow.close(self)

def main(args):
    if not os.path.exists(app_dir):
        os.makedirs(app_dir)
    app = QApplication(sys.argv)
    load_icons()
    dv = DictView()
    dv.show()
    dv.word_input.setFocus()
    dv.open_dicts(read_sources()+args)
    for title in read_history():
        dv.add_to_history(title)
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()



