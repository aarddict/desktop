#!/usr/bin/env python2.4
import pysdic
import sdict
import hildon
import osso
import gtk

osso_c = osso.Context("sdictviewer", pysdic.version, False)

class HildonStatusDisplay:
    def __init__(self, message, parent):
        self.message = message
        self.parent = parent        

    def show_start(self):
        osso_c.system_note_infoprint(self.message)
        #self.dialog = hildon.Note ("cancel_with_progress_bar", (self.parent, self.message, gtk.STOCK_DIALOG_INFO) )
        #self.dialog.set_button_text("Cancel")        
        #response = self.dialog.run()        
        #dialog.destroy()
        #if not response == gtk.RESPONSE_OK:
        #    print 'Cancel is not implemented'
        
    def show_end(self):
        #self.dialog.destroy()
        print ''

class HildonSDictViewer(pysdic.SDictViewer):
        
    def create_top_level_widget(self):
        app = hildon.Program()        
        window = hildon.Window()
        #window.set_title("SDict Viewer")
        app.add_window(window)        
        window.connect("destroy", self.destroy)
        return window
    
    def add_menu(self, content_box):        
        main_menu =  gtk.Menu()
        self.window.set_menu(main_menu)                
        for menu in self.create_menus():
            main_menu.append(menu)
            menu.show()     
    
    def create_dict_loading_status_display(self, dict_name):
        return HildonStatusDisplay("Loading " + dict_name, self.get_dialog_parent())
    
#    def get_dialog_parent(self):
#        return None    
    
#    def add_content(self, content_box):
#        self.window.add(content_box)            

if __name__ == "__main__":    
    viewer = HildonSDictViewer()
    viewer.main()