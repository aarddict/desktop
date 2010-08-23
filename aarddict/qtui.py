# This file is part of Aard Dictionary <http://aarddict.org>.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License <http://www.gnu.org/licenses/gpl-3.0.txt>
# for more details.
#
# Copyright (C) 2010 Igor Tkach

from __future__ import with_statement
import sys
import os
import time
import functools
import webbrowser
import logging
import locale
import re
import traceback

from collections import defaultdict, deque

from PyQt4.QtCore import (QObject, Qt, QThread, QTranslator, QLocale,
                          QTimer, QUrl, QVariant, pyqtProperty, pyqtSlot,
                          QSize, QByteArray, QPoint,
                          pyqtSignal, QString, QEvent)

from PyQt4.QtGui import (QWidget, QIcon, QPixmap, QFileDialog,
                         QLineEdit, QHBoxLayout, QVBoxLayout, QAction,
                         QKeySequence, QMainWindow, QListWidget,
                         QListWidgetItem, QTabWidget, QApplication,
                         QGridLayout, QSplitter, QProgressDialog,
                         QMessageBox, QDialog, QDialogButtonBox, QPushButton,
                         QTableWidget, QTableWidgetItem, QItemSelectionModel,
                         QDockWidget, QToolBar, QColor, QLabel,
                         QColorDialog, QCheckBox, QKeySequence, QPalette,
                         QMenu, QShortcut, QFontDialog, QFont, QToolButton)

from PyQt4.QtWebKit import QWebView, QWebPage, QWebSettings

import aarddict
from aarddict.dictionary import (format_title,
                                 Volume,
                                 Library,
                                 TooManyRedirects,
                                 ArticleNotFound,
                                 collation_key,
                                 PRIMARY,
                                 SECONDARY,
                                 TERTIARY,
                                 Entry,
                                 Article,
                                 cmp_words,
                                 VerifyError)

from aarddict import state, res
from aarddict.res import icons

log = logging.getLogger(__name__)

style_tag_re = re.compile(u'<style type="text/css">(.+?)</style>',
                          re.UNICODE | re.DOTALL)
http_link_re = re.compile("http[s]?://[^\s\)]+",
                          re.UNICODE)
max_history = 50


def linkify(text):
    return http_link_re.sub(lambda m: '<a href="%(target)s">%(target)s</a>'
                            % dict(target=m.group(0)), text)


class WebPage(QWebPage):

    def __init__(self, parent=None):
        QWebPage.__init__(self, parent)
        self.setLinkDelegationPolicy(QWebPage.DelegateAllLinks)

    def javaScriptConsoleMessage (self, message, lineNumber, sourceID):
        log.debug('[js] %r (line %d): %r', sourceID, lineNumber, message)

    def javaScriptAlert (self, originatingFrame, msg):
        log.debug('[js] %r: %r', originatingFrame, msg)


class WebView(QWebView):

    def __init__(self, entry=None, parent=None):
        QWebView.__init__(self, parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu_requested)
        self.entry = entry
        self.article = None
        self.loading = False
        self.actions = []

        def copy_link():
            self.page().triggerAction(QWebPage.CopyLinkToClipboard)
        self.action_copy_link = QAction(_('Copy Lin&k'), self, triggered=copy_link)


    title = property(lambda self: self.entry.title)

    def context_menu_requested(self, point):
        context_menu = QMenu()

        for action in self.actions:
            if action.isEnabled():
                context_menu.addAction(action)

        frame = self.page().currentFrame()

        hit_test = frame.hitTestContent(point)
        if unicode(hit_test.linkUrl().toString()):
            context_menu.addAction(self.action_copy_link)

        if self.settings().testAttribute(QWebSettings.DeveloperExtrasEnabled):
            context_menu.addSeparator()
            context_menu.addAction(self.pageAction(QWebPage.InspectElement))

        context_menu.exec_(self.mapToGlobal(point))


class SizedWebView(WebView):

    def __init__(self, size_hint, parent=None):
        WebView.__init__(self, parent)
        self.size_hint = size_hint

    def sizeHint(self):
        return self.size_hint


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


class WordLookupStopRequested(Exception): pass


class WordLookupThread(QThread):

    match_found = pyqtSignal(QString, object)
    stopped = pyqtSignal(QString)
    done = pyqtSignal(QString, list)
    lookup_failed = pyqtSignal(QString, QString)

    def __init__(self, dictionaries, word, parent=None):
        QThread.__init__(self, parent)
        self.dictionaries = dictionaries
        self.word = word
        self.stop_requested = False

    def run(self):
        wordstr = unicode(self.word)
        log.debug("Looking up %r", wordstr)
        t0 = time.time()
        entries = []
        try:
            for entry in self.dictionaries.best_match(wordstr):
                if self.stop_requested:
                    raise WordLookupStopRequested
                else:
                    entries.append(entry)
                    self.match_found.emit(self.word, entry)
            if self.stop_requested:
                raise WordLookupStopRequested
        except WordLookupStopRequested:
            self.stopped.emit(self.word)
        except Exception:
            self.lookup_failed.emit(self.word,
                                    u''.join(traceback.format_exc()))
        else:
            log.debug('Looked up %r in %ss', wordstr, time.time() - t0)
            self.done.emit(self.word, entries)

    def stop(self):
        self.stop_requested = True


class ArticleLoadThread(QThread):

    article_loaded = pyqtSignal(WebView)
    article_load_failed = pyqtSignal(WebView, QString)

    def __init__(self, dictionaries, view, parent=None):
        QThread.__init__(self, parent)
        self.dictionaries = dictionaries
        self.view = view
        self.view.loading = True

    def run(self):
        try:
            article = self._load_article(self.view.entry)
            redirect = None if article.entry == self.view.entry else self.view.entry.title
            article.text = res.article(article.text, redirect)
        except:
            log.exception('Failed to load article for %r', self.view.entry)
            self.article_load_failed.emit(self.view,
                                          u''.join(traceback.format_exc()))
        else:
            self.view.article = article
            self.view.loading = False
            self.article_loaded.emit(self.view)
        finally:
            del self.view
            del self.dictionaries

    def _load_article(self, entry):
        t0 = time.time()
        try:
            article = self.dictionaries.read(entry)
        except ArticleNotFound, e:
            log.debug('Article not found', exc_info=1)
            article = Article(entry,
                              _('Article "%s" not found') % e.entry.title)
        except TooManyRedirects, e:
            log.debug('Failed to resolve redirect', exc_info=1)
            article = Article(entry,
                              _('Too many redirects for "%s"') % e.entry.title)
        log.debug('Read %r from %s in %ss',
                  entry.title, entry.volume_id, time.time() - t0)
        return article


class DictOpenThread(QThread):

    dict_open_failed = pyqtSignal(str, str)
    dict_open_succeded = pyqtSignal(Volume)
    dict_open_started = pyqtSignal(int)

    def __init__(self, sources, dictionaries, parent=None):
        QThread.__init__(self, parent)
        self.sources = sources
        self.stop_requested = False
        self.dictionaries = dictionaries

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
        self.dict_open_started.emit(len(files))
        for candidate in files:
            if self.stop_requested:
                return
            try:
                vol = self.dictionaries.add(candidate)
            except Exception, e:
                self.dict_open_failed.emit(candidate, str(e))
            else:
                self.dict_open_succeded.emit(vol)

    def stop(self):
        self.stop_requested = True


class VolumeVerifyThread(QThread):

    verified = pyqtSignal(bool)
    progress = pyqtSignal(float)

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
                if not self.stop_requested:
                    self.progress.emit(progress)
        except VerifyError:
            self.verified.emit(False)
        else:
            self.verified.emit(True)

    def stop(self):
        self.stop_requested = True


