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
# Copyright (C) 2006-2009  Igor Tkach

import pygtk
pygtk.require('2.0')

import gtk
import pango
import locale

from collections import defaultdict

import ui

def create_text_view(wrap_mode=gtk.WRAP_NONE):
    text_view = gtk.TextView()
    text_view.set_wrap_mode(wrap_mode)
    text_view.set_editable(False)
    text_view.set_cursor_visible(False)
    return text_view

class DictDetailPane(gtk.HBox):

    def __init__(self):
        super(DictDetailPane, self).__init__()

        self.tabs = gtk.Notebook()
        self.tabs.set_tab_pos(gtk.POS_TOP)
        self.tabs.set_show_border(True)

        self.text_view = create_text_view(gtk.WRAP_WORD)
        self.text_view.set_left_margin(6)

        label = gtk.Label(_('Info'))
        self.tabs.append_page(ui.create_scrolled_window(self.text_view), label)

        self.license_view = create_text_view()

        label = gtk.Label(_('License'))
        self.tabs.append_page(ui.create_scrolled_window(self.license_view), label)
        self.pack_start(self.tabs, True, True, 0)

    def set_dict(self, volumes):

        buff = self.text_view.get_buffer()
        buff.set_text('')

        if volumes:

            volumes = sorted(volumes, key=lambda v: v.volume)
            d = volumes[0]

            def add(text, **attrs):
                if attrs:
                    buff.insert_with_tags(buff.get_end_iter(), text,
                                          buff.create_tag(**attrs))
                else:
                    buff.insert(buff.get_end_iter(), text)

            add('%s %s' % (d.title, d.version),
                weight=pango.WEIGHT_BOLD,
                scale=pango.SCALE_LARGE,
                pixels_above_lines=8)
            add('\n')

            add(_('Volumes: %s') % d.total_volumes,
                weight=pango.WEIGHT_BOLD,
                scale=pango.SCALE_SMALL,
                pixels_below_lines=8)
            add('\n')


            for dictionary in volumes:
                add(_('Volume %s: ') % dictionary.volume,
                    weight=pango.WEIGHT_BOLD,
                    left_margin=20)
                add(dictionary.file_name,
                    style=pango.STYLE_ITALIC,
                    left_margin=20)
                add('\n')

            add(_('Number of articles: '),
                weight=pango.WEIGHT_BOLD,
                pixels_below_lines=8,
                left_margin=20)
            add(locale.format("%u", d.article_count, True),
                style=pango.STYLE_ITALIC,
                pixels_below_lines=8,
                left_margin=20)
            add('\n')

            if d.description:
                add(d.description)
                add('\n')

            if d.source:
                add(_('Source\n'),
                    weight=pango.WEIGHT_BOLD,
                    scale=pango.SCALE_LARGE,
                    pixels_below_lines=4,
                    pixels_above_lines=8)
                add(d.source)
                add('\n')

            if d.copyright:
                add(_('Copyright Notice\n'),
                    weight=pango.WEIGHT_BOLD,
                    scale=pango.SCALE_LARGE,
                    pixels_below_lines=4,
                    pixels_above_lines=8)
                add(d.copyright)
                add('\n')

            lic_text = d.license if d.license else ''
            self.license_view.get_buffer().set_text(lic_text)

            if not d.license:
                self.tabs.set_current_page(0)
                self.tabs.set_show_tabs(False)
            else:
                self.tabs.set_show_tabs(True)


class DictInfoDialog(gtk.Dialog):

    def __init__(self, dicts, parent):
        super(DictInfoDialog, self).__init__(title=_('Dictionary Info'),
                                             flags=gtk.DIALOG_MODAL,
                                             parent = parent)
        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.add_button(gtk.STOCK_CLOSE, 1)
        self.connect('response', lambda w, resp: w.destroy())

        contentBox = self.get_child()
        box = gtk.VBox(contentBox)

        dict_list = gtk.TreeView(gtk.ListStore(object))
        cell = gtk.CellRendererText()
        dict_column = gtk.TreeViewColumn(_('Dictionary'), cell)
        dict_list.append_column(dict_column)

        box.pack_start(ui.create_scrolled_window(dict_list), True, True, 0)

        split_pane = gtk.HPaned()
        contentBox.pack_start(split_pane, True, True, 2)
        split_pane.add(box)

        self.detail_pane = DictDetailPane()

        split_pane.add(self.detail_pane)
        split_pane.set_position(200)

        self.resize(600, 320)

        model = dict_list.get_model()

        dictmap = defaultdict(list)

        for dictionary in dicts:
            dictmap[dictionary.uuid].append(dictionary)

        for uuid in dictmap:
            model.append([uuid])

        dict_list.get_selection().connect('changed', self.dict_selected, dictmap)

        dict_column.set_cell_data_func(cell, self.extract_dict_title_for_cell, dictmap)

        if dicts:
            dict_list.get_selection().select_iter(model.get_iter_first())

        self.show_all()


    def extract_dict_title_for_cell(self, column, cell_renderer, model, iter, dictmap):
        uuid = model[iter][0]
        dicts = dictmap[uuid]
        cell_renderer.set_property('text', dicts[0].title)
        return

    def dict_selected(self, selection, dictmap):
        if selection.count_selected_rows() > 0:
            model, itr = selection.get_selected()
            uuid = model[itr][0]
            volumes = dictmap[uuid]
        else:
            volumes = []
        self.detail_pane.set_dict(volumes)
