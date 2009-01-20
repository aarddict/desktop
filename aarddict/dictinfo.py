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
        
        buffer = gtk.TextBuffer()
        buffer.create_tag("title", 
                          weight = pango.WEIGHT_BOLD, 
                          justification = gtk.JUSTIFY_CENTER,
                          scale = pango.SCALE_LARGE,
                          pixels_above_lines = 3, 
                          pixels_below_lines = 3)        
        
        
        buffer.create_tag("file", 
                          style = pango.STYLE_ITALIC,
                          scale = pango.SCALE_SMALL,
                          justification = gtk.JUSTIFY_CENTER)                

        buffer.create_tag("count", 
                          justification = gtk.JUSTIFY_CENTER,
                          style = pango.STYLE_ITALIC,
                          pixels_below_lines = 3)

        buffer.create_tag("license",
                          wrap_mode = gtk.WRAP_NONE,
                          pixels_below_lines = 3)

        self.text_view.set_buffer(buffer)        
        
        label = gtk.Label('Info')
        self.tabs.append_page(ui.create_scrolled_window(self.text_view), label)        

        self.license_view = create_text_view()

        label = gtk.Label('License')
        self.tabs.append_page(ui.create_scrolled_window(self.license_view), label)        
        self.pack_start(self.tabs, True, True, 0)                                                       
    
    def set_dict(self, d):        
        buffer = self.text_view.get_buffer()
                
        if d:
            title_start = 0
            t = '%s %s\n' % (d.title, d.version)
            title_end = title_start + len(t.decode('utf-8'))

            file_start = title_end
            t += '(%s)\n' % d.file_name 
            file_end = len(t.decode('utf-8'))
            
            count_start = file_end
            article_count = locale.format("%u", d.article_count, True)
            t += '%s articles\n\n' % article_count 
            count_end = len(t.decode('utf-8'))
            
            if d.description:                
                t += '%s\n\n' % d.description

            if d.source:
                t += 'Source: %s\n\n' % d.source
                
            if d.copyright:
                t += '%s\n\n' % d.copyright 
            
            lic_text = d.license if d.license else ''  
            self.license_view.get_buffer().set_text(lic_text)
            
            if not d.license:
                self.tabs.set_current_page(0)
                self.tabs.set_show_tabs(False)
            else:
                self.tabs.set_show_tabs(True)
                        
            buffer.set_text(t)
            start = buffer.get_iter_at_offset(title_start)
            end = buffer.get_iter_at_offset(title_end)
            buffer.apply_tag_by_name('title', start, end)
            
            start = buffer.get_iter_at_offset(file_start)
            end = buffer.get_iter_at_offset(file_end)
            buffer.apply_tag_by_name('file', start, end)            

            start = buffer.get_iter_at_offset(count_start)
            end = buffer.get_iter_at_offset(count_end)
            buffer.apply_tag_by_name('count', start, end)
                                                
        else:
            buffer.set_text('')                
        
class DictInfoDialog(gtk.Dialog):
    def __init__(self, dicts, parent):        
        super(DictInfoDialog, self).__init__(title="Dictionary Info", flags=gtk.DIALOG_MODAL, parent = parent)
        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.add_button(gtk.STOCK_CLOSE, 1)
        self.connect("response", lambda w, resp: w.destroy())
                        
        contentBox = self.get_child()
        box = gtk.VBox(contentBox)        
                
        dict_list = gtk.TreeView(gtk.ListStore(object))
        cell = gtk.CellRendererText()
        dict_column = gtk.TreeViewColumn('Dictionary', cell)
        dict_list.append_column(dict_column)
        dict_column.set_cell_data_func(cell, self.extract_dict_title_for_cell)
                                    
        box.pack_start(ui.create_scrolled_window(dict_list), True, True, 0)

        split_pane = gtk.HPaned()        
        contentBox.pack_start(split_pane, True, True, 2)                        
        split_pane.add(box)
        
        self.detail_pane = DictDetailPane()
        
        split_pane.add(self.detail_pane)
        split_pane.set_position(200)
                            
        self.resize(600, 320)
        
        model = dict_list.get_model()
        
        for dict in dicts:
            model.append([dict])
            
        dict_list.get_selection().connect("changed", self.dict_selected)
        
        if dicts:
            dict_list.get_selection().select_iter(model.get_iter_first())        
        
        self.show_all()
                                        
        
    def extract_dict_title_for_cell(self, column, cell_renderer, model, iter, data = None):
        dict = model[iter][0]
        cell_renderer.set_property('text', dict.title)
        return        
    
    def dict_selected(self, selection):
        dict = None
        if selection.count_selected_rows() > 0:
            model, iter = selection.get_selected()
            dict = model[iter][0]
        self.detail_pane.set_dict(dict)