class LineEditWithClear(QLineEdit):

    cleared = pyqtSignal()

    pass_keys = (QKeySequence.MoveToNextLine,
                 QKeySequence.MoveToPreviousLine,
                 QKeySequence.MoveToNextPage,
                 QKeySequence.MoveToPreviousPage,
                 QKeySequence.MoveToStartOfDocument,
                 QKeySequence.MoveToEndOfDocument)

    def __init__(self, pass_target=None, parent=None):
        QLineEdit.__init__(self, parent)

        self.action_clear = QAction(icons['edit-clear'], _('Clear'), self,
                               triggered=self.clear)
        self.action_clear.setToolTip(_('Clear'))

        btn_clear = QToolButton(self)
        btn_clear.setToolButtonStyle(Qt.ToolButtonIconOnly)
        btn_clear.setIconSize(QSize(16,16))
        btn_clear.setDefaultAction(self.action_clear)
        btn_clear.setCursor(Qt.ArrowCursor)
        btn_clear.setStyleSheet('QToolButton {border: transparent;}')

        box = QHBoxLayout()
        box.addStretch(1)
        box.addWidget(btn_clear, 0)
        box.setSpacing(0)
        box.setContentsMargins(0, 0, 0, 0)
        self.setLayout(box)

        left, top, right, bottom = self.getTextMargins()
        right = max(right, btn_clear.iconSize().width() + 1)
        self.setTextMargins(left, top, right, bottom)
        self.pass_target = pass_target

    def _real_pass_target(self):
        if callable(self.pass_target):
            return self.pass_target()
        else:
            return self.pass_target

    def keyReleaseEvent (self, event):
        if any(event.matches(k) for k in self.pass_keys):
            target = self._real_pass_target()
            if target:
                target.keyReleaseEvent(event)
                return
        QLineEdit.keyReleaseEvent(self, event)

    def keyPressEvent (self, event):
        if any(event.matches(k) for k in self.pass_keys):
            target = self._real_pass_target()
            if target:
                target.keyPressEvent(event)
                return
        QLineEdit.keyPressEvent(self, event)

    def setClearShortcut(self, shortcut):
        self.action_clear.setShortcut(shortcut)

    def clear(self):
        self.setFocus()
        self.setText('')
        self.cleared.emit()


class FindWidget(QToolBar):

    def __init__(self, tabs, parent=None):
        QToolBar.__init__(self, _('&Find'), parent)
        self.tabs = tabs
        self.setIconSize(QSize(16,16))
        self.find_input = LineEditWithClear(self.tabs.currentWidget)
        self.find_input.textEdited.connect(self.find_in_article)

        lbl_find = QLabel(_('&Find:'))
        lbl_find.setStyleSheet('padding-right: 2px;')
        lbl_find.setBuddy(self.find_input)
        find_action_close = QAction(icons['window-close'], '', self,
                                    triggered=self.hide)
        find_action_close.setToolTip(_('Close Find bar'))
        self.addAction(find_action_close)
        self.addWidget(lbl_find)
        self.addWidget(self.find_input)
        find_action_prev = QAction(icons['go-previous'], '', self,
                                   triggered=lambda: self.find_in_article(forward=False))
        find_action_prev.setToolTip(_('Find the previous occurence of the phrase'))
        self.addAction(find_action_prev)

        find_action_next = QAction(icons['go-next'], '', self,
                               triggered=lambda: self.find_in_article(forward=True))
        find_action_next.setToolTip(_('Find the next occurence of the phrase'))
        self.addAction(find_action_next)

        self.cb_find_match_case = QCheckBox(_('&Match Case'))
        self.addWidget(self.cb_find_match_case)

    def find_in_article(self, word=None, forward=True):
        if word is None:
            word = self.find_input.text()
        current_tab = self.tabs.currentWidget()
        if current_tab:
            page = current_tab.page()
            flags = QWebPage.FindWrapsAroundDocument
            if self.cb_find_match_case.isChecked():
                flags = flags | QWebPage.FindCaseSensitively
            if not forward:
                flags = flags | QWebPage.FindBackward
            page.findText(word, flags)

    def keyPressEvent (self, event):
        key = event.key()
        modifiers = event.modifiers()
        if key == Qt.Key_Return or key == Qt.Key_Enter:
            if modifiers == Qt.NoModifier:
                self.find_in_article(forward=True)
            elif modifiers == Qt.ShiftModifier:
                self.find_in_article(forward=False)
        else:
            QToolBar.keyPressEvent(self, event)


class SingleRowItemSelectionModel(QItemSelectionModel):

    def select(self, arg1, _arg2):
        super(SingleRowItemSelectionModel, self).select(arg1,
                                                        QItemSelectionModel.Rows |
                                                        QItemSelectionModel.Select |
                                                        QItemSelectionModel.Clear)


class TabWidget(QTabWidget):

    def __init__(self):
        QTabWidget.__init__(self)
        self.setDocumentMode(True)
        content = QVBoxLayout()
        self.status = QLabel(self)
        c = QApplication.palette().color(QPalette.Disabled,
                                         QPalette.WindowText)
        self.status.setStyleSheet('QLabel {color: rgb(%s,%s,%s);}' %
                                  (c.red(), c.green(), c.blue()))
        self.status.setTextFormat(Qt.RichText)
        self.status.setWordWrap(True)
        self.status.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
        content.addSpacing(self.tabBar().geometry().height())
        content.addWidget(self.status, 1)
        self.setLayout(content)

    def _update_message_visibility(self):
        if self.count():
            self.status.hide()
        else:
            self.status.show()

    def addTab(self, *args, **kwargs):
        result = QTabWidget.addTab(self, *args, **kwargs)
        self._update_message_visibility()
        return result

    def removeTab(self, *args, **kwargs):
        result = QTabWidget.removeTab(self, *args, **kwargs)
        self._update_message_visibility()
        return result

    def show_message(self, msg):
        self.status.setText(msg)


class LimitedDict(dict):
    """
    >>> d = LimitedDict(max_size=2)
    >>> d['a'] = 1
    >>> d['b'] = 2
    >>> d['c'] = 3
    >>> 'b' in d and 'c' in d and 'a' not in d
    True
    >>> d['b'] = 4
    >>> d['b'] = 4
    >>> len(d)
    2
    >>> d['b']
    4

    """
    def __init__(self, *args, **kwargs):
        self.max_size = kwargs.pop('max_size', 100)
        dict.__init__(self, *args, **kwargs)
        self.keylist = deque()

    def __setitem__(self, key, value):
        if key not in self:
            self.keylist.append(key)
            if len(self.keylist) > self.max_size:
                k = self.keylist.popleft()
                del self[k]
        dict.__setitem__(self, key, value)

grouping_strength = {1: TERTIARY, 2: TERTIARY, 3: SECONDARY}

def article_grouping_key(article):
    title = article.title
    strength = grouping_strength.get(len(title), PRIMARY)
    return collation_key(title, strength).getByteArray()


def fix_float_title(widget, title_key, floating):
    title = _(title_key)
    if floating:
        title = title.replace('&', '')
    widget.setWindowTitle(title)


