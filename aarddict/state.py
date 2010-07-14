from __future__ import with_statement

import logging
import os
import gzip

try:
    import json
except ImportError:
    import simplejson as json

from PyQt4.QtCore import QRect
from PyQt4.QtGui import QApplication

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
    with open(sources_file, 'w') as f:
        json.dump(nodupe_sources, f, indent=2)
    return nodupe_sources

def read_sources():
    if os.path.exists(sources_file):
        with open(sources_file) as f:
            return json.load(f)
    return []


def write_state(state):
    f = gzip.open(state_file, 'wb')
    try:
        json.dump(state, f, indent=2)
    finally:
        f.close()

def read_state():
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
    if os.path.exists(state_file):
        try:
            f = gzip.open(state_file, 'rb')
            loaded = json.load(f)
        except:
            log.exception('Failed to load state')
        else:
            state.update(loaded)
    return state


def write_appearance(appearance):
    with open(appearance_file, 'w') as f:
        json.dump(appearance, f, indent=2)

def read_appearance():
    appearance = dict(colors=dict(active_link_bg='#e0e8e8',
                                  footnote_fg='#00557f',
                                  internal_link_fg='maroon',
                                  external_link_fg='#0000cc',
                                  footnote_backref_fg='#00557f',
                                  table_bg=''),
                      style=dict(use_mediawiki_style=True),
                      fonts=dict(default='Sans Serif,10,-1,5,50,0,0,0,0,0'))
    if os.path.exists(appearance_file):
        with open(appearance_file, 'r') as f:
            loaded = json.load(f)
            appearance.update(loaded)
    return appearance


def write_layout(layout):
    with open(layout_file, 'wb') as f:
        f.write(layout)

def read_layout():
    if os.path.exists(layout_file):
        with open(layout_file, 'rb') as f:
            return f.read()
    return None


