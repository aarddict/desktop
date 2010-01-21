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
import tempfile

from ConfigParser import ConfigParser
from uuid import UUID
from itertools import groupby
from collections import defaultdict

from PyQt4.QtCore import (QObject, Qt, QThread, SIGNAL, QMutex,
                          QTimer, QUrl, QVariant, pyqtProperty, pyqtSlot,
                          QModelIndex, QSize, QByteArray, QPoint, QRect)

from PyQt4.QtGui import (QWidget, QIcon, QPixmap, QFileDialog,
                         QLineEdit, QHBoxLayout, QVBoxLayout, QAction,
                         QKeySequence, QToolButton,
                         QMainWindow, QListWidget, QListWidgetItem,
                         QTabWidget, QApplication, QStyle,
                         QGridLayout, QSplitter, QProgressDialog,
                         QMessageBox, QDialog, QDialogButtonBox, QPushButton,
                         QTableWidget, QTableWidgetItem, QItemSelectionModel,
                         QDockWidget, QToolBar, QFormLayout, QColor, QLabel,
                         QColorDialog, QCheckBox, QKeySequence, QPalette,
                         QMenu, QProgressBar)

from PyQt4.QtWebKit import QWebView, QWebPage, QWebSettings

import aar2html
import aarddict
from aarddict.dictionary import (Dictionary, format_title,
                                 DictionaryCollection,
                                 RedirectResolveError,
                                 collation_key,
                                 PRIMARY,
                                 SECONDARY,
                                 TERTIARY,
                                 QUATERNARY,
                                 Article,
                                 split_word,
                                 cmp_words,
                                 VerifyError)

from aarddict import package_dir

import gettext

connect = QObject.connect

log = logging.getLogger(__name__)

locale.setlocale(locale.LC_ALL, '')
locale_dir = os.path.join(package_dir, 'locale')
gettext_domain = aarddict.__name__ + '-qt'
gettext.bindtextdomain(gettext_domain, locale_dir)
gettext.textdomain(gettext_domain)
gettext.install(gettext_domain, locale_dir, unicode=True, names=['ngettext'])


def load_file(name, binary=False):
    with open(name, 'r'+ ('b' if binary else '')) as f:
        content = f.read()
        return content if binary else content.decode('utf8')

app_dir = os.path.expanduser('~/.aarddict')
sources_file = os.path.join(app_dir, 'sources')
history_file = os.path.join(app_dir, 'history')
history_current_file = os.path.join(app_dir, 'history_current')
layout_file = os.path.join(app_dir, 'layout')
geometry_file = os.path.join(app_dir, 'geometry')
appearance_file = os.path.join(app_dir, 'appearance.ini')
preferred_dicts_file = os.path.join(app_dir, 'preferred')
lastfiledir_file = os.path.join(app_dir, 'lastfiledir')
lastdirdir_file = os.path.join(app_dir, 'lastdirdir')
lastsave_file = os.path.join(app_dir, 'lastsave')
zoomfactor_file = os.path.join(app_dir, 'zoomfactor')

js = ('<script type="text/javascript">%s</script>' % 
      load_file(os.path.join(package_dir, 'aar.js')))

shared_style_str = load_file(os.path.join(package_dir, 'shared.css'))

aard_style_tmpl = string.Template(('<style type="text/css">%s</style>' %
                                   '\n'.join((shared_style_str, 
                                              load_file(os.path.join(package_dir, 
                                                                     'aar.css.tmpl'))))))


mediawiki_style = ('<style type="text/css">%s</style>' % 
                   '\n'.join((shared_style_str, 
                              load_file(os.path.join(package_dir, 'mediawiki_shared.css')),
                              load_file(os.path.join(package_dir, 'mediawiki_monobook.css')))))

style_tag_re = re.compile(u'<style type="text/css">(.+?)</style>', re.UNICODE | re.DOTALL)

appearance_conf = ConfigParser()

max_history = 50

iconset = 'Human-O2'
icondir = os.path.join(package_dir, 'icons/%s/' % iconset)
logodir = os.path.join(package_dir, 'icons/%s/' % 'hicolor')

dict_detail_tmpl= string.Template("""
<html>
<body>
<h1>$title $version</h1>
<div style="margin-left:20px;marging-right:20px;">
<p><strong>$lbl_total_volumes $total_volumes</strong></p>
$volumes
<p><strong>$lbl_num_of_articles</strong> <em>$num_of_articles</em></p>
$language_links
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
<table cellspacing='5'>
<tr style="vertical-align: middle;" >
  <td><img src="$logodir/64x64/apps/aarddict.png"></td>
  <td style="text-align: center; font-weight: bold;">
      <span style="font-size: large;">$appname</span><br>
      $version
  </td>
</tr>
</table>
<p>$copyright1<br>$copyright2</p>
<p><a href="$website">$website</a></p>
</div>
<div align="center">
<p style="font-size: small;">
$lic_notice
</p>
<p style="font-size: small;">
$logo_notice<br>
$icons_notice
</p>
</div>
""")

about_html = about_tmpl.substitute(dict(appname=_(aarddict.__appname__),
                                        version=aarddict.__version__,
                                        logodir=logodir,
                                        website='http://aarddict.org',
                                        copyright1=_('(C) 2006-2010 Igor Tkach'),
                                        copyright2=_('(C) 2008 Jeremy Mortis'),
                                        lic_notice=_('Distributed under terms and conditions '
                                                      'of <a href="http://www.gnu.org/licenses'
                                                      '/gpl-3.0.html">GNU Public License Version 3</a>'),
                                        logo_notice=_('Aard Dictionary logo by Iryna Gerasymova'),
                                        icons_notice=_('Human-O2 icon set by '
                                                       '<a href="http://schollidesign.deviantart.com">'
                                                       '~schollidesign</a>')
                                        )
                                   )

http_link_re = re.compile("http[s]?://[^\s\)]+", re.UNICODE)


def mkicon(name, toggle_name=None, icondir=icondir):
    icon = QIcon()
    for size in os.listdir(icondir):
        current_dir = os.path.join(icondir, size)
        icon.addFile(os.path.join(current_dir, name+'.png'))
        if toggle_name:
            icon.addFile(os.path.join(current_dir, toggle_name+'.png'),
                         QSize(), QIcon.Active, QIcon.On)
    return icon

icons = {}

