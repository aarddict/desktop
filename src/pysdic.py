import pygtk
pygtk.require('2.0')
import gtk
import pango
import sdict
import os.path
import threading
import gobject
import time

gobject.threads_init()

version = "0.1.0"
settings_file_name = ".pysdic"

def read_last_dict():
    home_dir = os.path.expanduser('~')
    settings = os.path.join(home_dir, settings_file_name) 
    if os.path.exists(settings):
        settings_file = file(settings, "r")
        for line in settings_file.readlines():
            prop_name, dict_path = line.split("=")
            return dict_path                
    return None

def write_last_dict(file_name):
    home_dir = os.path.expanduser('~')
    settings = os.path.join(home_dir, settings_file_name) 
    settings_file = file(settings, "w")
    settings_file.writelines(("dictionary=",file_name))    
    
def create_scrolled_window(widget):
    scrolled_window = gtk.ScrolledWindow()
    scrolled_window.set_shadow_type(gtk.SHADOW_IN)
    scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    scrolled_window.add(widget)                                
    return scrolled_window


class DictOpenThread(threading.Thread):
     def __init__(self, file_name, sdict_viewer):
         super(DictOpenThread, self).__init__()
         self.file_name = file_name
         self.sdict_viewer = sdict_viewer

     def set_dict(self, dict):
         self.sdict_viewer.set_dict(dict)
         return False

     def run(self):
         dict = None
         try:
             dict = sdict.SDictionary(self.file_name)
         except Exception, e:
             print e
         gobject.idle_add(self.set_dict, dict)

class SmallToolButton(gtk.ToolButton):
    def __init__(self, icon_widget=None, label=None):
        super(SmallToolButton, self).__init__(icon_widget=None, label=None)

    def __init__(self, stock_id):
        super(SmallToolButton, self).__init__(stock_id)

    def get_icon_size(self):
        print gtk.ToolButton.get_icon_size(self)
        return gtk.ICON_SIZE_SMALL_TOOLBAR

class SDictViewer:
         
    def destroy(self, widget, data=None):
        gtk.main_quit()  
        
    def word_input_callback(self, widget, data = None):
        if not self.dict:
            print "No dictionary opened"
            return        
        word = self.word_input.child.get_text()         
        if not word:
            return     
        #self.schedule_word_lookup(word)
        self.process_word_input(word)
          
    def schedule_word_lookup(self, word):
         self.schedule(self.process_word_input, 200, word)
        
    def schedule(self, f, timeout, *args):
        if self.current_word_handler:
            gobject.source_remove(self.current_word_handler)
            self.current_word_handler = None
        self.current_word_handler = gobject.timeout_add(timeout, f, *args)                
                
    def process_word_input(self, word):
        word = word.strip()
        if not self.show_article_for(word):                        
            model = self.word_completion.get_model()
            first_completion = model.get_iter_first()
            if first_completion:                        
                word = model.get_value(first_completion, 0)
                self.show_article_for(word)        
        
                        
    def word_ref_clicked(self, widget, event, word):
        self.word_input.child.set_text(word)
        self.word_input.child.activate()
                
    def add_to_history(self, word):        
        model = self.word_input.get_model()
        insert = True;
        for row in model:
            if word == row[0]:
                insert = False;
                break;
        if insert:
            model.insert(0, [word])  
        history_size = model.iter_n_children(None)
        if history_size > 10:
            model.remove(model.get_iter(history_size - 1))
                
    def show_article_for(self, word):
        article = self.dict.lookup(word)
        buffer = self.article_view.get_buffer()
        if article:
            text = self.format_article(article)                                        
            text = word + "\n" + text
            buffer.set_text(text)
            word_start = buffer.get_iter_at_offset(0)
            word_end = buffer.get_iter_at_offset(len(word.decode('utf-8')))
            buffer.apply_tag_by_name("b", word_start, word_end) 
            
            regions_to_remove = []
                        
            transcript_regions = self.find_tag_bounds(buffer, "<t>", "</t>", regions_to_remove)
            italic_regions = self.find_tag_bounds(buffer, "<i>", "</i>", regions_to_remove)
            bold_regions = self.find_tag_bounds(buffer, "<b>", "</b>", regions_to_remove)
            underline_regions = self.find_tag_bounds(buffer, "<u>", "</u>", regions_to_remove)
            forms_regions = self.find_tag_bounds(buffer, "<f>", "</f>", regions_to_remove)
            ref_regions = self.find_tag_bounds(buffer, "<r>", "</r>", regions_to_remove)
            
            for mark in regions_to_remove:
                buffer.delete(buffer.get_iter_at_mark(mark[0]), buffer.get_iter_at_mark(mark[1]))            
            
            self.apply_tag_to_regions(buffer, transcript_regions, "t", "[", "]")
            self.apply_tag_to_regions(buffer, italic_regions, "i")
            self.apply_tag_to_regions(buffer, bold_regions, "b")
            self.apply_tag_to_regions(buffer, underline_regions, "u")
            self.apply_tag_to_regions(buffer, forms_regions, "f")
            self.apply_tag_to_regions(buffer, ref_regions, "r")
            for mark in ref_regions:            
                start = buffer.get_iter_at_mark(mark[0])
                end = buffer.get_iter_at_mark(mark[1])
                text = buffer.get_text(start, end)
                start = buffer.get_iter_at_mark(mark[0])
                #start.backward_chars(3)
                anchor = buffer.create_child_anchor(start)
                label = gtk.Label()
                markup_text = "<span foreground='blue' background='white' underline='single' rise='-5'>"+text.replace("&", "&amp;")+"</span>"
                label.set_markup(markup_text)
                btn = gtk.EventBox()
                btn.add(label)                
                ref_text = text.replace("~", word)
                btn.connect('button-release-event', self.word_ref_clicked, ref_text)
                self.article_view.add_child_at_anchor(btn, anchor)
                hand_cursor = gtk.gdk.Cursor(gtk.gdk.HAND2)                
                btn.window.set_cursor(hand_cursor)                
                start = buffer.get_iter_at_mark(mark[0])
                end = buffer.get_iter_at_mark(mark[1])                
                buffer.apply_tag_by_name("invisible", start, end)                
            self.article_view.show_all()
