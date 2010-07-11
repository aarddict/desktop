import os
import gettext
import locale
from string import Template # pylint: disable-msg=W0402

from PyQt4.QtCore import QTranslator, QLocale, QSize
from PyQt4.QtGui import QIcon

import aarddict
from aarddict import package_dir 


def _read(name):
    with open(name, 'r') as f:
        return f.read().decode('utf8')


_article_js = ('<script type="text/javascript">%s</script>' %
               _read(os.path.join(package_dir, 'aar.js')))

_shared_style_str = _read(os.path.join(package_dir, 'shared.css'))

_aard_style_tmpl = Template(('<style type="text/css">%s</style>' %
                             '\n'.join((_shared_style_str,
                                        _read(os.path.join(package_dir,
                                                           'aar.css.tmpl'))))))


_mediawiki_style = ('<style type="text/css">%s</style>' %
                   '\n'.join((_shared_style_str,
                              _read(os.path.join(package_dir, 
                                                 'mediawiki_shared.css')),
                              _read(os.path.join(package_dir, 
                                                 'mediawiki_monobook.css')))))

_iconset = 'Human-O2'
_icondir = os.path.join(package_dir, 'icons/%s/' % _iconset)
_logodir = os.path.join(package_dir, 'icons/%s/' % 'hicolor')

_dict_detail_tmpl = Template("""
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

_about_tmpl = Template("""
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

_redirect_info_tmpl = Template(u"""
<div id="aard-redirectinfo"">
Redirected from <strong>$title</strong>
</div>
""")

_article_tmpl = Template(u"""<html>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
        $style
    </head>
    <body>
        <div id="globalWrapper">
        $redirect_info
        $content
        </div>
        $scripts
    </body>
</html>
""")


def _mkicon(name, toggle_name=None, icondir=_icondir):
    icon = QIcon()
    for size in os.listdir(icondir):
        current_dir = os.path.join(icondir, size)
        icon.addFile(os.path.join(current_dir, name+'.png'))
        if toggle_name:
            icon.addFile(os.path.join(current_dir, toggle_name+'.png'),
                         QSize(), QIcon.Active, QIcon.On)
    return icon

icons = {}

def _load_icons():
    icons['edit-find'] = _mkicon('actions/edit-find')
    icons['edit-clear'] = _mkicon('actions/edit-clear')
    icons['system-search'] = _mkicon('actions/system-search')
    icons['add-file'] = _mkicon('actions/add-files-to-archive')
    icons['add-folder'] = _mkicon('actions/add-folder-to-archive')
    icons['list-remove'] = _mkicon('actions/list-remove')
    icons['go-next'] = _mkicon('actions/go-next')
    icons['go-previous'] = _mkicon('actions/go-previous')
    icons['go-next-page'] = _mkicon('actions/go-next-page')
    icons['go-previous-page'] = _mkicon('actions/go-previous-page')
    icons['view-fullscreen'] = _mkicon('actions/view-fullscreen',
                                      toggle_name='actions/view-restore')
    icons['application-exit'] = _mkicon('actions/application-exit')
    icons['zoom-in'] = _mkicon('actions/zoom-in')
    icons['zoom-out'] = _mkicon('actions/zoom-out')
    icons['zoom-original'] = _mkicon('actions/zoom-original')
    icons['help-about'] = _mkicon('actions/help-about')
    icons['system-run'] = _mkicon('actions/system-run')
    icons['document-open-recent'] = _mkicon('actions/document-open-recent')
    icons['document-properties'] = _mkicon('actions/document-properties')

    icons['folder'] = _mkicon('places/folder')
    icons['file'] = _mkicon('mimetypes/text-x-preview')

    icons['emblem-web'] = _mkicon('emblems/emblem-web')
    icons['emblem-ok'] = _mkicon('emblems/emblem-ok')
    icons['emblem-unreadable'] = _mkicon('emblems/emblem-unreadable')
    icons['emblem-art2'] = _mkicon('emblems/emblem-art2')

    icons['info'] = _mkicon('status/dialog-information')
    icons['question'] = _mkicon('status/dialog-question')
    icons['warning'] = _mkicon('status/dialog-warning')
    icons['aarddict'] = _mkicon('apps/aarddict', icondir=_logodir)
    icons['document-save'] = _mkicon('actions/document-save')
    icons['edit-copy'] = _mkicon('actions/edit-copy')
    icons['window-close'] = _mkicon('actions/window-close')


def _install_translator(app):
    locale.setlocale(locale.LC_ALL, '')
    if os.name == 'nt':
        # windows hack for locale setting
        lang = os.getenv('LANG')
        if lang is None:
            default_lang = locale.getdefaultlocale()[0]
            if default_lang:
                lang = default_lang
            if lang:
                os.environ['LANG'] = lang

    locale_dir = os.path.join(package_dir, 'locale')
    gettext_domain = aarddict.__name__
    gettext.bindtextdomain(gettext_domain, locale_dir)
    gettext.textdomain(gettext_domain)
    gettext.install(gettext_domain, locale_dir, 
                    unicode=True, names=['ngettext'])

    qtranslator = QTranslator()
    qtranslator.load('qt_'+str(QLocale.system().name()), locale_dir)
    app.installTranslator(qtranslator)

    
def load(app):
    _load_icons()
    _install_translator(app)


colors = None
use_mediawiki_style = True

def style():
    return (_mediawiki_style if use_mediawiki_style else 
            _aard_style_tmpl.substitute(colors))


def article(content, redirect):
    if redirect is not None:
        redirect_info = _redirect_info_tmpl.substitute(dict(title=redirect))
    else:
        redirect_info = u''
    return _article_tmpl.substitute(dict(style=style(),
                                        redirect_info=redirect_info,
                                        content=content,
                                        scripts=_article_js))


def dict_detail(params):
    return _dict_detail_tmpl.safe_substitute(params)


def about():
    params = dict(appname=_(aarddict.__appname__),
                  version=aarddict.__version__,
                  logodir=_logodir,
                  website='http://aarddict.org',
                  copyright1=_('(C) 2006-2010 Igor Tkach'),
                  copyright2=_('(C) 2008 Jeremy Mortis'),
                  lic_notice=_('Distributed under terms and conditions '
                               'of <a href="http://www.gnu.org/licenses'
                               '/gpl-3.0.html">GNU Public License Version 3</a>'),
                  logo_notice=_('Aard Dictionary logo by Iryna Gerasymova'),
                  icons_notice=_('Human-O2 icon set by '
                                 '<a href="http://schollidesign.deviantart.com">'
                                 '~schollidesign</a>'))
    return _about_tmpl.substitute(params)