def load_icons():
    icons['edit-find'] = mkicon('actions/edit-find')
    icons['system-search'] = mkicon('actions/system-search')
    icons['add-file'] = mkicon('actions/add-files-to-archive')
    icons['add-folder'] = mkicon('actions/add-folder-to-archive')
    icons['list-remove'] = mkicon('actions/list-remove')
    icons['go-next'] = mkicon('actions/go-next')
    icons['go-previous'] = mkicon('actions/go-previous')
    icons['go-next-page'] = mkicon('actions/go-next-page')
    icons['go-previous-page'] = mkicon('actions/go-previous-page')
    icons['view-fullscreen'] = mkicon('actions/view-fullscreen',
                                      toggle_name='actions/view-restore')
    icons['application-exit'] = mkicon('actions/application-exit')
    icons['zoom-in'] = mkicon('actions/zoom-in')
    icons['zoom-out'] = mkicon('actions/zoom-out')
    icons['zoom-original'] = mkicon('actions/zoom-original')
    icons['help-about'] = mkicon('actions/help-about')
    icons['system-run'] = mkicon('actions/system-run')
    icons['document-open-recent'] = mkicon('actions/document-open-recent')
    icons['document-properties'] = mkicon('actions/document-properties')

    icons['folder'] = mkicon('places/folder')
    icons['file'] = mkicon('mimetypes/text-x-preview')

    icons['emblem-web'] = mkicon('emblems/emblem-web')
    icons['emblem-ok'] = mkicon('emblems/emblem-ok')
    icons['emblem-unreadable'] = mkicon('emblems/emblem-unreadable')
    icons['emblem-art2'] = mkicon('emblems/emblem-art2')

    icons['info'] = mkicon('status/dialog-information')
    icons['question'] = mkicon('status/dialog-question')
    icons['warning'] = mkicon('status/dialog-warning')
    icons['aarddict'] = mkicon('apps/aarddict', icondir=logodir)
    icons['document-save'] = mkicon('actions/document-save')
    icons['edit-copy'] = mkicon('actions/edit-copy')


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

    def __init__(self, parent=None):
        QWebView.__init__(self, parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        connect(self,SIGNAL('customContextMenuRequested (const QPoint&)'),
                self.context_menu_requested)

    def context_menu_requested(self, point):
        context_menu = QMenu()
        frame = self.page().currentFrame()

        if unicode(self.selectedText()):
            context_menu.addAction(self.pageAction(QWebPage.Copy))
        hit_test = frame.hitTestContent(point)
        if unicode(hit_test.linkUrl().toString()):
            context_menu.addAction(self.pageAction(QWebPage.CopyLinkToClipboard))
        context_menu.addAction(self.pageAction(QWebPage.SelectAll))

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

dict_access_lock = QMutex()


class WordLookupStopRequested(Exception): pass


class WordLookupThread(QThread):

    def __init__(self, dictionaries, word, parent=None):
        QThread.__init__(self, parent)
        self.dictionaries = dictionaries
        self.word = word
        self.stop_requested = False

    def run(self):
        wordstr = unicode(self.word)
        log.debug("Looking up %r", wordstr)
        articles = []
        dict_access_lock.lock()
        try:
            for article in self.dictionaries.best_match(wordstr):
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

    def __init__(self, article_read_funcs, parent=None, use_mediawiki_style=False):
        QThread.__init__(self, parent)
        self.article_read_funcs = article_read_funcs
        self.stop_requested = False
        self.use_mediawiki_style = use_mediawiki_style
        self.html_cache = {}
        self.errors = []

    def run(self):
        self.emit(SIGNAL("article_load_started"), self.article_read_funcs)
        dict_access_lock.lock()
        try:
            for read_func in self.article_read_funcs:
                article = self._load_article(read_func)
                html = self._tohtml(article)
                title = read_func.title
                self.emit(SIGNAL("article_loaded"), title, article, html)
                QThread.yieldCurrentThread()
        except ArticleLoadStopRequested:
            self.emit(SIGNAL("article_load_stopped"), self)
        except Exception, e:
            self.errors.append((read_func, e))
        else:
            self.emit(SIGNAL("article_load_finished"), self, self.article_read_funcs)
        finally:
            dict_access_lock.unlock()
            self.html_cache.clear()
            del self.html_cache
            del self.article_read_funcs

    def _load_article(self, read_func):
        t0 = time.time()
        if self.stop_requested:
            raise ArticleLoadStopRequested
        try:
            article = read_func()
        except RedirectResolveError, e:
            log.debug('Failed to resolve redirect', exc_info=1)
            article = Article(e.article.title,
                              _('Redirect to %s not found') % e.article.redirect.encode('utf8'),
                              dictionary=e.article.dictionary)
        log.debug('Read %r from %s in %ss',
                  article.title,
                  article.dictionary, time.time() - t0)
        return article

    def _tohtml(self, article):
        t0 = time.time()
        if self.stop_requested:
            raise ArticleLoadStopRequested

        cache_key = (article.position, article.dictionary)
        if cache_key in self.html_cache:
            result = self.html_cache[cache_key]
        else:
            article_format = article.dictionary.metadata['article_format']

            result = ['<html>',
                      '<head>']
            if self.use_mediawiki_style:
                result.append(mediawiki_style)
            else:
                result.append(aard_style)
            result += ['<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>'
                       '</head>',
                      '<body>',
                      '<div id="globalWrapper">']
            if article_format == 'json':
                for c in aar2html.convert(article):
                    if self.stop_requested:
                        raise ArticleLoadStopRequested
                    result.append(c)
                steps = [aar2html.fix_new_lines,
                         ''.join,
                         aar2html.remove_p_after_h,
                         aar2html.add_notebackrefs]
                for step in steps:
                    if self.stop_requested:
                        raise ArticleLoadStopRequested
                    result = step(result)
            else:
                result = ''.join(result)
                result += article.text
            result += js
            result += '</div></body></html>'
            self.html_cache[cache_key] = result
        log.debug('Converted %r in %ss',
                  article.title, time.time() - t0)
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
                self.emit(SIGNAL("dict_open_failed"), candidate, str(e))
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
                if not self.stop_requested:
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
                f.write(source.encode('utf8'))
                f.write('\n')
                written.append(source)
            else:
                log.debug('Source %r is already written, ignoring', source)
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

def read_preferred_dicts():
    if os.path.exists(preferred_dicts_file):
        def parse(line):
            key, val = line.split()
            return (UUID(hex=key).bytes, float(val))
        return dict(parse(line) for line
                    in load_file(preferred_dicts_file).splitlines()
                    if line)
    else:
        return {}

def write_preferred_dicts(preferred_dicts):
    with open(preferred_dicts_file, 'w') as f:
        f.write('\n'.join( '%s %s' % (UUID(bytes=key).hex, val)
                           for key, val in preferred_dicts.iteritems()))

def write_lastfiledir(lastfiledir):
    with open(lastfiledir_file, 'w') as f:
        f.write(lastfiledir.encode('utf8'))

def read_lastfiledir():
    if os.path.exists(lastfiledir_file):
        return load_file(lastfiledir_file).strip()
    else:
        return os.path.expanduser('~')

def write_lastdirdir(lastdirdir):
    with open(lastdirdir_file, 'w') as f:
        f.write(lastdirdir.encode('utf8'))

def read_lastdirdir():
    if os.path.exists(lastdirdir_file):
        return load_file(lastdirdir_file).strip()
    else:
        return os.path.expanduser('~')

def write_lastsave(lastsave):
    with open(lastsave_file, 'w') as f:
        f.write(lastsave.encode('utf8'))

def read_lastsave():
    if os.path.exists(lastsave_file):
        return load_file(lastsave_file).strip()
    else:
        return os.path.expanduser('~')


def read_geometry():
    if os.path.exists(geometry_file):
        return tuple(int(item) for item in load_file(geometry_file).split())
    else:
        r = QRect(0, 0, 640, 480)
        r.moveCenter(QApplication.desktop().availableGeometry().center())
    return (r.x(), r.y(), r.width(), r.height())

def write_geometry(rect_tuple):
    with open(geometry_file, 'w') as f:
        f.write(' '.join(str(item) for item in rect_tuple))

def read_zoomfactor():
    if os.path.exists(zoomfactor_file):
        try:
            return float(load_file(zoomfactor_file))
        except:
            return 1.0
    else:
        return 1.0

def write_zoomfactor(zoomfactor):
    with open(zoomfactor_file, 'w') as f:
        f.write(str(zoomfactor))

def mkcss(values):    
    return aard_style_tmpl.substitute(values)

aard_style = None

def update_css(css):
    global aard_style    
    aard_style = css
    return aard_style


default_colors = dict(active_link_bg='#e0e8e8',
                      footnote_fg='#00557f',
                      internal_link_fg='maroon',
                      external_link_fg='#0000cc',
                      footnote_backref_fg='#00557f',
                      table_bg='')

def read_appearance():
    colors = dict(default_colors)
    use_mediawiki_style = True
    appearance_conf.read(appearance_file)
    if appearance_conf.has_section('colors'):
        for opt in appearance_conf.options('colors'):
            colors[opt] = appearance_conf.get('colors', opt)
    if appearance_conf.has_section('style'):
        use_mediawiki_style = appearance_conf.getboolean('style', 'use_mediawiki_style')
    return colors, use_mediawiki_style

def write_appearance(colors, use_mediawiki_style):
    if not appearance_conf.has_section('colors'):
        appearance_conf.add_section('colors')
    if not appearance_conf.has_section('style'):
        appearance_conf.add_section('style')
    for key, val in colors.iteritems():
        appearance_conf.set('colors', key, val)
    appearance_conf.set('style', 'use_mediawiki_style', use_mediawiki_style)
    with open(appearance_file, 'w') as f:
        appearance_conf.write(f)

grouping_strength = {1: QUATERNARY, 2: TERTIARY, 3: SECONDARY}

def article_grouping_key(article):
    title = article.title
    strength = grouping_strength.get(len(title), PRIMARY)
    return collation_key(title, strength).getByteArray()


class TabWidget(QTabWidget):

    def __init__(self):
        QTabWidget.__init__(self)
        self.setDocumentMode(True)
        self.article_progress = QProgressBar(self)
        self.article_progress.setMinimum(0)
        self.article_progress.hide()
        self.article_progress.setTextVisible(False)

    def _update_progress_pos(self):
        self.article_progress.move(self.geometry().width() -
                                   self.article_progress.geometry().width() - 3, 2)


    def progress_start(self, maximum):
        self.article_progress.setMaximum(maximum)
        self.article_progress.setValue(0)
        self.article_progress.show()

    def progress_update(self):
        value = self.article_progress.value() + 1
        self.article_progress.setValue(value)
        if value == self.article_progress.maximum():
            self.progress_stop()

    def progress_stop(self):
        self.article_progress.hide()

    def resizeEvent(self, event):
        QTabWidget.resizeEvent(self, event)
        self._update_progress_pos()


def fix_float_title(widget, title_key, floating):
    title = _(title_key)
    if floating:
        title = title.replace('&', '')
    widget.setWindowTitle(title)


class DictView(QMainWindow):

    def __init__(self, debug=False):
        QMainWindow.__init__(self)
        self.setUnifiedTitleAndToolBarOnMac(False)
        self.setWindowIcon(icons['aarddict'])

        self.dictionaries = DictionaryCollection()
        self.update_title()

        action_lookup_box = QAction(_('&Lookup Box'), self)
        action_lookup_box.setIcon(icons['edit-find'])
        action_lookup_box.setShortcuts([_('Ctrl+L'), _('F2')])
        action_lookup_box.setToolTip(_('Move focus to word input and select its content'))
        connect(action_lookup_box, SIGNAL('triggered()'), self.go_to_lookup_box)

        self.word_input = WordInput(action_lookup_box)

        connect(self.word_input, SIGNAL('textEdited (const QString&)'),
                     self.word_input_text_edited)
        self.word_completion = QListWidget()
        connect(self.word_input, SIGNAL('word_input_down'), self.select_next_word)
        connect(self.word_input, SIGNAL('word_input_up'), self.select_prev_word)

        def focus_current_tab():
            current_tab = self.tabs.currentWidget()
            if current_tab:
                current_tab.setFocus()
        connect(self.word_input, SIGNAL('returnPressed ()'),
                focus_current_tab)

        box = QVBoxLayout()
        box.setSpacing(2)
        #we want right margin set to 0 since it borders with splitter
        #(left widget)
        box.setContentsMargins(2, 2, 0, 2)
        box.addWidget(self.word_input)
        box.addWidget(self.word_completion)
        lookup_pane = QWidget()
        lookup_pane.setLayout(box)

        self.history_view = QListWidget()

        self.action_history_back = QAction(icons['go-previous'], _('&Back'), self)
        self.action_history_back.setShortcuts([QKeySequence.Back, _('Ctrl+['), _('Esc')])
        self.action_history_back.setToolTip(_('Go back to previous word in history'))
        connect(self.action_history_back, SIGNAL('triggered()'), self.history_back)
        self.action_history_fwd = QAction(icons['go-next'], _('&Forward'), self)
        self.action_history_fwd.setShortcuts([QKeySequence.Forward, _('Ctrl+]'), _('Shift+Esc')])
        self.action_history_fwd.setToolTip(_('Go forward to next word in history'))
        connect(self.action_history_fwd, SIGNAL('triggered()'), self.history_fwd)

        connect(self.history_view,
                     SIGNAL('currentItemChanged (QListWidgetItem *,QListWidgetItem *)'),
                     self.history_selection_changed)

        connect(self.history_view,
                     SIGNAL('currentItemChanged (QListWidgetItem *,QListWidgetItem *)'),
                     self.update_history_actions)


        connect(self.word_completion,
                     SIGNAL('currentItemChanged (QListWidgetItem *,QListWidgetItem *)'),
                     self.word_selection_changed)

        self.tabs = TabWidget()

        self.setDockNestingEnabled(True)

        self.dock_lookup_pane = QDockWidget(_('&Lookup'), self)
        self.dock_lookup_pane.setObjectName('dock_lookup_pane')
        self.dock_lookup_pane.setWidget(lookup_pane)
        #On Windows and Mac OS X title bar shows & when floating
        connect(self.dock_lookup_pane, SIGNAL('topLevelChanged (bool)'),
                functools.partial(fix_float_title, self.dock_lookup_pane, '&Lookup'))
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_lookup_pane)

        dock_history = QDockWidget(_('&History'), self)
        dock_history.setObjectName('dock_history')
        dock_history.setWidget(self.history_view)
        connect(dock_history, SIGNAL('topLevelChanged (bool)'),
                functools.partial(fix_float_title, dock_history, '&History'))
        self.addDockWidget(Qt.LeftDockWidgetArea, dock_history)

        self.tabifyDockWidget(self.dock_lookup_pane, dock_history)
        self.dock_lookup_pane.raise_()


        menubar = self.menuBar()
        mn_dictionary = menubar.addMenu(_('&Dictionary'))

        action_add_dicts = QAction(icons['add-file'], _('&Add Dictionaries...'), self)
        action_add_dicts.setShortcut(_('Ctrl+O'))
        action_add_dicts.setToolTip(_('Add dictionaries'))
        connect(action_add_dicts, SIGNAL('triggered()'), self.add_dicts)
        mn_dictionary.addAction(action_add_dicts)

        action_add_dict_dir = QAction(icons['add-folder'], _('Add &Directory...'), self)
        action_add_dict_dir.setToolTip(_('Add dictionary directory'))
        connect(action_add_dict_dir, SIGNAL('triggered()'), self.add_dict_dir)
        mn_dictionary.addAction(action_add_dict_dir)

        action_verify = QAction(icons['system-run'], _('&Verify...'), self)
        action_verify.setShortcut(_('Ctrl+Y'))
        action_verify.setToolTip(_('Verify volume data integrity'))
        connect(action_verify, SIGNAL('triggered()'), self.verify)
        mn_dictionary.addAction(action_verify)

        action_remove_dict_source = QAction(icons['list-remove'], _('&Remove...'), self)
        action_remove_dict_source.setShortcut(_('Ctrl+R'))
        action_remove_dict_source.setToolTip(_('Remove dictionary or dictionary directory'))
        connect(action_remove_dict_source, SIGNAL('triggered()'), self.remove_dict_source)
        mn_dictionary.addAction(action_remove_dict_source)

        action_info = QAction(icons['document-properties'], _('&Info...'), self)
        action_info.setShortcut(_('Ctrl+I'))
        action_info.setToolTip(_('Information about open dictionaries'))
        connect(action_info, SIGNAL('triggered()'), self.show_info)
        mn_dictionary.addAction(action_info)

        action_quit = QAction(icons['application-exit'], _('&Quit'), self)
        action_quit.setShortcut(_('Ctrl+Q'))
        action_quit.setToolTip(_('Exit application'))
        action_quit.setMenuRole(QAction.QuitRole)
        connect(action_quit, SIGNAL('triggered()'), self.close)
        mn_dictionary.addAction(action_quit)

        mn_navigate = menubar.addMenu(_('&Navigate'))

        mn_navigate.addAction(action_lookup_box)

        mn_navigate.addAction(self.action_history_back)
        mn_navigate.addAction(self.action_history_fwd)

        self.action_next_article = QAction(icons['go-next-page'], _('&Next Article'), self)
        self.action_next_article.setShortcuts([_('Ctrl+K'), _('Ctrl+.')])
        self.action_next_article.setToolTip(_('Show next article'))
        connect(self.action_next_article, SIGNAL('triggered()'), self.show_next_article)
        mn_navigate.addAction(self.action_next_article)

        self.action_prev_article = QAction(icons['go-previous-page'], _('&Previous Article'), self)
        self.action_prev_article.setShortcuts([_('Ctrl+J'), _('Ctrl+,')])
        self.action_prev_article.setToolTip(_('Show previous article'))
        connect(self.action_prev_article, SIGNAL('triggered()'), self.show_prev_article)
        mn_navigate.addAction(self.action_prev_article)


        mn_article = menubar.addMenu(_('&Article'))

        self.action_copy_article = QAction(icons['edit-copy'], _('&Copy'), self)
        self.action_copy_article.setShortcut(_('Ctrl+Shift+C'))
        self.action_copy_article.setToolTip(_('Copy article to clipboard'))
        connect(self.action_copy_article, SIGNAL('triggered()'), self.copy_article)
        mn_article.addAction(self.action_copy_article)

        self.action_save_article = QAction(icons['document-save'], _('&Save...'), self)
        self.action_save_article.setShortcut(_('Ctrl+S'))
        self.action_save_article.setToolTip(_('Save article text to file'))
        connect(self.action_save_article, SIGNAL('triggered()'), self.save_article)
        mn_article.addAction(self.action_save_article)

        self.action_online_article = QAction(icons['emblem-web'], _('&View Online'), self)
        self.action_online_article.setShortcut(_('Ctrl+T'))
        self.action_online_article.setToolTip(_('Open online version of this article in a web browser'))
        connect(self.action_online_article, SIGNAL('triggered()'), self.show_article_online)
        mn_article.addAction(self.action_online_article)

        mn_view = menubar.addMenu(_('&View'))

        mn_view.addAction(self.dock_lookup_pane.toggleViewAction())
        mn_view.addAction(dock_history.toggleViewAction())

        toolbar = QToolBar(_('&Toolbar'), self)
        toolbar.setObjectName('toolbar')
        mn_view.addAction(toolbar.toggleViewAction())

        action_article_appearance = QAction(icons['emblem-art2'], _('&Article Appearance...'), self)
        action_article_appearance.setToolTip(_('Customize article appearance'))
        connect(action_article_appearance, SIGNAL('triggered()'), self.article_appearance)
        mn_view.addAction(action_article_appearance)

        mn_text_size = mn_view.addMenu(_('Text &Size'))

        action_increase_text = QAction(icons['zoom-in'], _('&Increase'), self)
        action_increase_text.setShortcuts([QKeySequence.ZoomIn, _("Ctrl+="), _('F7')])
        action_increase_text.setToolTip(_('Increase size of article text'))
        connect(action_increase_text, SIGNAL('triggered()'), self.increase_text_size)
        mn_text_size.addAction(action_increase_text)

        action_decrease_text = QAction(icons['zoom-out'], _('&Decrease'), self)
        action_decrease_text.setShortcuts([QKeySequence.ZoomOut, _('F8')])
        action_decrease_text.setToolTip(_('Decrease size of article text'))
        connect(action_decrease_text, SIGNAL('triggered()'), self.decrease_text_size)
        mn_text_size.addAction(action_decrease_text)

        action_reset_text = QAction(icons['zoom-original'], _('&Reset'), self)
        action_reset_text.setShortcut(_('Ctrl+0'))
        action_reset_text.setToolTip(_('Reset size of article text to default'))
        connect(action_reset_text, SIGNAL('triggered()'), self.reset_text_size)
        mn_text_size.addAction(action_reset_text)

        action_full_screen = QAction(icons['view-fullscreen'], _('&Full Screen'), self)
        action_full_screen.setShortcut(_('F11'))
        action_full_screen.setToolTip(_('Toggle full screen mode'))
        action_full_screen.setCheckable(True)
        connect(action_full_screen, SIGNAL('triggered(bool)'), self.toggle_full_screen)
        mn_view.addAction(action_full_screen)

        mn_help = menubar.addMenu(_('H&elp'))

        action_about = QAction(icons['help-about'], _('&About...'), self)
        action_about.setToolTip(_('Information about Aard Dictionary'))
        action_about.setMenuRole(QAction.AboutRole)
        connect(action_about, SIGNAL('triggered()'), self.about)
        mn_help.addAction(action_about)

        toolbar.addAction(self.action_history_back)
        toolbar.addAction(self.action_history_fwd)
        toolbar.addAction(self.action_online_article)
        toolbar.addSeparator()
        toolbar.addAction(action_increase_text)
        toolbar.addAction(action_decrease_text)
        toolbar.addAction(action_reset_text)
        toolbar.addAction(action_full_screen)
        toolbar.addSeparator()
        toolbar.addAction(action_add_dicts)
        toolbar.addAction(action_add_dict_dir)
        toolbar.addAction(action_info)
        toolbar.addSeparator()
        toolbar.addAction(action_quit)
        self.addToolBar(toolbar)

        self.setCentralWidget(self.tabs)

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.scheduled_func = None

        self.preferred_dicts = {}

        connect(self.tabs, SIGNAL('currentChanged (int)'),
                self.article_tab_switched)

        self.current_lookup_thread = None

        self.sources = []
        self.zoom_factor = 1.0
        self.lastfiledir = u''
        self.lastdirdir = u''
        self.lastsave = u''

        self.use_mediawiki_style = True
        self.update_current_article_actions(-1)

    def add_debug_menu(self):
        import debug

        mn_debug = self.menuBar().addMenu('Debug')

        action_cache_stats = QAction('Cache Stats', self)
        connect(action_cache_stats, SIGNAL('triggered()'),
                debug.dump_cache_stats)
        mn_debug.addAction(action_cache_stats)

        action_instances_diff = QAction('Instances Diff', self)
        connect(action_instances_diff, SIGNAL('triggered()'),
                debug.dump_type_count_diff)
        mn_debug.addAction(action_instances_diff)

        action_set_diff_checkpoint = QAction('Set Instances Diff Checkpoint', self)
        connect(action_set_diff_checkpoint, SIGNAL('triggered()'),
                debug.set_type_count_checkpoint)
        mn_debug.addAction(action_set_diff_checkpoint)

        action_instances_checkpoint_diff = QAction('Instances Checkpoint Diff', self)
        connect(action_instances_checkpoint_diff, SIGNAL('triggered()'),
                debug.dump_type_count_checkpoint_diff)
        mn_debug.addAction(action_instances_checkpoint_diff)

        action_rungc = QAction('Run GC', self)
        connect(action_rungc, SIGNAL('triggered()'),
                debug.rungc)
        mn_debug.addAction(action_rungc)


    def add_dicts(self):
        self.open_dicts(self.select_files())

    def add_dict_dir(self):
        self.open_dicts(self.select_dir())

    def open_dicts(self, sources):

        self.sources = write_sources(self.sources + sources)

        dict_open_thread = DictOpenThread(sources, self)

        progress = QProgressDialog(self)
        progress.setLabelText(_('Opening dictionaries...'))
        progress.setCancelButtonText(_('Stop'))
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
            log.debug('Opened %r' % d.file_name)
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
            self.update_title()
            self.update_preferred_dicts()
            if errors:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle(_('Open Failed'))
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setInformativeText(_('Failed to open some dictionaries'))
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
        file_names = QFileDialog.getOpenFileNames(self, _('Add Dictionary'),
                                                  self.lastfiledir,
                                                  _('Aard Dictionary Files')+' (*.aar)')
        file_names = [unicode(name) for name in file_names]
        if file_names:
            self.lastfiledir = os.path.dirname(file_names[-1])
        return file_names


    def select_dir(self):
        name = QFileDialog.getExistingDirectory (self, _('Add Dictionary Directory'),
                                                      self.lastdirdir,
                                                      QFileDialog.ShowDirsOnly)
        dirname = unicode(name)
        if dirname:
            self.lastdirdir = os.path.dirname(dirname)
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

        connect(btn_select_all, SIGNAL('clicked()'), item_list.selectAll)

        btn_remove = QPushButton(icons['list-remove'], _('&Remove'))

        def remove():
            rows = [index.row() for index in item_list.selectedIndexes()]
            for row in reversed(sorted(rows)):
                item_list.takeItem(row)
            if rows:
                remaining = [unicode(item_list.item(i).text())
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
            self.update_title()
            func = functools.partial(self.update_word_completion, self.word_input.text())
            self.schedule(func, 0)

    def article_tab_switched(self, current_tab_index):
        if current_tab_index > -1:
            web_view = self.tabs.widget(current_tab_index)
            dict_uuid = str(web_view.property('aard:dictionary').toByteArray())
            self.update_preferred_dicts(dict_uuid=dict_uuid)
        self.update_current_article_actions(current_tab_index)

    def update_current_article_actions(self, current_tab_index):
        count = self.tabs.count()
        self.action_next_article.setEnabled(-1 < current_tab_index < count - 1)
        self.action_prev_article.setEnabled(current_tab_index > 0)
        self.action_online_article.setEnabled(self.get_current_article_url() is not None)
        self.action_save_article.setEnabled(count > 0)
        self.action_copy_article.setEnabled(count > 0)

    def update_preferred_dicts(self, dict_uuid=None):
        if dict_uuid:
            self.preferred_dicts[dict_uuid] = time.time()
        self.dictionaries.sort(key=lambda d: -self.preferred_dicts.get(d.uuid, 0))

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
        self.word_input.setFocus()
        self.word_completion.clear()
        self.word_completion.addItem('Loading...')
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
        word_lookup_thread.start(QThread.LowestPriority)

    def word_lookup_finished(self, word, articles):
        log.debug('Lookup for %r finished, got %d article(s)', word, len(articles))
        self.word_completion.clear()
        items = dict()
        for article in articles:
            article_key =  article_grouping_key(article)
            if article_key in items:
                item = items[article_key]
                article_group = item.data(Qt.UserRole).toPyObject()
                article_group.append(article)
                item.setData(Qt.UserRole, QVariant(article_group))
            else:
                item = QListWidgetItem()
                item.setText(article.title)
                item.setData(Qt.UserRole, QVariant([article]))
                items[article_key] = item
            self.word_completion.addItem(item)

        count = range(self.word_completion.count())
        if count:
            item = self.word_completion.item(0)
            self.word_completion.setCurrentItem(item)
            self.word_completion.scrollToItem(item)
        else:
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

    def word_selection_changed(self, selected, deselected):
        func = functools.partial(self.update_shown_article, selected)
        self.schedule(func, 200)

    def history_selection_changed(self, selected, deselected):
        title = unicode(selected.text()) if selected else u''
        func = functools.partial(self.set_word_input, title)
        self.schedule(func, 200)

    def update_history_actions(self, selected, deselected):
        current_row = self.history_view.currentRow()
        self.action_history_fwd.setEnabled(current_row > 0)
        self.action_history_back.setEnabled(-1 < current_row < self.history_view.count() - 1)

    def update_shown_article(self, selected):
        self.emit(SIGNAL("stop_article_load"))
        self.clear_current_articles()
        if selected:
            self.add_to_history(unicode(selected.text()))
            article_group = selected.data(Qt.UserRole).toPyObject()
            self.tabs.progress_start(2*len(article_group))
            load_thread = ArticleLoadThread(article_group, self, self.use_mediawiki_style)
            connect(load_thread, SIGNAL("article_loaded"),
                    self.article_loaded, Qt.QueuedConnection)

            def finished():
                if load_thread.errors:
                    errors_txt = u'\n'.join([(_('Error reading article %(title)s from '
                                                '%(dict_title)s (file %(dict_file)s): '
                                                '%(exception)s') %
                                              dict(title=read_func.title,
                                                   dict_title=format_title(read_func.source),
                                                   dict_file=read_func.source.file_name,
                                                   exception=ex))
                                             for read_func, ex in load_thread.errors])
                    for error in load_thread.errors:
                        read_func, ex = error
                    msg_box = QMessageBox(self)
                    msg_box.setWindowTitle(_('Article Load Failed'))
                    msg_box.setIcon(QMessageBox.Critical)
                    msg_box.setInformativeText(_('There was an error while loading articles. '
                                                 'Dictionary files may be corrupted. '
                                                 'Would you like to verify now?'))
                    msg_box.setDetailedText(errors_txt)
                    msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    result = msg_box.exec_()
                    if result == QMessageBox.Yes:
                        self.verify()
                del load_thread.errors[:]
                load_thread.setParent(None)

            connect(load_thread, SIGNAL("finished ()"),
                    finished,
                    Qt.QueuedConnection)
            connect(load_thread, SIGNAL("article_load_started"),
                    self.article_load_started, Qt.QueuedConnection)
            connect(load_thread, SIGNAL("article_load_stopped"),
                    self.tabs.progress_stop, Qt.QueuedConnection)
            connect(self, SIGNAL("stop_article_load"),
                    load_thread.stop, Qt.QueuedConnection)
            load_thread.start(QThread.LowestPriority)

    def clear_current_articles(self):
        self.tabs.blockSignals(True)
        for i in reversed(range(self.tabs.count())):
            w = self.tabs.widget(i)
            self.tabs.removeTab(i)
            w.deleteLater()
        self.tabs.blockSignals(False)
        self.update_current_article_actions(self.tabs.currentIndex())

    def article_loaded(self, title, article, html):
        log.debug('Loaded article %r (original title %r) (section %r) (%r at %r)',
                  article.title, title, article.section, article.position, article.dictionary)

        dictionary = article.dictionary
        volume = dictionary.key()
        self.tabs.progress_update()
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            pos = w.property('aard:position').toPyObject()
            vol = w.property('aard:volume').toPyObject()
            if pos == article.position and vol == volume:
                log.debug('Duplicate article')
                tooltip = unicode(self.tabs.tabToolTip(i))
                self.tabs.setTabToolTip(i, u'\n'.join((tooltip, title)))
                self.tabs.progress_update()
                return

        view = WebView()
        view.setPage(WebPage(view))
        view.setProperty('aard:dictionary', QVariant(dictionary.uuid))
        view.setProperty('aard:volume', QVariant(volume))
        view.setProperty('aard:title', QVariant(article.title))
        view.setProperty('aard:position', QVariant(article.position))

        def loadFinished(ok):
            if ok and article.section:
                self.go_to_section(view, article.section)
            self.tabs.progress_update()

        connect(view, SIGNAL('loadFinished (bool)'),
                loadFinished, Qt.QueuedConnection)

        view.page().currentFrame().setHtml(html, QUrl(title))
        view.setZoomFactor(self.zoom_factor)

        dict_title = format_title(dictionary)
        i = self.tabs.count()
        if i < 9:
            tab_label = ('&%d ' % (i+1))+dict_title
        else:
            tab_label = dict_title

        self.tabs.blockSignals(True)
        self.tabs.addTab(view, tab_label)
        self.tabs.setTabToolTip(self.tabs.count() - 1,
                                u'\n'.join((dict_title, title)))
        self.select_preferred_dict()
        self.tabs.blockSignals(False)
        self.update_current_article_actions(self.tabs.currentIndex())

        connect(view, SIGNAL('linkClicked (const QUrl&)'),
                     self.link_clicked)


    def article_load_started(self, read_funcs):
        log.debug('Loading %d article(s)', len(read_funcs))

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
                logging.debug('No site info in dictionary %r', dictionary_key)
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


    def link_clicked(self, url):
        scheme = url.scheme()
        title = unicode(url.toString())
        log.debug('Link clicked: %r', title)
        if scheme in ('http', 'https', 'ftp', 'sftp'):
            webbrowser.open(title)
        else:
            if '_' in title:
                log.debug('Found underscore character in title %r, replacing with space',
                          title)
                title = title.replace(u'_', u' ')
            if title.startswith('#'):
                current_tab = self.tabs.currentWidget()
                if current_tab:
                    self.go_to_section(current_tab, title[1:])
                else:
                    log.error('Link %r clicked, but no article view?', title)
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
        if self.dock_lookup_pane.isHidden():
            self.dock_lookup_pane.show()
            QTimer.singleShot(20, self.go_to_lookup_box)
        else:
            self.dock_lookup_pane.raise_()
            self.dock_lookup_pane.activateWindow()
            self.word_input.setFocus()
            self.word_input.selectAll()

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
        item_list.setSelectionModel(SingleRowItemSelectionModel(item_list.model()))

        for i, dictionary in enumerate(self.dictionaries):
            text = format_title(dictionary)
            item = QTableWidgetItem(text)
            item.setData(Qt.UserRole, QVariant(dictionary.key()))
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
            dict_key = str(item.data(Qt.UserRole).toString())
            volume = [d for d in self.dictionaries if d.key() == dict_key][0]
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

            connect(progress, SIGNAL('canceled ()'), verify_thread.stop, Qt.DirectConnection)
            connect(verify_thread, SIGNAL('progress'), update_progress,
                    Qt.QueuedConnection)
            connect(verify_thread, SIGNAL('verified'), verified,
                    Qt.QueuedConnection)
            connect(verify_thread, SIGNAL('finished()'), finished,
                    Qt.QueuedConnection)
            verify_thread.start(QThread.LowestPriority)


        connect(btn_verify, SIGNAL('clicked()'), verify)

        button_box.addButton(btn_verify, QDialogButtonBox.ApplyRole)
        button_box.setStandardButtons(QDialogButtonBox.Close)

        content.addWidget(button_box)

        connect(button_box, SIGNAL('rejected()'), dialog.reject)

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
            dictmap[UUID(bytes=dictionary.uuid).hex].append(dictionary)

        for uuid_hex, dicts in dictmap.iteritems():
            text = format_title(dicts[0], with_vol_num=False)
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, QVariant(uuid_hex))
            item_list.addItem(item)

        splitter = QSplitter()
        splitter.addWidget(item_list)
        detail_view = WebView()
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
                    params['copyright'] = '<h2>%s</h2>%s' %(_('Copyright Notice'), linkify(d.copyright))
                if d.license:
                    params['license'] = '<h2>%s</h2><pre>%s</pre>' % (_('License'), d.license)

                html = dict_detail_tmpl.safe_substitute(params)
            else:
                html = ''
            detail_view.setHtml(html)

        connect(item_list,
                SIGNAL('currentItemChanged (QListWidgetItem *,QListWidgetItem *)'),
                current_changed)

        if item_list.count():
            item_list.setCurrentRow(0)

        connect(button_box, SIGNAL('rejected()'), dialog.reject)

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

        preview_pane.page().currentFrame().setHtml(mediawiki_style if self.use_mediawiki_style 
                                                   else aard_style + html)

        colors = read_appearance()[0]

        color_pane = QGridLayout()
        color_pane.setColumnStretch(1, 2)

        def set_color(btn, color_name):
            c = QColorDialog.getColor(QColor(colors[color_name]))
            if c.isValid():
                pixmap = QPixmap(24, 16)
                pixmap.fill(c)
                btn.setIcon(QIcon(pixmap))
                colors[color_name] = str(c.name())
                style_str = mkcss(colors)
                preview_pane.page().currentFrame().setHtml(style_str + html)


        pixmap = QPixmap(24, 16)
        pixmap.fill(QColor(colors['internal_link_fg']))
        btn_internal_link = QPushButton()
        btn_internal_link.setIcon(QIcon(pixmap))
        color_pane.addWidget(btn_internal_link, 0, 0)
        color_pane.addWidget(QLabel(_('Internal Link')), 0, 1)

        connect(btn_internal_link, SIGNAL('clicked()'),
                functools.partial(set_color, btn_internal_link, 'internal_link_fg'))

        pixmap = QPixmap(24, 16)
        pixmap.fill(QColor(colors['external_link_fg']))
        btn_external_link = QPushButton()
        btn_external_link.setIcon(QIcon(pixmap))
        color_pane.addWidget(btn_external_link, 1, 0)
        color_pane.addWidget(QLabel(_('External Link')), 1, 1)

        connect(btn_external_link, SIGNAL('clicked()'),
                functools.partial(set_color, btn_external_link, 'external_link_fg'))

        pixmap = QPixmap(24, 16)
        pixmap.fill(QColor(colors['footnote_fg']))
        btn_footnote = QPushButton()
        btn_footnote.setIcon(QIcon(pixmap))
        color_pane.addWidget(btn_footnote, 2, 0)
        color_pane.addWidget(QLabel(_('Footnote Link')), 2, 1)

        connect(btn_footnote, SIGNAL('clicked()'),
                functools.partial(set_color, btn_footnote, 'footnote_fg'))

        pixmap = QPixmap(24, 16)
        pixmap.fill(QColor(colors['footnote_backref_fg']))
        btn_footnote_back = QPushButton()
        btn_footnote_back.setIcon(QIcon(pixmap))
        color_pane.addWidget(btn_footnote_back, 3, 0)
        color_pane.addWidget(QLabel(_('Footnote Back Link')), 3, 1)

        connect(btn_footnote_back, SIGNAL('clicked()'),
                functools.partial(set_color, btn_footnote_back, 'footnote_backref_fg'))

        pixmap = QPixmap(24, 16)
        pixmap.fill(QColor(colors['active_link_bg']))
        btn_active_link = QPushButton()
        btn_active_link.setIcon(QIcon(pixmap))
        color_pane.addWidget(btn_active_link, 4, 0)
        color_pane.addWidget(QLabel(_('Active Link')), 4, 1)

        connect(btn_active_link, SIGNAL('clicked()'),
                functools.partial(set_color, btn_active_link, 'active_link_bg'))

        cb_use_mediawiki_style = QCheckBox(_('Use Wikipedia style'))
        color_pane.addWidget(cb_use_mediawiki_style, 5, 0, 1, 2)

        def use_mediawiki_style_changed(state):
            if state == Qt.Checked:
                style_str = mediawiki_style
            else:
                style_str = mkcss(colors)
            preview_pane.page().currentFrame().setHtml(style_str + html)

        connect(cb_use_mediawiki_style, SIGNAL('stateChanged(int)'),
                use_mediawiki_style_changed)

        cb_use_mediawiki_style.setChecked(self.use_mediawiki_style)

        color_pane.addWidget(preview_pane, 0, 2, 6, 1)

        content.addLayout(color_pane)

        button_box = QDialogButtonBox()

        button_box.setStandardButtons(QDialogButtonBox.Close)

        content.addWidget(button_box)

        def close():
            dialog.reject()
            update_css(mkcss(colors))
            self.use_mediawiki_style = cb_use_mediawiki_style.isChecked()
            style_str = mediawiki_style if self.use_mediawiki_style else aard_style
            for i in range(self.tabs.count()):
                view = self.tabs.widget(i)
                currentFrame = view.page().currentFrame()
                html = unicode(currentFrame.toHtml())
                html = style_tag_re.sub(style_str, html, count=1)
                view.page().currentFrame().setHtml(html)
            write_appearance(colors, self.use_mediawiki_style)

        connect(button_box, SIGNAL('rejected()'), close)

        dialog.setLayout(content)

        dialog.exec_()

    def closeEvent(self, event):
        self.write_settings()
        for d in self.dictionaries:
            d.close()
        event.accept()

    def write_settings(self):
        history = []
        for i in reversed(range(self.history_view.count())):
            item = self.history_view.item(i)
            history.append(unicode(item.text()))
        write_history(history)
        write_preferred_dicts(self.preferred_dicts)
        pos = self.pos()
        size = self.size()
        write_geometry((pos.x(), pos.y(), size.width(), size.height()))
        layout = self.saveState()
        with open(layout_file, 'wb') as f:
            f.write(str(layout))
        with open(history_current_file, 'w') as f:
            f.write(str(self.history_view.currentRow()))
        write_lastfiledir(self.lastfiledir)
        write_lastdirdir(self.lastdirdir)
        write_lastsave(self.lastsave)
        write_zoomfactor(self.zoom_factor)

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
            article_title = unicode(current_tab.property('aard:title').toString())
            dirname = os.path.dirname(self.lastsave)
            propose_name = os.path.extsep.join((article_title, u'html'))
            file_name = QFileDialog.getSaveFileName(self, _('Save Article'),
                                                    os.path.join(dirname, propose_name),
                                                    _('HTML Documents (*.htm *.html)'))
            if file_name:
                file_name = unicode(file_name)
                self.lastsave = file_name
                try:
                    with open(file_name, 'w') as f:
                        current_frame = current_tab.page().currentFrame()
                        html = unicode(current_frame.toHtml())
                        f.write(html.encode('utf8'))
                except Exception, e:
                    msg_box = QMessageBox(self)
                    msg_box.setWindowTitle(_('Failed to Save Article'))
                    msg_box.setIcon(QMessageBox.Critical)
                    msg_box.setInformativeText(_('There was an error when writing article to file %s')
                                               % file_name)
                    msg_box.setDetailedText(unicode(e))
                    msg_box.setStandardButtons(QMessageBox.Ok)
                    msg_box.open()


    def copy_article(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            page = current_tab.page()
            page.triggerAction(QWebPage.SelectAll)
            page.triggerAction(QWebPage.Copy)
            page.currentFrame().evaluateJavaScript("document.getSelection().empty();")

def main(args, debug=False, dev_extras=False):

    if not os.path.exists(app_dir):
        os.makedirs(app_dir)
    app = QApplication(sys.argv)
    load_icons()
    dv = DictView()

    if dev_extras:
        from PyQt4.QtWebKit import QWebSettings
        (QWebSettings.globalSettings()
         .setAttribute(QWebSettings.DeveloperExtrasEnabled, True))
    if debug:
        dv.add_debug_menu()

    x, y, w, h = read_geometry()
    dv.move(QPoint(x, y))
    dv.resize(QSize(w, h))

    if os.path.exists(layout_file):
        try:
            dv.restoreState(QByteArray(load_file(layout_file, binary=True)))
        except:
            log.exception('Failed to restore layout from %s', layout_file)

    dv.show()

    for title in read_history():
        dv.add_to_history(title)

    if os.path.exists(history_current_file):
        try:
            history_current = int(load_file(history_current_file))
        except:
            log.exception('Failed to load data from %s', history_current_file)
        else:
            if history_current > -1:
                dv.history_view.blockSignals(True)
                dv.history_view.setCurrentRow(history_current)
                dv.history_view.blockSignals(False)
                word = unicode(dv.history_view.currentItem().text())
                dv.word_input.setText(word)
                dv.update_history_actions(None, None)

    dv.preferred_dicts = read_preferred_dicts()
    dv.lastfiledir = read_lastfiledir()
    dv.lastdirdir = read_lastdirdir()
    dv.lastsave = read_lastsave()
    dv.zoom_factor = read_zoomfactor()
    dv.word_input.setFocus()
    colors, use_mediawiki_style = read_appearance()
    update_css(mkcss(colors))
    dv.use_mediawiki_style = use_mediawiki_style
    preferred_enc = locale.getpreferredencoding()
    dv.open_dicts(read_sources()+[arg.decode(preferred_enc) for arg in args])
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

