#!/usr/bin/env python2.4
import pysdic
import sdict
import hildon
import osso

osso_c = osso.Context("sdictviewer", pysdic.version, False)

class HildonStatusDisplay:
    def __init__(self, message, parent):
        self.message = message
        self.parent = parent        

    def show_start(self):
        osso_c.system_note_infoprint(self.message)
        
    def show_end(self):
        print ''

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
    
    def create_dict_loading_status_display(self, dict_name):
        return HildonStatusDisplay("Loading " + dict_name, self.get_dialog_parent())
    
    def get_dialog_parent(self):
        return None    
    
    def add_content(self, content_box):
        self.window.get_appview().add(content_box)            

if __name__ == "__main__":    
    viewer = HildonSDictViewer()
    viewer.main()