#            for mark in regions_to_remove:
#                buffer.delete(buffer.get_iter_at_mark(mark[0]), buffer.get_iter_at_mark(mark[1]))
                
            self.article_view.scroll_to_iter(buffer.get_start_iter(), 0)
            self.add_to_history(word)            
            return True           
        else:
            buffer.set_text('Word not found')        
            return False
    
    def apply_tag_to_regions(self, buffer, regions, tag_name, surround_text_start = '', surround_text_end = ''):
        for mark in regions:            
            regions_start_iter = buffer.get_iter_at_mark(mark[0]);
            buffer.insert(regions_start_iter, surround_text_start)
            buffer.insert(buffer.get_iter_at_mark(mark[1]), surround_text_end)
            
            tag_start = buffer.get_iter_at_mark(mark[0])            
            tag_end = buffer.get_iter_at_mark(mark[1])
            
            tag_start.backward_chars(len(surround_text_start))
            
            buffer.apply_tag_by_name(tag_name, tag_start, tag_end)
        
    def find_tag_bounds(self, buffer, start_tag, end_tag, regions_to_remove):
        current_iter = buffer.get_start_iter()            
        regions_to_mark = []            
        while True:            
            match_start, match_end = current_iter.forward_search(start_tag, gtk.TEXT_SEARCH_TEXT_ONLY) or (None, None)
            if not match_start:
                break;                
            mark_start_i_tag = buffer.create_mark(None, match_start)
            mark_start_i = buffer.create_mark(None, match_end)            
            match_start, match_end = current_iter.forward_search(end_tag, gtk.TEXT_SEARCH_TEXT_ONLY)
            current_iter = match_end
            if not match_start:
                break;                
            mark_end_i_tag = buffer.create_mark(None, match_end)
            mark_end_i = buffer.create_mark(None, match_start)
                            
            regions_to_mark.append((mark_start_i, mark_end_i))
            regions_to_remove.append((mark_start_i_tag, mark_start_i))
            regions_to_remove.append((mark_end_i, mark_end_i_tag))                                
        return regions_to_mark
        
        
    def format_article(self, article_text):                    
