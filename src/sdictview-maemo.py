#!/usr/bin/env python
"""
This file is part of SDict Viewer (http://sdictviewer.sf.net) - 
a dictionary application that allows to use data bases 
in AXMASoft's open dictionary format. 

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2006-2007 Igor Tkach
"""
import pysdic
import sdict
import hildon
import osso
import gtk

osso_c = osso.Context("sdictviewer", pysdic.version, False)

class HildonSDictViewer(pysdic.SDictViewer):
            
    def create_top_level_widget(self):
        app = hildon.Program()        
        window = hildon.Window()
        gtk.set_application_name(pysdic.app_name)
        self.window_in_fullscreen = False
        window.connect("key-press-event", self.on_key_press)
        window.connect("window-state-event", self.on_window_state_change)
        app.add_window(window)        
        window.connect("destroy", self.destroy)
        return window
    
    def on_window_state_change(self, widget, event, *args):             
         if event.new_window_state & gtk.gdk.WINDOW_STATE_FULLSCREEN:
             self.window_in_fullscreen = True
         else:
             self.window_in_fullscreen = False    
    
    def on_key_press(self, widget, event, *args):
        if event.keyval == gtk.keysyms.F6:
            # The "Full screen" hardware key has been pressed
            if self.window_in_fullscreen:
                self.window.unfullscreen ()
            else:
                self.window.fullscreen ()
        if event.keyval == gtk.keysyms.Escape:
            self.clear_word_input(None, None)
        if event.keyval == gtk.keysyms.F7:
            self.tabs.next_page()            
        if event.keyval == gtk.keysyms.F8:
            self.tabs.prev_page()
                
    
    def add_menu(self, content_box):        
        main_menu =  gtk.Menu()
        self.window.set_menu(main_menu)                
        for menu in self.create_menus():
            main_menu.append(menu)
        main_menu.show_all()
    
    def create_menus(self):           
        return (self.mi_open, self.mn_remove_item, self.mi_info, self.mn_copy_item, self.mi_select_phonetic_font, self.mi_about, self.mi_exit)
    
    
    def create_file_chooser_dlg(self):
        return hildon.FileChooserDialog(self.window, gtk.FILE_CHOOSER_ACTION_OPEN);        
         
        
if __name__ == "__main__":    
    viewer = HildonSDictViewer()
    viewer.main()