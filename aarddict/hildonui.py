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

import gtk
import webbrowser

import osso
import hildon

import aarddict
import ui
import articleformat

osso_c = osso.Context(aarddict.__name__, aarddict.__version__, False)

#hack, normal way of determining char width for some reason yields incorrect
#result
oldstrwidth = articleformat.strwidth
articleformat.strwidth = lambda s: (5.0/3)*oldstrwidth(s)

class HildonDictViewer(ui.DictViewer):
            
    def create_top_level_widget(self):
        app = hildon.Program()        
        window = hildon.Window()
        try:
            #This function has been omited twice already during significant 
            #Pymaemo updates - hence try/except
            gtk.set_application_name(aarddict.__appname__)
        except:
            print 'Failed to set application name'
        window.connect("key-press-event", self.on_key_press)
        window.connect("window-state-event", self.on_window_state_change)
        window.connect("event", self.window_event)
        app.add_window(window)
        return window
    
    def update_title(self):
        self.window.set_title(self.create_dict_title())
    
    def on_key_press(self, widget, event, *args):
        if (event.keyval == gtk.keysyms.Escape 
            or (event.state & gtk.gdk.CONTROL_MASK 
                and event.keyval == gtk.keysyms.b)):
            self.history_back()
        elif (event.state & gtk.gdk.CONTROL_MASK 
                and event.keyval == gtk.keysyms.f):
            self.history_forward()
        elif event.keyval == gtk.keysyms.F7:
            self.tabs.prev_page()
        elif event.keyval == gtk.keysyms.F8:
            self.tabs.next_page()        
        elif event.keyval == gtk.keysyms.F6:
            # The "Full screen" hardware key has been pressed
            self.actiongroup.get_action('FullScreen').activate()
    
    def add_menu(self, content_box):        
        main_menu =  gtk.Menu()
        self.window.set_menu(main_menu)                
        for menu in self.create_menus():
            main_menu.append(menu)
        main_menu.show_all()
    
    def create_menus(self):
        mn_nav = gtk.Menu()
        mn_nav_item = gtk.MenuItem("_Navigate")
        mn_nav_item.set_submenu(mn_nav)
        mn_nav.add(self.mi_lookup_box)
        mn_nav.add(self.mi_back)
        mn_nav.add(self.mi_forward)
        mn_nav.add(self.mi_prev_article)
        mn_nav.add(self.mi_next_article)
        mn_nav.add(self.mi_prev_lang)
        mn_nav.add(self.mi_next_lang)
        
        mn_view = gtk.Menu()
        mn_view_item = gtk.MenuItem("_View")
        mn_view_item.set_submenu(mn_view)
        
        mn_view.append(self.mi_select_phonetic_font)
        mn_view.append(self.mi_select_colors)
        mn_view.append(self.mi_increase_text_size)
        mn_view.append(self.mi_decrease_text_size)
        mn_view.append(self.mi_reset_text_size)
        mn_view.append(self.mi_drag_selects)
        mn_view.append(self.mi_show_word_list)
        mn_view.append(self.mi_full_screen)
        
        return (self.mi_open, 
                self.mn_remove_item, 
                self.mi_info, 
                self.mn_copy_item,
                self.mi_paste,
                self.mi_new_lookup,
                mn_nav_item,
                mn_view_item,
                self.mi_about, 
                self.mi_exit)
    
    def create_file_chooser_dlg(self):
        return hildon.FileChooserDialog(self.window, 
                                        gtk.FILE_CHOOSER_ACTION_OPEN);  
    
    def open_external_link(self, url):
        webbrowser.open(url, context = osso_c)
        
#    def supports_cursor_changes(self):
#        return False         
        