class DictView(QMainWindow):

    def __init__(self):
        QMainWindow.__init__(self)

        self._pos = self.pos()
        self._size = self.size()

        self.setUnifiedTitleAndToolBarOnMac(False)
        self.setWindowIcon(icons['aarddict'])

        self.dictionaries = Library()
        self.update_title()

        self.word_completion = QListWidget()

        self.word_input = LineEditWithClear(self.word_completion)
        self.word_input.setClearShortcut(_('Ctrl+N'))
        self.word_input.textEdited.connect(self.word_input_text_edited)
        self.word_input.cleared.connect(functools.partial(self.schedule,
                                                          self.update_word_completion, 0))

        self.word_input.returnPressed.connect(self.focus_current_tab)

        box = QVBoxLayout()
        box.setSpacing(2)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.word_input)
        box.addWidget(self.word_completion)
        lookup_pane = QWidget()
        lookup_pane.setLayout(box)

        self.history_view = QListWidget()

        self.history_view.currentItemChanged.connect(self.history_selection_changed)
        self.history_view.currentItemChanged.connect(self.update_history_actions)
        self.word_completion.currentItemChanged.connect(self.word_selection_changed)

        self.tabs = TabWidget()
        self.tabs.setDocumentMode(True)

        self.setDockNestingEnabled(True)

        self.dock_lookup_pane = QDockWidget(_('&Lookup'), self)
        self.dock_lookup_pane.setObjectName('dock_lookup_pane')
        self.dock_lookup_pane.setWidget(lookup_pane)
        #On Windows and Mac OS X title bar shows & when floating
        self.dock_lookup_pane.topLevelChanged[bool].connect(
            functools.partial(fix_float_title, self.dock_lookup_pane, '&Lookup'))

        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_lookup_pane)

        self.dock_history = QDockWidget(_('&History'), self)
        self.dock_history.setObjectName('dock_history')
        self.dock_history.setWidget(self.history_view)
        self.dock_history.topLevelChanged[bool].connect(
            functools.partial(fix_float_title, self.dock_history, '&History'))
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_history)

        self.tabifyDockWidget(self.dock_lookup_pane, self.dock_history)
        self.dock_lookup_pane.raise_()

        self.toolbar = toolbar = QToolBar(_('&Toolbar'), self)
        toolbar.setObjectName('toolbar')
        self.addToolBar(toolbar)

        menubar = self.menuBar()
        self.menubar_should_be_visible = menubar.isVisible()

        def a(name, icon_name, tooltip, shortcuts, func, checkable=False):
            if icon_name:
                action = QAction(icons[icon_name], name, self)
            else:
                action = QAction(name, self)
            if checkable:
                action.setCheckable(True)
                action.triggered[bool].connect(func)
            else:
                action.triggered.connect(func)
            if shortcuts:
                if isinstance(shortcuts, (list, tuple)):
                    action.setShortcuts(shortcuts)
                else:
                    action.setShortcut(shortcuts)
            action.setToolTip(tooltip)
            self.addAction(action)
            return action

        def m(name, *args):
            mn = QMenu(name, self)
            for item in args:
                if item is None:
                    mn.addSeparator()
                elif isinstance(item, QMenu):
                    mn.addMenu(item)
                else:
                    mn.addAction(item)
            return mn

        def t(toolbar, *args):
            for item in args:
                if item is None:
                    toolbar.addSeparator()
                else:
                    toolbar.addAction(item)


        action_add_dicts = a(_('&Add Dictionaries...'), 'add-file',
                             _('Add dictionaries'),
                             _('Ctrl+O'), self.add_dicts)

        action_add_dict_dir = a(_('Add &Directory...'), 'add-folder',
                                _('Add dictionary directory'),
                                _('Ctrl+Shift+O'), self.add_dict_dir)

        action_remove_dict_source = a(_('&Remove...'), 'list-remove',
                                      _('Remove dictionary or dictionary directory'),
                                      _('Ctrl+R'), self.remove_dict_source)

        action_verify = a(_('&Verify...'), 'system-run',
                          _('Verify volume data integrity'),
                          _('Ctrl+E'), self.verify)
        self.action_verify = action_verify

        action_info = a(_('&Info...'), 'document-properties',
                        _('Information about open dictionaries'),
                        _('Ctrl+I'), self.show_info)

        action_quit = a(_('&Quit'), 'application-exit',
                        _('Exit application'),
                        _('Ctrl+Q'), self.close)

        def lookup():
            fw = QApplication.focusWidget()
            if hasattr(fw, 'selectedText'):
                text = fw.selectedText()
                if text:
                    self.set_word_input(text)
        ctrl_ret, ctrl_enter = _('Ctrl+Return'), _('Ctrl+Enter')
        action_lookup = a(_('&Lookup'), 'system-search',
                          _('Lookup the selected text'),
                          [ctrl_enter, ctrl_ret] if not is_mac_os()
                          else [ctrl_ret, ctrl_enter], lookup)
        self.action_lookup = action_lookup


        def cut():
            fw = QApplication.focusWidget()
            if isinstance(fw, QLineEdit):
                fw.cut()
        action_cut = a(_('Cu&t'), 'edit-cut', _('Cut the selection'),
                       QKeySequence.Cut, cut)

        def copy():
            fw = QApplication.focusWidget()
            if isinstance(fw, QLineEdit):
                fw.copy()
            elif isinstance(fw, QWebView):
                fw.page().triggerAction(QWebPage.Copy)
        action_copy = a(_('&Copy'), 'edit-copy', _('Copy the selection'),
                        [QKeySequence.Copy, _('Ctrl+Insert')], copy)
        self.action_copy = action_copy

        def paste():
            fw = QApplication.focusWidget()
            if isinstance(fw, QLineEdit):
                fw.paste()
        action_paste = a(_('&Paste'), 'edit-paste',
                         _('Paste the clipboard'),
                         [QKeySequence.Paste, _('Shift+Insert')], paste)

        def delete():
            fw = QApplication.focusWidget()
            if isinstance(fw, QLineEdit):
                fw.del_()
        action_delete = a(_('&Delete'), 'edit-delete',
                          _('Delete the selected text'),
                          QKeySequence.Delete, delete)

        def select_all():
            fw = QApplication.focusWidget()
            if isinstance(fw, QLineEdit):
                fw.selectAll()
            elif isinstance(fw, QWebView):
                fw.page().triggerAction(QWebPage.SelectAll)
        action_select_all = a(_('&Select All'), 'edit-select-all',
                              _('Select the entire text'),
                              QKeySequence.SelectAll, select_all)
        self.action_select_all = action_select_all

        action_lookup_box = a(_('&Lookup Box'),
                              None,
                              _('Move focus to word input and select its content'),
                              [_('Ctrl+L'), _('F2')],
                              self.go_to_lookup_box)

        action_history_back = a(_('&Back'),
                                'go-previous',
                                _('Go back to previous word in history'),
                                [QKeySequence.Back, _('Ctrl+[')],
                                self.history_back)
        self.action_history_back = action_history_back

        action_history_fwd = a(_('&Forward'), 'go-next',
                               _('Go forward to next word in history'),
                               [QKeySequence.Forward, _('Ctrl+]'), _('Shift+Esc')],
                               self.history_fwd)
        self.action_history_fwd = action_history_fwd

        action_next_article = a(_('&Next Article'),
                                'go-next-page',
                                _('Show next article'),
                                _('Ctrl+K'),
                                self.show_next_article)
        self.action_next_article = action_next_article

        action_prev_article = a(_('&Previous Article'), 'go-previous-page',
                                _('Show previous article'), _('Ctrl+J'),
                                self.show_prev_article)
        self.action_prev_article = action_prev_article

        #If 'Ctrl+.' and 'Ctrl+,' are set as shotcuts on next/previous article actions
        #they result in '.' and ',' characters entered if focus is
        #in an input field and corresponding action is disabled.
        #Make them shortcuts that are never disabled instead.
        QShortcut(QKeySequence(_('Ctrl+.')), self).activated.connect(self.show_next_article)
        QShortcut(QKeySequence(_('Ctrl+,')), self).activated.connect(self.show_prev_article)

        def go_to_find_pane():
            find_toolbar.show()
            find_toolbar.find_input.setFocus()
            find_toolbar.find_input.selectAll()
        action_article_find = a(_('&Find...'), 'edit-find',
                                _('Find text in article'),
                                [QKeySequence.Find, _('/')],
                                go_to_find_pane)

        action_save_article = a( _('&Save...'), 'document-save',
                                 _('Save article text to file'),
                                 _('Ctrl+S'), self.save_article)
        self.action_save_article = action_save_article

        action_online_article = a(_('&View Online'), 'emblem-web',
                                  _('Open online version of this '
                                    'article in a web browser'),
                                  _('Ctrl+T'), self.show_article_online)
        self.action_online_article = action_online_article

        action_article_appearance = a(_('&Appearance...'), 'emblem-art2',
                                      _('Customize article appearance'),
                                      _('Ctrl+U'), self.article_appearance)

        action_increase_text = a(_('&Increase'), 'zoom-in',
                                 _('Increase size of article text'),
                                 [QKeySequence.ZoomIn, _("Ctrl+="), _('F7')],
                                 self.increase_text_size)

        action_decrease_text = a(_('&Decrease'), 'zoom-out',
                                 _('Decrease size of article text'),
                                 [QKeySequence.ZoomOut, _('F8')],
                                 self.decrease_text_size)

        action_reset_text = a(_('&Reset'), 'zoom-original',
                              _('Reset size of article text to default'),
                              _('Ctrl+0'), self.reset_text_size)
        
        mac_os_full_screen_shortcut = _('Ctrl+Shift+F')
        full_screen_shortcuts = (mac_os_full_screen_shortcut if is_mac_os() 
                                 else [_('F11'), mac_os_full_screen_shortcut])
        action_full_screen = a(_('&Full Screen'), 'view-fullscreen',
                               _('Toggle full screen mode'),
                               full_screen_shortcuts, 
                               self.toggle_full_screen, checkable=True)
        self.action_full_screen = action_full_screen

        action_about = a(_('&About...'), 'help-about',
                         _('Information about Aard Dictionary'),
                         None, self.about)
        action_about.setMenuRole(QAction.AboutRole)

        menubar.addMenu(m(_('&Dictionary'),
                          action_add_dicts,
                          action_add_dict_dir,
                          action_remove_dict_source,
                          None,
                          action_verify,
                          action_info,
                          None,
                          action_quit))

        menubar.addMenu(m(_('&Edit'),
                          action_lookup,
                          None,
                          action_cut,
                          action_paste,
                          action_delete,
                          None,
                          action_select_all))

        menubar.addMenu(m(_('&Navigate'),
                          action_lookup_box,
                          None,
                          action_history_back,
                          action_history_fwd,
                          None,
                          action_next_article,
                          action_prev_article))

        menubar.addMenu(m(_('&Article'),
                          action_article_find,
                          action_save_article,
                          action_online_article,
                          action_article_appearance))

        menubar.addMenu(m(_('&View'),
                          self.dock_lookup_pane.toggleViewAction(),
                          self.dock_history.toggleViewAction(),
                          toolbar.toggleViewAction(),
                          m(_('Text &Size'),
                            action_increase_text,
                            action_decrease_text,
                            action_reset_text),
                          action_full_screen))

        menubar.addMenu(m(_('H&elp'),
                          action_about))

        t(toolbar,
          action_history_back,
          action_history_fwd,
          action_article_find,
          action_online_article,
          None,
          action_increase_text,
          action_decrease_text,
          action_reset_text,
          action_full_screen,
          None,
          action_add_dicts,
          action_add_dict_dir,
          action_info,
          None,
          action_quit)

        def update_edit_actions():
            fw = QApplication.focusWidget()
            lineedit = isinstance(fw, QLineEdit)
            webview = isinstance(fw, QWebView)
            selected = (bool(fw.selectedText())
                        if (lineedit or webview) else False)

            action_lookup.setEnabled(selected)
            action_cut.setEnabled(selected and lineedit)
            action_copy.setEnabled(selected)
            action_paste.setEnabled(lineedit and QApplication.clipboard().mimeData().hasText())
            action_delete.setEnabled(lineedit)
            action_select_all.setEnabled(lineedit or webview)

        def focus_changed(old, now):
            #On Mac OS X context menu grabs focus,
            #don't want to update actions for that
            if isinstance(now, QMenu):
                return
            if isinstance(now, QWebView):
                now.page().selectionChanged.connect(update_edit_actions)
            elif isinstance(now, QLineEdit):
                now.selectionChanged.connect(update_edit_actions)
            if isinstance(old, QWebView):
                old.page().selectionChanged.disconnect(update_edit_actions)
            elif isinstance(old, QLineEdit):
                old.selectionChanged.disconnect(update_edit_actions)
            update_edit_actions()

        QApplication.instance().focusChanged.connect(focus_changed)


        find_toolbar = FindWidget(self.tabs)
        find_toolbar.hide()
        self.find_toolbar = find_toolbar

        def esc():
            if find_toolbar.isVisible():
                if find_toolbar.find_input.hasFocus():
                    self.focus_current_tab()
                find_toolbar.hide()
            else:
                self.history_back()

        QShortcut(QKeySequence(_('Esc')), self).activated.connect(esc)

        central_widget_box = QVBoxLayout()
        central_widget_box.setSpacing(2)
        central_widget_box.setContentsMargins(0, 0, 0, 0)
        central_widget_box.addWidget(self.tabs)
        central_widget_box.addWidget(find_toolbar)
        central_widget = QWidget()
        central_widget.setLayout(central_widget_box)
        self.setCentralWidget(central_widget)

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.scheduled_func = None

        self.tabs.currentChanged.connect(self.article_tab_switched)

        self.current_lookup_thread = None

        self.sources = []
        self.zoom_factor = 1.0
        self.last_file_parent = u''
        self.last_dir_parent = u''
        self.last_save = u''

        self.update_current_article_actions(-1)
        self.scroll_values = LimitedDict()
        self.state_before_full_screen = None

    @property
    def preferred_dicts(self):
        c = self.history_view.currentItem()
        if c is not None:
            return c.preferred_dicts
        else:
            return dict([(vol.uuid.hex, i) for i, vol in
                         enumerate(reversed(self.dictionaries))])

    def add_debug_menu(self):
        from aarddict import debug
        mn_debug = self.menuBar().addMenu('Debug')
        mn_debug.addAction(QAction('Cache Stats', self,
                                   triggered=debug.dump_cache_stats))
        mn_debug.addAction(QAction('Instances Diff', self,
                                   triggered=debug.dump_type_count_diff))
        mn_debug.addAction(QAction('Set Instances Diff Checkpoint', self,
                                   triggered=debug.set_type_count_checkpoint))
        mn_debug.addAction(QAction('Instances Checkpoint Diff', self,
                                   triggered=debug.dump_type_count_checkpoint_diff))
        mn_debug.addAction(QAction('Run GC', self, triggered=debug.rungc))

    def add_dicts(self):
        self.open_dicts(self.select_files())

    def add_dict_dir(self):
        self.open_dicts(self.select_dir())

    def open_dicts(self, sources):
        self.sources = state.write_sources(self.sources + sources)
        dict_open_thread = DictOpenThread(sources, self.dictionaries, self)

        progress = QProgressDialog(self)
        progress.setLabelText(_('Opening dictionaries...'))
        progress.setCancelButtonText(_('Stop'))
        progress.setMinimum(0)
        progress.setMinimumDuration(800)

        errors = []

        def show_loading_dicts_dialog(num):
            progress.setMaximum(num)
            progress.setValue(0)

        dict_open_thread.dict_open_started.connect(show_loading_dicts_dialog)

        def dict_opened(d):
            progress.setValue(progress.value() + 1)
            log.debug('Opened %r' % d.file_name)

        def dict_failed(source, error):
            errors.append((source, error))
            progress.setValue(progress.value() + 1)
            log.error('Failed to open %s: %s', source, error)

        def canceled():
            dict_open_thread.stop()

        def finished():
            dict_open_thread.setParent(None)
            self.update_title()
            self.update_preferred_dicts()
            self.schedule(self.update_word_completion, 200)
            if errors:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle(_('Open Failed'))
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setInformativeText(_('Failed to open some dictionaries'))
                msg_box.setDetailedText('\n'.join('%s: %s' % error for error in errors))
                msg_box.setStandardButtons(QMessageBox.Ok)
                msg_box.open()

        progress.canceled.connect(canceled)
        dict_open_thread.dict_open_succeded.connect(dict_opened, Qt.QueuedConnection)
        dict_open_thread.dict_open_failed.connect(dict_failed, Qt.QueuedConnection)
        dict_open_thread.finished.connect(finished, Qt.QueuedConnection)
        dict_open_thread.start()

    def select_files(self):
        file_names = QFileDialog.getOpenFileNames(self, _('Add Dictionary'),
                                                  self.last_file_parent,
                                                  _('Aard Dictionary Files')+' (*.aar)')
        file_names = [unicode(name) for name in file_names]
        if file_names:
            self.last_file_parent = os.path.dirname(file_names[-1])
        return file_names

    def select_dir(self):
        name = QFileDialog.getExistingDirectory (self, _('Add Dictionary Directory'),
                                                      self.last_dir_parent,
                                                      QFileDialog.ShowDirsOnly)
        dirname = unicode(name)
        if dirname:
            self.last_dir_parent = os.path.dirname(dirname)
            return [dirname]
        else:
            return []

    def remove_dict_source(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(_('Remove Dictionaries'))
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

        btn_select_all = QPushButton(_('Select &All'))
        button_box.addButton(btn_select_all, QDialogButtonBox.ActionRole)
        btn_select_all.clicked.connect(item_list.selectAll)

        btn_remove = QPushButton(icons['list-remove'], _('&Remove'))

        def remove():
            rows = [index.row() for index in item_list.selectedIndexes()]
            for row in reversed(sorted(rows)):
                item_list.takeItem(row)
            if rows:
                remaining = [unicode(item_list.item(i).text())
                             for i in range(item_list.count())]
                self.cleanup_sources(remaining)

        btn_remove.clicked.connect(remove)

        button_box.addButton(btn_remove, QDialogButtonBox.ApplyRole)
        button_box.setStandardButtons(QDialogButtonBox.Close)

        content.addWidget(button_box)

        button_box.rejected.connect(dialog.reject)

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

        self.sources = state.write_sources(remaining)

        if to_be_removed:
            self.update_title()
            self.schedule(self.update_word_completion, 0)

    def article_tab_switched(self, current_tab_index):
        if current_tab_index > -1:
            web_view = self.tabs.widget(current_tab_index)
            dict_uuid = self.dictionaries.volume(web_view.entry.volume_id).uuid
            self.update_preferred_dicts(dict_uuid=dict_uuid)
            if web_view.article is None and not web_view.loading:
                self.load_article(web_view)
        self.update_current_article_actions(current_tab_index)

    def update_current_article_actions(self, current_tab_index):
        count = self.tabs.count()
        self.action_next_article.setEnabled(-1 < current_tab_index < count - 1)
        self.action_prev_article.setEnabled(current_tab_index > 0)
        self.action_online_article.setEnabled(self.get_current_article_url() is not None)
        self.action_save_article.setEnabled(count > 0)

    def update_preferred_dicts(self, dict_uuid=None):
        if dict_uuid:
            self.preferred_dicts[dict_uuid.hex] = time.time()
        self.dictionaries.sort(key=lambda d: -self.preferred_dicts.get(d.uuid.hex, 0))

    def schedule(self, func, delay=500):
        if self.scheduled_func:
            self.timer.timeout.disconnect(self.scheduled_func)
        self.timer.timeout.connect(func)
        self.scheduled_func = func
        self.timer.start(delay)

    def word_input_text_edited(self, _word=None):
        self.schedule(self.update_word_completion)

    def update_word_completion(self):
        word = self.word_input.text()
        if not self.history_view.hasFocus():
            if self.word_input.isVisible():
                self.word_input.setFocus()
        self.word_completion.clear()
        self.word_completion.addItem(_('Loading...'))
        self.tabs.show_message(_('Looking up <strong>%s</strong>') % unicode(word))
        if self.current_lookup_thread:
            self.current_lookup_thread.stop()
            self.current_lookup_thread = None

        word_lookup_thread = WordLookupThread(self.dictionaries, word, self)
        word_lookup_thread.lookup_failed.connect(self.word_lookup_failed,
                                                 Qt.QueuedConnection)
        word_lookup_thread.done.connect(self.word_lookup_finished,
                                        Qt.QueuedConnection)
        word_lookup_thread.finished.connect(
            functools.partial(word_lookup_thread.setParent, None),
            Qt.QueuedConnection)
        self.current_lookup_thread = word_lookup_thread
        word_lookup_thread.start(QThread.LowestPriority)

    def word_lookup_failed(self, word, exception_txt):
        formatted_error = (_('Error while looking up %(word)s:\n'
                             '%(exception)s') %
                           dict(word=word, exception=exception_txt))
        self.show_dict_error(_('Word Lookup Failed'), formatted_error)

    def word_lookup_finished(self, word, entries):
        log.debug('Lookup for %r finished, got %d article(s)', word, len(entries))
        self.word_completion.clear()
        items = dict()
        for entry in entries:
            article_key =  article_grouping_key(entry)
            if article_key in items:
                item = items[article_key]
                article_group = item.data(Qt.UserRole).toPyObject()
                article_group.append(entry)
                item.setData(Qt.UserRole, QVariant(article_group))
            else:
                item = QListWidgetItem()
                item.setText(entry.title)
                item.setData(Qt.UserRole, QVariant([entry]))
                items[article_key] = item
            self.word_completion.addItem(item)

        count = range(self.word_completion.count())
        if count:
            item = self.word_completion.item(0)
            self.word_completion.setCurrentItem(item)
            self.word_completion.scrollToItem(item)
            self.tabs.show_message('')
        else:
            self.tabs.show_message(_('Nothing found'))
            #add to history if nothing found so that back button works
            self.add_to_history(unicode(word))
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

    def word_selection_changed(self, selected, _deselected):
        func = functools.partial(self.update_shown_article, selected)
        self.schedule(func, 200)

    def history_selection_changed(self, selected, _deselected):
        title = unicode(selected.text()) if selected else u''
        def func():
            self.update_preferred_dicts()
            self.set_word_input(title)
        self.schedule(func, 200)

    def update_history_actions(self, _selected, _deselected):
        current_row = self.history_view.currentRow()
        self.action_history_fwd.setEnabled(current_row > 0)
        self.action_history_back.setEnabled(-1 < current_row <
                                             self.history_view.count() - 1)

    def update_shown_article(self, selected):
        self.clear_current_articles()
        if selected:
            self.add_to_history(unicode(selected.text()))
            entries = selected.data(Qt.UserRole).toPyObject()
            self.tabs.blockSignals(True)
            view_to_load = None
            for i, entry in enumerate(self.sort_preferred(entries)):
                view = WebView(entry)
                view.actions = [self.action_lookup,
                                self.action_copy,
                                self.action_select_all]
                view.setPage(WebPage(view))
                volume = self.dictionaries.volume(entry.volume_id)
                view.page().currentFrame().setHtml(_('Loading...'), QUrl(''))
                view.setZoomFactor(self.zoom_factor)

                dict_title = format_title(volume)
                if i < 9:
                    tab_label = ('&%d ' % (i+1))+dict_title
                else:
                    tab_label = dict_title
                self.tabs.addTab(view, tab_label)
                self.tabs.setTabToolTip(i, entry.title)
                self.update_current_article_actions(self.tabs.currentIndex())
                view.linkClicked.connect(self.link_clicked)
            self.tabs.blockSignals(False)
            view_to_load = self.tabs.widget(0)

            #don't want to steal focus from word input or history view
            #but if they are not visible, e.g. in fullscreen, take it
            if not ((self.history_view.isVisible() and
                     self.history_view.hasFocus()) or
                    (self.word_input.isVisible() and
                     self.word_input.hasFocus())):
                view_to_load.setFocus()
            self.load_article(view_to_load)

    def load_article(self, view):
        view.article_loaded = True
        load_thread = ArticleLoadThread(self.dictionaries, view, self)
        load_thread.article_loaded.connect(self.article_loaded,
                                           Qt.QueuedConnection)
        load_thread.article_load_failed.connect(self.article_load_failed,
                                                Qt.QueuedConnection)
        load_thread.start(QThread.LowestPriority)

    def article_load_failed(self, view, exception_txt):
        entry = view.entry
        vol = self.dictionaries.volume(entry.volume_id)
        view.page().currentFrame().setHtml(_('Failed to load article %s')
                                           % view.entry.title)
        formatted_error = (_('Error reading article %(title)s from '
                             '%(dict_title)s (file %(dict_file)s):\n'
                             '%(exception)s') %
                           dict(title=entry.title,
                                dict_title=format_title(vol),
                                dict_file=vol.file_name,
                                exception=exception_txt))
        self.show_dict_error(_('Article Load Failed'), formatted_error)


    def show_dict_error(self, title, error_detail):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setInformativeText(_('There was an error while accessing dictionaries. '
                                     'Dictionary files may be corrupted. '
                                     'Would you like to verify now?'))
        msg_box.setDetailedText(error_detail)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        result = msg_box.exec_()
        if result == QMessageBox.Yes:
            self.verify()

    def clear_current_articles(self):
        self.tabs.blockSignals(True)
        for i in reversed(range(self.tabs.count())):
            w = self.tabs.widget(i)
            f = w.page().mainFrame()
            scrollx = f.scrollBarValue(Qt.Horizontal)
            scrolly = f.scrollBarValue(Qt.Vertical)
            if w.article is not None:
                self.scroll_values[w.entry] = (scrollx, scrolly)
            self.tabs.removeTab(i)
            w.deleteLater()
        self.tabs.blockSignals(False)
        self.update_current_article_actions(self.tabs.currentIndex())

    def article_loaded(self, view):
        article = view.article
        log.debug('Loaded article for %r (original entry %r)',
                  article.entry, view.entry)

        def loadFinished(ok):
            log.debug('article loadFinished for entry %r', article.entry)
            if ok:
                if view.entry in self.scroll_values:
                    scrollx, scrolly = self.scroll_values[view.entry]
                    f = view.page().mainFrame()
                    f.setScrollBarValue(Qt.Horizontal, scrollx)
                    f.setScrollBarValue(Qt.Vertical, scrolly)
                if article.entry.section:
                    self.go_to_section(view, article.entry.section)

        view.loadFinished[bool].connect(loadFinished, Qt.QueuedConnection)
        view.page().currentFrame().setHtml(article.text, QUrl(view.title))
        view.setZoomFactor(self.zoom_factor)


    def show_next_article(self):
        current = self.tabs.currentIndex()
        count = self.tabs.count()
        new_current = current + 1
        if new_current < count:
            self.tabs.setCurrentIndex(new_current)

    def show_prev_article(self):
        current = self.tabs.currentIndex()
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
            if current_tab.entry is None:
                return None
            volume_id = current_tab.entry.volume_id
            volume = self.dictionaries.volume(volume_id)
            if not volume:
                return None
            article_title = current_tab.entry.title
            article_url = volume.article_url
            if article_url:
                return article_url.replace(u'$1', article_title)

    def sort_preferred(self, entries):
        def key(x):
            vol = self.dictionaries.volume(x.volume_id)
            return -self.preferred_dicts.get(vol.uuid.hex, 0)
        return sorted(entries, key=key)

    def go_to_section(self, view, section):
        log.debug('Go to section %r', section)
        mainFrame = view.page().mainFrame()
        mainFrame.addToJavaScriptWindowObject('matcher', matcher)
        js_template = 'scrollToMatch("%s", %%s)' % section
        for strength in (TERTIARY, SECONDARY, PRIMARY):
            js = js_template % strength
            result = mainFrame.evaluateJavaScript(js)
            if result.toBool():
                break

    def link_clicked(self, url):
        log.debug('Link clicked: %r', url)
        scheme = unicode(url.scheme())
        path = unicode(url.path())
        fragment = unicode(url.fragment())
        log.debug('scheme: %r, path: %r, frag: %r', scheme, path, fragment)
        if scheme in (u'http', u'https', u'ftp', u'sftp'):
            webbrowser.open(unicode(url.toString()))
        else:
            title = '#'.join((path, fragment)) if fragment else path
            if '_' in title:
                log.debug('Found underscore character in title %r, '
                          'replacing with space', title)
                title = title.replace(u'_', u' ')
            if scheme:
                current_tab = self.tabs.currentWidget()
                volume_id = current_tab.entry.volume_id
                vol = self.dictionaries.volume(volume_id)
                article_url = vol.interwiki_map.get(scheme)
                if article_url:
                    dictionary_id = self.dictionaries.dict_by_article_url(article_url)
                    if dictionary_id:
                        log.debug('Found dictionary %r by namespace %r',
                                  dictionary_id, scheme)
                        self.update_preferred_dicts(dictionary_id)
                    else:
                        log.debug('No dictionary with article url %r',
                                  article_url)
                else:
                    log.debug('Scheme %r does not appear to be a valid namespace, '
                              'probably part of title', scheme)
                    title = ':'.join((scheme, title))

            if not path and fragment:
                current_tab = self.tabs.currentWidget()
                if current_tab:
                    self.go_to_section(current_tab, fragment)
                else:
                    log.error('Link %r clicked, but no article view?', title)
            else:
                self.set_word_input(title)

    def set_word_input(self, text):
        self.word_input.setText(text)
        #don't call directly to make sure previous update is unscheduled
        self.schedule(self.update_word_completion, 0)

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

    def add_to_history(self, title, preferred_dicts=None):
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
            if preferred_dicts is None:
                item.preferred_dicts = dict(self.preferred_dicts)
            else:
                item.preferred_dicts = preferred_dicts
            self.history_view.insertItem(0, item)
            self.history_view.setCurrentItem(item)
            while self.history_view.count() > max_history:
                self.history_view.takeItem(self.history_view.count() - 1)
            self.history_view.blockSignals(False)
            self.update_history_actions(None, None)

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
        if self.windowState() == Qt.WindowFullScreen:
            self.action_full_screen.trigger()
        if self.dock_lookup_pane.isHidden():
            self.dock_lookup_pane.show()
            QTimer.singleShot(20, self.go_to_lookup_box)
        else:
            self.dock_lookup_pane.raise_()
            self.dock_lookup_pane.activateWindow()
            self.word_input.setFocus()
            self.word_input.selectAll()

    def focus_current_tab(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            self.raise_()
            self.activateWindow()
            current_tab.setFocus()

    def verify(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(_('Verify'))
        content = QVBoxLayout()

        item_list = QTableWidget()
        item_list.setRowCount(len(self.dictionaries))
        item_list.setColumnCount(2)
        item_list.setHorizontalHeaderLabels([_('Status'), _('Volume')])
        item_list.setSelectionMode(QTableWidget.SingleSelection)
        item_list.setEditTriggers(QTableWidget.NoEditTriggers)
        item_list.verticalHeader().setVisible(False)
        item_list.setSelectionModel(
            SingleRowItemSelectionModel(item_list.model()))

        for i, volume in enumerate(self.dictionaries):
            text = format_title(volume)
            item = QTableWidgetItem(text)
            item.setData(Qt.UserRole, QVariant(volume.volume_id))
            item_list.setItem(i, 1, item)
            item = QTableWidgetItem(_('Unverified'))
            item.setData(Qt.DecorationRole, icons['question'])
            item_list.setItem(i, 0, item)

        item_list.horizontalHeader().setStretchLastSection(True)
        item_list.resizeColumnToContents(0)

        content.addWidget(item_list)

        dialog.setLayout(content)
        button_box = QDialogButtonBox()

        btn_verify = QPushButton(icons['system-run'], _('&Verify'))

        def verify():
            current_row = item_list.currentRow()
            item = item_list.item(current_row, 1)
            volume_id = str(item.data(Qt.UserRole).toString())
            volume = self.dictionaries.volume(volume_id)
            verify_thread = VolumeVerifyThread(volume)
            progress = QProgressDialog(dialog)
            progress.setWindowTitle(_('Verifying...'))
            progress.setLabelText(format_title(volume))
            progress.setValue(0)
            progress.forceShow()

            def update_progress(num):
                if not verify_thread.stop_requested:
                    progress.setValue(100*num)

            def verified(isvalid):
                status_item = item_list.item(current_row, 0)
                if isvalid:
                    status_item.setText(_('Ok'))
                    status_item.setData(Qt.DecorationRole, icons['emblem-ok'])
                else:
                    status_item.setText(_('Corrupt'))
                    status_item.setData(Qt.DecorationRole, icons['emblem-unreadable'])

            def finished():
                verify_thread.volume = None
                verify_thread.setParent(None)

            progress.canceled.connect(verify_thread.stop, Qt.DirectConnection)
            verify_thread.progress.connect(update_progress, Qt.QueuedConnection)
            verify_thread.verified.connect(verified, Qt.QueuedConnection)
            verify_thread.finished.connect(finished, Qt.QueuedConnection)
            verify_thread.start(QThread.LowestPriority)

        btn_verify.clicked.connect(verify)

        button_box.addButton(btn_verify, QDialogButtonBox.ApplyRole)
        button_box.setStandardButtons(QDialogButtonBox.Close)

        content.addWidget(button_box)

        button_box.rejected.connect(dialog.reject)

        if item_list.rowCount():
            item_list.setCurrentCell(0, 0)

        dialog.exec_()

    def show_info(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(_('Dictionary Info'))
        content = QVBoxLayout()

        item_list = QListWidget()

        dictmap = defaultdict(list)

        for dictionary in self.dictionaries:
            dictmap[dictionary.uuid].append(dictionary)

        for uuid, dicts in dictmap.iteritems():
            text = format_title(dicts[0], with_vol_num=False)
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, QVariant(uuid))
            item_list.addItem(item)

        splitter = QSplitter()
        splitter.addWidget(item_list)
        detail_view = WebView()
        detail_view.setPage(WebPage(self))

        detail_view.linkClicked.connect(self.link_clicked)

        splitter.addWidget(detail_view)
        splitter.setSizes([100, 300])

        content.addWidget(splitter)

        dialog.setLayout(content)
        button_box = QDialogButtonBox()

        button_box.setStandardButtons(QDialogButtonBox.Close)

        content.addWidget(button_box)

        def current_changed(current, __):
            uuid = current.data(Qt.UserRole).toPyObject()
            volumes = dictmap[uuid]

            if volumes:
                volumes = sorted(volumes, key=lambda v: v.volume)
                d = volumes[0]

                volumes_str = '<br>'.join(('<strong>%s %s:</strong> <em>%s</em>' %
                                           (_('Volume'), v.volume, v.file_name))
                                          for v in volumes)

                params = defaultdict(unicode)

                try:
                    num_of_articles = locale.format('%u', d.article_count, True)
                    num_of_articles = num_of_articles.decode(locale.getpreferredencoding())
                except:
                    log.warn("Failed to format number of articles")
                    num_of_articles = unicode(d.article_count)

                params.update(dict(title=d.title, version=d.version,
                              lbl_total_volumes=_('Volumes:'),
                              total_volumes=d.total_volumes,
                              volumes=volumes_str,
                              lbl_num_of_articles=_('Number of articles:'),
                              num_of_articles=num_of_articles))

                if d.language_links:
                    params['language_links'] = ('<p><strong>%s</strong> <em>%s</em></p>'
                                                % (_('Language links:'),
                                                   ', '.join(d.language_links)))
                if d.description:
                    params['description'] = '<p>%s</p>' % linkify(d.description)
                if d.source:
                    params['source'] = '<h2>%s</h2>%s' % (_('Source'), linkify(d.source))
                if d.copyright:
                    params['copyright'] = '<h2>%s</h2>%s' % (_('Copyright Notice'), linkify(d.copyright))
                if d.license:
                    params['license'] = '<h2>%s</h2><pre>%s</pre>' % (_('License'), d.license)

                html = res.dict_detail(params)
            else:
                html = ''
            detail_view.setHtml(html)

        item_list.currentItemChanged.connect(current_changed)

        if item_list.count():
            item_list.setCurrentRow(0)

        button_box.rejected.connect(dialog.reject)

        dialog.setSizeGripEnabled(True)
        dialog.exec_()

    def about(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(_('About'))
        content = QVBoxLayout()

        detail_view = SizedWebView(QSize(400, 260))
        detail_view.setPage(WebPage(self))
        palette = detail_view.palette()
        palette.setBrush(QPalette.Base, Qt.transparent)
        detail_view.page().setPalette(palette)
        detail_view.setAttribute(Qt.WA_OpaquePaintEvent, False)
        detail_view.setHtml(res.about())

        detail_view.linkClicked.connect(self.link_clicked)

        content.addWidget(detail_view)

        dialog.setLayout(content)
        button_box = QDialogButtonBox()

        button_box.setStandardButtons(QDialogButtonBox.Close)

        content.addWidget(button_box)

        button_box.rejected.connect(dialog.reject)

        dialog.setSizeGripEnabled(True)
        dialog.exec_()

    def article_appearance(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(_('Article Appearance'))
        content = QVBoxLayout()

        preview_pane = SizedWebView(QSize(300, 300))
        preview_pane.setPage(WebPage(self))
        html = _("""<div id="globalWrapper">
This is an <a href="#">internal link</a>. <br>
This is an <a href="http://example.com">external link</a>. <br>
This is text with a footnote reference<a id="_r123" href="#">[1]</a>. <br>
<p>Click on any link to see active link color.</p>

<div>1. <a href="#_r123">&#8593;</a> This is a footnote.</div>
</div>
""")
        preview_pane.page().currentFrame().setHtml(res.style() + html)

        colors = res.colors

        color_pane = QGridLayout()
        color_pane.setColumnStretch(1, 2)

        def set_color(btn, color_name):
            c = QColorDialog.getColor(QColor(colors[color_name]))
            if c.isValid():
                pixmap = QPixmap(24, 16)
                pixmap.fill(c)
                btn.setIcon(QIcon(pixmap))
                colors[color_name] = str(c.name())
                if not cb_use_mediawiki_style.isChecked():
                    frame = preview_pane.page().currentFrame()
                    frame.setHtml(res.style() + html)

        pixmap = QPixmap(24, 16)
        pixmap.fill(QColor(colors['internal_link_fg']))
        btn_internal_link = QPushButton()
        btn_internal_link.setIcon(QIcon(pixmap))
        color_pane.addWidget(btn_internal_link, 0, 0)
        color_pane.addWidget(QLabel(_('Internal Link')), 0, 1)

        btn_internal_link.clicked.connect(
            functools.partial(set_color, btn_internal_link, 'internal_link_fg'))

        pixmap = QPixmap(24, 16)
        pixmap.fill(QColor(colors['external_link_fg']))
        btn_external_link = QPushButton()
        btn_external_link.setIcon(QIcon(pixmap))
        color_pane.addWidget(btn_external_link, 1, 0)
        color_pane.addWidget(QLabel(_('External Link')), 1, 1)

        btn_external_link.clicked.connect(
            functools.partial(set_color, btn_external_link, 'external_link_fg'))

        pixmap = QPixmap(24, 16)
        pixmap.fill(QColor(colors['footnote_fg']))
        btn_footnote = QPushButton()
        btn_footnote.setIcon(QIcon(pixmap))
        color_pane.addWidget(btn_footnote, 2, 0)
        color_pane.addWidget(QLabel(_('Footnote Link')), 2, 1)

        btn_footnote.clicked.connect(
            functools.partial(set_color, btn_footnote, 'footnote_fg'))

        pixmap = QPixmap(24, 16)
        pixmap.fill(QColor(colors['footnote_backref_fg']))
        btn_footnote_back = QPushButton()
        btn_footnote_back.setIcon(QIcon(pixmap))
        color_pane.addWidget(btn_footnote_back, 3, 0)
        color_pane.addWidget(QLabel(_('Footnote Back Link')), 3, 1)

        btn_footnote_back.clicked.connect(
            functools.partial(set_color, btn_footnote_back, 'footnote_backref_fg'))

        pixmap = QPixmap(24, 16)
        pixmap.fill(QColor(colors['active_link_bg']))
        btn_active_link = QPushButton()
        btn_active_link.setIcon(QIcon(pixmap))
        color_pane.addWidget(btn_active_link, 4, 0)
        color_pane.addWidget(QLabel(_('Active Link')), 4, 1)

        btn_active_link.clicked.connect(
            functools.partial(set_color, btn_active_link, 'active_link_bg'))

        btn_font = QPushButton(_('AaBb'))
        btn_font.setFont(res.font)
        def select_font():
            font, ok = QFontDialog.getFont(res.font, self)
            if ok:
                res.font = font
                btn_font.setFont(font)
                frame = preview_pane.page().currentFrame()
                frame.setHtml(res.style() + html)
        btn_font.clicked.connect(select_font)
        color_pane.addWidget(btn_font, 5, 0)
        color_pane.addWidget(QLabel(_('Article Text')), 5, 1)

        cb_use_mediawiki_style = QCheckBox(_('Use Wikipedia style'))
        color_pane.addWidget(cb_use_mediawiki_style, 6, 0, 1, 2)

        def use_mediawiki_style_changed(_):
            res.use_mediawiki_style = cb_use_mediawiki_style.isChecked()
            preview_pane.page().currentFrame().setHtml(res.style() + html)

        cb_use_mediawiki_style.stateChanged.connect(use_mediawiki_style_changed)
        cb_use_mediawiki_style.setChecked(res.use_mediawiki_style)
        color_pane.addWidget(preview_pane, 0, 2, 7, 1)
        content.addLayout(color_pane)
        button_box = QDialogButtonBox()
        button_box.setStandardButtons(QDialogButtonBox.Close)
        content.addWidget(button_box)

        def close():
            dialog.reject()
            appearance = dict(style=dict(use_mediawiki_style=res.use_mediawiki_style),
                              colors=res.colors,
                              fonts=dict(default=unicode(res.font.toString())))
            state.write_appearance(appearance)
            style = res.style()
            for i in range(self.tabs.count()):
                view = self.tabs.widget(i)
                frame = view.page().currentFrame()
                html = unicode(frame.toHtml())
                html = style_tag_re.sub(style, html, count=1)
                frame.setHtml(html)

        button_box.rejected.connect(close)
        dialog.setLayout(content)
        dialog.exec_()

    def resizeEvent(self, event):
        window_state = self.windowState()
        if window_state != Qt.WindowFullScreen:
            self._size = event.size()

    def moveEvent(self, event):
        window_state = self.windowState()
        if window_state != Qt.WindowFullScreen:
            self._pos = event.pos()

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            self.update_view_actions()
            window_state = self.windowState()
            if window_state == Qt.WindowFullScreen:
                self.action_full_screen.setChecked(True)
                self.state_before_full_screen = self.saveState()
                self.menubar_should_be_visible = self.menuBar().isVisible()
                self.dock_history.hide()
                self.dock_lookup_pane.hide()
                self.toolbar.hide()
                self.menuBar().hide()
                btn = QToolButton(self.tabs)
                btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
                btn.setDefaultAction(self.action_full_screen)
                btn.show()
                self.tabs.setCornerWidget(btn, Qt.TopRightCorner)

                if not self.find_toolbar.find_input.hasFocus():
                    self.focus_current_tab()
            else:
                self.tabs.setCornerWidget(None, Qt.TopRightCorner)
                self.action_full_screen.setChecked(False)
                self.menuBar().setVisible(self.menubar_should_be_visible)
                if self.state_before_full_screen:
                    self.restoreState(self.state_before_full_screen)

    def update_view_actions(self):
        window_state = self.windowState()
        enabled = window_state != Qt.WindowFullScreen
        self.dock_lookup_pane.toggleViewAction().setEnabled(enabled)
        self.dock_history.toggleViewAction().setEnabled(enabled)
        self.toolbar.toggleViewAction().setEnabled(enabled)

    def closeEvent(self, _event):
        self.clear_current_articles()
        self.write_state()
        for d in self.dictionaries:
            d.close()

    def update_title(self):
        dict_title = self.create_dict_title()
        title = u'%s - %s' % (_(aarddict.__appname__), dict_title)
        self.setWindowTitle(title)

    def create_dict_title(self):
        dcount = len(self.dictionaries.uuids())
        vcount = len(self.dictionaries)
        if vcount == 0:
            return _('No dictionaries')
        volumestr_template =  ngettext('%d volume', '%d volumes', vcount)
        volumestr = volumestr_template % vcount
        dictstr_template = ngettext('%d dictionary', '%d dictionaries', dcount)
        dictstr =  dictstr_template % dcount
        return u'%s (%s)' % (dictstr, volumestr)

    def save_article(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            article_title = current_tab.title
            dirname = os.path.dirname(self.last_save)
            propose_name = os.path.extsep.join((article_title, u'html'))
            file_name = QFileDialog.getSaveFileName(self, _('Save Article'),
                                                    os.path.join(dirname, propose_name),
                                                    _('HTML Documents (*.htm *.html)'))
            if file_name:
                file_name = unicode(file_name)
                self.last_save = file_name
                try:
                    with open(file_name, 'w') as f:
                        current_frame = current_tab.page().currentFrame()
                        html = unicode(current_frame.toHtml())
                        f.write(html.encode('utf8'))
                except Exception, e:
                    msg_box = QMessageBox(self)
                    msg_box.setWindowTitle(_('Failed to Save Article'))
                    msg_box.setIcon(QMessageBox.Critical)
                    msg_box.setInformativeText(_('There was an error when '
                                                 'writing article to file %s')
                                               % file_name)
                    msg_box.setDetailedText(unicode(e))
                    msg_box.setStandardButtons(QMessageBox.Ok)
                    msg_box.open()

    def write_state(self):
        appstate = {}
        history = []
        for i in reversed(range(self.history_view.count())):
            item = self.history_view.item(i)
            preferred_dicts = item.preferred_dicts
            history.append([unicode(item.text()), preferred_dicts])
        appstate['history'] = history
        pos = self._pos
        size = self._size
        appstate['geometry'] = [pos.x(), pos.y(), size.width(), size.height()]
        appstate['history_current'] = self.history_view.currentRow()
        appstate['last_file_parent'] = self.last_file_parent
        appstate['last_dir_parent'] = self.last_dir_parent
        appstate['last_save'] = self.last_save
        appstate['zoom_factor'] = self.zoom_factor

        scroll_values = []
        for entry, value in self.scroll_values.iteritems():
            scroll_values.append([entry.volume_id, entry.index, value[0], value[1]])

        appstate['scroll_values'] = scroll_values

        state.write_state(appstate)

        if self.windowState() == Qt.WindowFullScreen:
            if self.state_before_full_screen:
                state.write_layout(self.state_before_full_screen)
        else:
            layout = self.saveState()
            state.write_layout(layout)

    def read_state(self, load):
        appstate = state.read_state(load)

        x, y, w, h = appstate['geometry']
        self.move(QPoint(x, y))
        self.resize(QSize(w, h))

        layout = state.read_layout(load)
        if layout:
            self.restoreState(QByteArray(layout))

        history = appstate['history']
        for title, preferred_dicts in history:
            self.add_to_history(title, preferred_dicts)

        history_current = appstate['history_current']
        if history_current > -1 and self.history_view.count():
            self.history_view.blockSignals(True)
            self.history_view.setCurrentRow(history_current)
            self.history_view.blockSignals(False)
            word = unicode(self.history_view.currentItem().text())
            self.word_input.setText(word)
            self.update_history_actions(None, None)

        self.last_file_parent = appstate['last_file_parent']
        self.last_dir_parent = appstate['last_dir_parent']
        self.last_save = appstate['last_save']
        self.zoom_factor = appstate['zoom_factor']

        scrollvalues = appstate['scroll_values']
        for item in scrollvalues:
            volume_id, index, scrollx, scrolly = item
            self.scroll_values[Entry(volume_id, index)] = (scrollx, scrolly)

        appearance = state.read_appearance(load)
        res.use_mediawiki_style = appearance['style']['use_mediawiki_style']
        res.colors = appearance['colors']
        font = QFont()
        font.fromString(appearance['fonts']['default'])
        res.font = font


def is_mac_os():
    import platform
    mac_ver = platform.mac_ver()
    return mac_ver and mac_ver[0]


def main(args, debug=False, dev_extras=False):
    app = QApplication(sys.argv)

    qtranslator = QTranslator()
    qtranslator.load('qt_'+str(QLocale.system().name()), res.locale_dir)
    app.installTranslator(qtranslator)

    res.load()

    dv = DictView()
    if dev_extras:
        (QWebSettings.globalSettings()
         .setAttribute(QWebSettings.DeveloperExtrasEnabled, True))
    if debug:
        dv.add_debug_menu()
    try:
        dv.read_state(True)
    except:
        state.show_error(_('Failed to load saved application state'))
        dv.read_state(False)
    dv.show()
    dv.word_input.setFocus()
    preferred_enc = locale.getpreferredencoding()
    dv.open_dicts(state.read_sources()+[arg.decode(preferred_enc) for arg in args])
    sys.exit(app.exec_())