#       article_text = article_text.replace('<t>', '[')
#       article_text = article_text.replace('</t>', ']')        
       article_text = article_text.replace('<br>', '\n')
       article_text = article_text.replace('<p>', '\n\n')
       return article_text        
    
    def word_selected(self, tree_view, start_editing = None, data = None):
        if tree_view.get_selection().count_selected_rows() == 0:
            return
        model, iter = tree_view.get_selection().get_selected()        
        model = tree_view.get_model()
        cursor_path, focus_col = tree_view.get_cursor()        
        if cursor_path:
            if iter:
                selected_path = model.get_path(iter)
            else:
                selected_path = cursor_path
            if cursor_path == selected_path: 
                word, = model.get(model.get_iter(cursor_path), 0)
                #self.show_article_for(word)
                self.schedule_word_lookup(word)
                   
    def delayed_clear_word_input(self, btn, data = None):
        gobject.idle_add(self.clear_word_input, btn, data)
        
    def clear_word_input(self, btn, data = None):
        self.word_input.child.set_text('')
        gobject.idle_add(self.word_input.child.grab_focus)
                        
    def word_input_changed(self, editable, data = None):
        #self.update_completion(editable.get_text())                
        self.schedule(self.update_completion, 600, editable.get_text())        
                
    def update_completion(self, word, n = 20):
        word = word.strip()
        self.word_completion.handler_block(self.cursor_changed_handler_id)
        model = self.word_completion.get_model()        
        self.word_completion.set_model(None)        
        model.clear()
        if self.dict:
            word_list = self.dict.get_word_list(word, n)
            for word in word_list:
                model.append([word])     
            if len(word_list) == 1:
                self.word_input.child.set_text(word_list[0])
                self.word_input.child.set_position(-1)
                self.word_input.child.activate()
        self.word_completion.set_model(model)
        self.word_completion.handler_unblock(self.cursor_changed_handler_id)
        
        
    def __init__(self):
        self.dict = None
        self.fileChooser = None
        self.current_word_handler = None                               
        self.window = self.create_top_level_widget()                               
        self.font = None
                                 
        contentBox = gtk.VBox(False, 0)
        self.add_menu(contentBox)
                                        
        box = gtk.VBox()        
        
        self.word_input = self.create_word_input()
        
        input_box = gtk.HBox()
        input_box.pack_start(self.word_input, True, True, 0)
        clear_input = gtk.ToolButton(gtk.STOCK_CLEAR)        
        clear_input.connect("clicked", self.delayed_clear_word_input);
        input_box.pack_start(clear_input, False, False, 2)
        
        box.pack_start(input_box, False, False, 4)
        
        self.word_completion = self.create_word_completion()
        box.pack_start(create_scrolled_window(self.word_completion), True, True, 0)

        split_pane = gtk.HPaned()        
        contentBox.pack_start(split_pane, True, True, 2)                        
        split_pane.add(box)
        
        self.article_view = self.create_article_view()        
        split_pane.add(create_scrolled_window(self.article_view))
                        
        self.add_content(contentBox)
        self.update_title()
        self.window.show_all()

    def create_top_level_widget(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)    
        window.connect("destroy", self.destroy)
        window.set_border_width(2)                
        window.resize(600, 400)
        window.set_position(gtk.WIN_POS_CENTER)        
        return window
    
    def add_content(self, content_box):
        self.window.add(content_box)        
    
    def add_menu(self, content_box):
        menu_bar = gtk.MenuBar()
        menu_bar.set_border_width(1)                        
        for menu in self.create_menus():
            menu_bar.append(menu)     
        content_box.pack_start(menu_bar, False, False, 2)           

    def create_word_completion(self):
        word_completion = gtk.TreeView(gtk.ListStore(str))        
        word_completion.set_headers_visible(False)
        self.cursor_changed_handler_id = word_completion.connect("cursor-changed", self.word_selected)
        word_completion.connect("row-activated", self.word_selected)        
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn("", renderer, text=0)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        word_completion.append_column(column)            
        word_completion.set_fixed_height_mode(True)
        return word_completion

    def create_word_input(self):
        word_input = gtk.combo_box_entry_new_text()
        word_input.child.connect("activate", self.word_input_callback)
        word_input.child.connect("changed", self.word_input_changed)                        
        word_input.connect("changed", self.word_selected_in_history)
        return word_input
    
    def word_selected_in_history(self, widget, data = None):        
         model = widget.get_model()
         iter = widget.get_active_iter()
         if iter:
             self.word_input.child.activate()

    def create_menus(self):        
        mi_open = gtk.MenuItem("Open...")
        mi_open.connect("activate", self.select_dict_file)
        mi_info = gtk.MenuItem("Info...")
        mi_info.connect("activate", self.show_dict_info)
        mi_exit = gtk.MenuItem("Exit")
        mi_exit.connect("activate", self.destroy)
        
        mn_dict = gtk.Menu()
        mn_dict_item = gtk.MenuItem("Dictionary")
        mn_dict_item.set_submenu(mn_dict)        
        
        mn_dict.append(mi_open)        
        mn_dict.append(mi_info)
        mn_dict.append(mi_exit)

        mi_about = gtk.MenuItem("About")        
        mi_about.connect("activate", self.show_about)
        
        mn_help = gtk.Menu()
        mn_help_item = gtk.MenuItem("Help")
        mn_help_item.set_submenu(mn_help)
        
        mn_help.append(mi_about)
        
        mn_dict.show_all()
        mn_help_item.show_all()
        
        mn_options = gtk.Menu()
        mn_options_item = gtk.MenuItem("Options")
        mn_options_item.set_submenu(mn_options)
        
        mi_select_font = gtk.MenuItem("Font...")
        mi_select_font.connect("activate", self.show_font_select_dlg)
        mn_options.append(mi_select_font)
        mn_options.show_all()
        return (mn_dict_item, mn_options_item, mn_help_item)        

    def get_dialog_parent(self):
        return self.window

    def update_title(self):
        if self.dict:        
            dict_title = self.dict.title
        else:
            dict_title = "No dictionary"
        title = "SDict Viewer - %s" % dict_title        
        self.window.set_title(title)

    def create_article_view(self):
        article_view = gtk.TextView()
        article_view.set_wrap_mode(gtk.WRAP_WORD)
        article_view.set_editable(False)        
        article_view.set_cursor_visible(False)
        buffer = article_view.get_buffer()
        buffer.create_tag("b", weight = pango.WEIGHT_BOLD)
        buffer.create_tag("i", style = pango.STYLE_ITALIC)
        buffer.create_tag("u", underline = True)
        buffer.create_tag("f", style = pango.STYLE_ITALIC, foreground = "green")
        buffer.create_tag("r", underline = True, foreground = "blue", rise = -10, rise_set = True)
        buffer.create_tag("t", weight = pango.WEIGHT_BOLD, foreground = "darkred")
        buffer.create_tag("invisible", invisible = True)
        return article_view

    def select_dict_file(self, widget):
        if not self.fileChooser:
            self.fileChooser = gtk.FileSelection("Select Dictionary")
            if self.dict:
                self.fileChooser.set_filename(self.dict.file_name)
            self.fileChooser.ok_button.connect("clicked", self.file_selected)
            self.fileChooser.cancel_button.connect("clicked", lambda w: self.fileChooser.hide())
        self.fileChooser.show()
    
    def file_selected(self, widget):
        fileName = self.fileChooser.get_filename()
        try:
            self.open_dict(fileName)
        except Exception, ex:
            print "Failed to open dictionary in file", fileName, "\n", ex
        else:
            self.fileChooser.hide()

    def open_dict(self, file):
        self.loading_dialog = gtk.Dialog(title="Loading", parent=self.get_dialog_parent(), flags=gtk.DIALOG_MODAL)
        self.loading_dialog.set_decorated(False)
        self.loading_dialog.set_modal(True)
        self.loading_dialog.set_has_separator(False)
        self.loading_dialog.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("lightgrey"))
        
        label = gtk.Label("Loading "+file)
        self.loading_dialog.vbox.pack_start(label, True, True, 0)
        label.show()
        
        t = DictOpenThread(file, self)
        t.start()
        self.loading_dialog.show()
        
    def set_dict(self, dict):     
        if self.loading_dialog:
            self.loading_dialog.destroy()
            self.loading_dialog = None
        if self.dict:
            self.dict.close() 
            self.word_completion.get_model().clear()
            self.article_view.get_buffer().set_text('')
            self.dict = None
        self.dict = dict        
        try:
            write_last_dict(self.dict.file_name)            
        except Exception, ex:
            print 'Failed to store settings:', ex
        self.update_title()

    def show_dict_info(self, widget):
        dialog = gtk.AboutDialog()
        dialog.set_position(gtk.WIN_POS_CENTER)
        dialog.set_name(self.dict.title)
        dialog.set_version(self.dict.version)
        dialog.set_copyright(self.dict.copyright)
        comments = "Contains %d words, packed with %s\nRead from %s" % (self.dict.header.num_of_words, self.dict.compression, self.dict.file_name)        
        dialog.set_comments(comments)        
        dialog.show()
        
    def show_about(self, widget):
        dialog = gtk.AboutDialog()
        dialog.set_position(gtk.WIN_POS_CENTER)
        dialog.set_name("SDict Viewer")
        dialog.set_version(version)
        dialog.set_copyright("Igor Tkach")
        dialog.set_website("http://sf.net/projects/sdictviewer")
        comments = "SDict Viewer is viewer for dictionaries in open format described at http://sdict.com\nDistributed under terms and conditions of GNU Public License\nSee http://www.gnu.org/licenses/gpl.txt for details"
        dialog.set_comments(comments)        
        dialog.show()     
        
    def show_font_select_dlg(self, widget):
        dialog = gtk.FontSelectionDialog("Select Article Font")
        dialog.set_position(gtk.WIN_POS_CENTER)
        dialog.ok_button.connect("clicked",
                                     self.font_selection_ok, dialog)
        dialog.cancel_button.connect_object("clicked",
                                                lambda wid: wid.destroy(),
                                                dialog)        
        if self.font:
            dialog.set_font_name(self.font)
        dialog.show()
        
    def font_selection_ok(self, button, dialog):
        self.font = dialog.get_font_name()                    
        print "font name %s" % dialog.get_font_name()
        font_desc = pango.FontDescription(self.font)
        if font_desc: 
            #self.article_view.modify_font(font_desc)
            text_buffer = self.article_view.get_buffer()
            tag_table = text_buffer.get_tag_table()
            tag_table.lookup("t").set_property("font-desc", font_desc)
        dialog.destroy()
        
    def main(self):
        gtk.main()            