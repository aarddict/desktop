#!/usr/bin/env python
import pysdic
import sdict
import hildon
import gtk

class HildonStatusDisplay:
    def __init__(self, message, parent):
        self.message = message
        self.parent = parent
        self.dialog = None
    
    def show_start(self):
        self.dialog = hildon.Note ("information", (self.parent, self.message, gtk.STOCK_DIALOG_INFO) )
        self.dialog.show_all()
        
    def show_end(self):
        self.dialog.destroy()

class HildonSDictViewer(pysdic.SDictViewer):
    
    def create_top_level_widget(self):
        app = hildon.App()
        appview = hildon.AppView("SDict Viewer")
        appview.set_fullscreen_key_allowed(True)        
        app.set_two_part_title(True)
        app.set_appview(appview)
        appview.connect("destroy", self.destroy)
        return app
    
    def add_menu(self, content_box):        
        main_menu = self.window.get_appview().get_menu()                
        for menu in self.create_menus():
            main_menu.append(menu)
            menu.show()     
    
#    def create_dict_loading_status_display(self, dict_name):
#        return HildonStatusDisplay("Loading " + dict_name, self.get_dialog_parent())    
    
    def get_dialog_parent(self):
        return None    
    
    def add_content(self, content_box):
        self.window.get_appview().add(content_box)            

if __name__ == "__main__":    
    viewer = HildonSDictViewer()
    viewer.main()