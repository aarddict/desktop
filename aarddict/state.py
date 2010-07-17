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

import logging
import os
import gzip
import traceback

try:
    import json
except ImportError:
    import simplejson as json

from PyQt4.QtCore import QRect
from PyQt4.QtGui import QApplication, QMessageBox

log = logging.getLogger(__name__)

app_dir = os.path.expanduser('~/.aarddict')

if not os.path.exists(app_dir):
    os.makedirs(app_dir)

sources_file = os.path.join(app_dir, 'sources.json')
state_file = os.path.join(app_dir, 'state.json.gz')
appearance_file = os.path.join(app_dir, 'appearance.json')
layout_file = os.path.join(app_dir, 'layout.bin')

def write_sources(sources):
    nodupe_sources = []
    for source in sources:
        if source not in nodupe_sources:
            nodupe_sources.append(source)
        else:
            log.debug('Source %r is already written, ignoring',
                      source)
    try:
        with open(sources_file, 'w') as f:
            json.dump(nodupe_sources, f, indent=2)
    except:
        show_error(_('Failed to save list of dictionary locations'))
    return nodupe_sources

def read_sources():
    try:
        if os.path.exists(sources_file):
            with open(sources_file) as f:
                return json.load(f)
    except:
        show_error(_('Failed to load list of dictionary locations'))
    return []


def write_state(state):
    try:
        f = gzip.open(state_file, 'wb')
        try:
            json.dump(state, f, indent=2)
        finally:
            f.close()
    except:
        show_error(_('Failed to save application state'))

def read_state(load=True):
    home = os.path.expanduser('~')

    r = QRect(0, 0, 640, 480)
    r.moveCenter(QApplication.desktop().availableGeometry().center())
    geometry = [r.x(), r.y(), r.width(), r.height()]

    state = dict(last_file_parent=home,
                 last_dir_parent=home,
                 last_save=home,
                 geometry=geometry,
                 zoom_factor=1.0,
                 history=[],
                 history_current=-1,
                 scroll_values={})
    try:
        if load and os.path.exists(state_file):
            f = gzip.open(state_file, 'rb')
            try:            
                loaded = json.load(f)
                state.update(loaded)
            finally:
                f.close()
    except:
        show_error(_('Failed to load saved application state'))
    return state


def write_appearance(appearance):
    try:
        with open(appearance_file, 'w') as f:
            json.dump(appearance, f, indent=2)
    except:
        show_error(_('Failed to save appearance settings'))

def read_appearance(load=True):    
    appearance = dict(colors=dict(active_link_bg='#e0e8e8',
                                  footnote_fg='#00557f',
                                  internal_link_fg='maroon',
                                  external_link_fg='#0000cc',
                                  footnote_backref_fg='#00557f',
                                  table_bg=''),
                      style=dict(use_mediawiki_style=True),
                      fonts=dict(default='Sans Serif,10,-1,5,50,0,0,0,0,0'))
    try:
        if load and os.path.exists(appearance_file):
            with open(appearance_file, 'r') as f:
                loaded = json.load(f)
                appearance.update(loaded)
    except:
        show_error(_('Failed to load saved appearance settings'))
    return appearance


def write_layout(layout):
    try:
        with open(layout_file, 'wb') as f:
            f.write(layout)
    except:
        show_error(_('Failed to save layout'))

def read_layout(load=True):
    try:
        if load and os.path.exists(layout_file):
            with open(layout_file, 'rb') as f:
                return f.read()        
    except:
        show_error(_('Failed to load saved layout'))
    return None


def show_error(msg):
    msg_box = QMessageBox()
    msg_box.setWindowTitle(_('Error'))
    msg_box.setIcon(QMessageBox.Warning)
    msg_box.setInformativeText(msg)
    msg_box.setDetailedText(u''.join(traceback.format_exc()))
    msg_box.setStandardButtons(QMessageBox.Close)
    msg_box.exec_()
    
