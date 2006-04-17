#!/var/lib/install/usr/bin/python2.4
import pysdic
import sdict
import hildon

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
    
    def get_dialog_parent(self):
        return None    
    
    def add_content(self, content_box):
        self.window.get_appview().add(content_box)            

if __name__ == "__main__":    
    viewer = HildonSDictViewer()
    dict_file = pysdic.read_last_dict()
    if dict_file:
        viewer.open_dict(dict_file)    
    viewer.main()