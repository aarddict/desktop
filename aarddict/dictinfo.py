"""
This file is part of AardDict (http://code.google.com/p/aarddict) - 
a dictionary for Nokia Internet Tablets. 

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2006-2008 Igor Tkach
"""
import pygtk
pygtk.require('2.0')

import gtk
import pango
import locale
import ui

class DictDetailPane(gtk.HBox):
    
    def __init__(self):
        super(DictDetailPane, self).__init__()
        
        self.text_view = gtk.TextView()
        self.text_view.set_wrap_mode(gtk.WRAP_WORD)
        self.text_view.set_editable(False)        
        self.text_view.set_cursor_visible(False)
        
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

        self.text_view.set_buffer(buffer)        
        
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_shadow_type(gtk.SHADOW_IN)
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add_with_viewport(self.text_view) 
        
        self.pack_start(scrolled_window, True, True, 0)                                                       
    
    def set_dict(self, d):        
        buffer = self.text_view.get_buffer()
                
        if d:
            title_start = 0
            t = '%s %s\n' % (d.title, d.version)
            title_end = title_start + len(t.decode(d.character_encoding))

            file_start = title_end
            t += '(%s)\n' % d.file_name 
            file_end = len(t.decode(d.character_encoding))
            
            count_start = file_end
            article_count = locale.format("%u", d.article_count, True)
            t += '%s articles\n' % article_count 
            count_end = len(t.decode(d.character_encoding))

            if d.copyright:
                t += 'Copyright %s\n' % d.copyright 
            
            t += d.description
                        
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
