import os
import gettext
import locale
import string

from PyQt4.QtCore import QTranslator, QLocale, QSize
from PyQt4.QtGui import QIcon

import aarddict
from aarddict import package_dir 

def load_file(name):
    with open(name, 'r') as f:
        return f.read().decode('utf8')

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

# style_tag_re = re.compile(u'<style type="text/css">(.+?)</style>', re.UNICODE | re.DOTALL)

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


# http_link_re = re.compile("http[s]?://[^\s\)]+", re.UNICODE)


redirect_info_tmpl = string.Template(u"""
<div id="aard-redirectinfo"">
Redirected from <strong>$title</strong>
</div>
""")

article_tmpl = string.Template(u"""<html>
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

def _load_icons():
    icons['edit-find'] = mkicon('actions/edit-find')
    icons['edit-clear'] = mkicon('actions/edit-clear')
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
    icons['window-close'] = mkicon('actions/window-close')


def _install_translator(app):

    locale.setlocale(locale.LC_ALL, '')

    if os.name == 'nt':
        # windows hack for locale setting
        lang = os.getenv('LANG')
        if lang is None:
            default_lang, default_enc = locale.getdefaultlocale()
            if default_lang:
                lang = default_lang
            if lang:
                os.environ['LANG'] = lang

    locale_dir = os.path.join(package_dir, 'locale')
    gettext_domain = aarddict.__name__
    gettext.bindtextdomain(gettext_domain, locale_dir)
    gettext.textdomain(gettext_domain)
    gettext.install(gettext_domain, locale_dir, unicode=True, names=['ngettext'])


    qtranslator = QTranslator()
    qtranslator.load('qt_'+str(QLocale.system().name()), locale_dir)
    app.installTranslator(qtranslator)
    

def load(app):
    _load_icons()
    _install_translator(app)

def css(params):
    return aard_style_tmpl.substitute(params)

aard_style = None

def update_css(css):
    global aard_style
    aard_style = css
    return aard_style

use_mediawiki_style = True

def style():
    return mediawiki_style if use_mediawiki_style else aard_style

def article(content, redirect):
    if redirect is not None:
        redirect_info = redirect_info_tmpl.substitute(dict(title=redirect))
    else:
        redirect_info = u''
    return article_tmpl.substitute(dict(style=style(),
                                        redirect_info=redirect_info,
                                        content=content,
                                        scripts=js))

def dict_detail(params):
    return dict_detail_tmpl.safe_substitute(params)

def icon(name):
    return icons[name]

def about():
    return about_tmpl.substitute(dict(appname=_(aarddict.__appname__),
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

