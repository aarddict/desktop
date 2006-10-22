import pygtk
pygtk.require('2.0')
import gtk
import pango
import sdict
import os.path
import threading
import gobject
import time
import pickle
import string

gobject.threads_init()

version = "0.2.2"
settings_file_name = ".sdictviewer"

def save_app_state(app_state):
    home_dir = os.path.expanduser('~')
    settings = os.path.join(home_dir, settings_file_name) 
    settings_file = file(settings, "w")    
    pickle.dump(app_state, settings_file)
    
def load_app_state():
    home_dir = os.path.expanduser('~')
    settings = os.path.join(home_dir, settings_file_name) 
    if os.path.exists(settings):        
        settings_file = file(settings, "r")
        app_state = pickle.load(settings_file)
        return app_state
    return None    
    
def create_scrolled_window(widget):
    scrolled_window = gtk.ScrolledWindow()
    scrolled_window.set_shadow_type(gtk.SHADOW_IN)
    scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    scrolled_window.add(widget)                                
    return scrolled_window

class State:    
    def __init__(self, dict_file = None, phonetic_font = None, word = None, history = [], recent = []):
        self.dict_file = dict_file
        self.phonetic_font = phonetic_font
        self.word = word
        self.history = history
        self.recent = recent
     
class BackgroundWorker(threading.Thread):
    def __init__(self, task, status_display, callback):
        super(BackgroundWorker, self).__init__()
        self.callback = callback
        self.status_display = status_display
        self.task = task
            
    def run(self):
        gobject.idle_add(self.status_display.show_start)
        result = None
        error = None
        try:
            result = self.task()
        except Exception, ex:
            print "Failed to execute task: ", ex
            error = ex
        gobject.idle_add(self.callback, result, error)
        gobject.idle_add(self.status_display.show_end)
        
class DialogStatusDisplay:
    
    def __init__(self, title, message, parent):
        self.loading_dialog = None
        self.message = message
        self.parent = parent
        self.title = title
        
    def show_start(self):        
        self.loading_dialog = gtk.MessageDialog(parent=self.parent, flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_INFO, message_format=self.message)        
        self.loading_dialog.set_title(self.title)
        self.loading_dialog.run()        
        
    def show_end(self):    
        if self.loading_dialog:
            self.loading_dialog.destroy()
            self.loading_dialog = None        

class ArticleFormat: 
    
    def __init__(self):
        self.template = string.Template("$word\n$text")
       
    def apply(self, word, article, article_view, word_ref_callback):
        buffer = article_view.get_buffer()
        text = self.convert_newlines(article)                                        
        text = self.convert_paragraphs(text)
        text = self.template.substitute(text = text, word = word)
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
        
        [buffer.delete(buffer.get_iter_at_mark(mark[0]), buffer.get_iter_at_mark(mark[1])) for mark in regions_to_remove]
        [self.apply_tag(mark, buffer, "t", "[", "]") for mark in transcript_regions]
        [self.apply_tag(mark, buffer, "i") for mark in italic_regions]
        [self.apply_tag(mark, buffer, "b") for mark in bold_regions]
        [self.apply_tag(mark, buffer, "u") for mark in underline_regions]
        [self.apply_tag(mark, buffer, "f") for mark in forms_regions]
        [self.apply_tag(mark, buffer, "r") for mark in ref_regions]
        [self.create_ref(mark, buffer, word, word_ref_callback, article_view) for mark in ref_regions]
            
            
    def create_ref(self, mark, buffer, word, word_ref_callback, article_view):
        start = buffer.get_iter_at_mark(mark[0])
        end = buffer.get_iter_at_mark(mark[1])
        text = buffer.get_text(start, end)
        start = buffer.get_iter_at_mark(mark[0])
        anchor = buffer.create_child_anchor(start)
        label = gtk.Label()
        markup_text = "<span foreground='blue' background='white' underline='single' rise='-5'>"+text.replace("&", "&amp;")+"</span>"
        label.set_markup(markup_text)
        btn = gtk.EventBox()
        btn.add(label)                
        ref_text = text.replace("~", word)
        btn.connect('button-release-event', word_ref_callback, ref_text)
        article_view.add_child_at_anchor(btn, anchor)
        hand_cursor = gtk.gdk.Cursor(gtk.gdk.HAND2)                
        btn.window.set_cursor(hand_cursor)                
        start = buffer.get_iter_at_mark(mark[0])
        end = buffer.get_iter_at_mark(mark[1])                
        buffer.apply_tag_by_name("invisible", start, end)                   
            
            
    def apply_tag(self, mark, buffer, tag_name, surround_text_start = '', surround_text_end = ''):
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
        
        
    def convert_newlines(self, article_text):                    
       return article_text.replace('<br>', '\n')

    def convert_paragraphs(self, article_text):                    
       return article_text.replace('<p>', '\n\t')

class SDictViewer:
             
    def destroy(self, widget, data=None):
        try:
            word = self.word_input.child.get_text()
            history_list = []
            hist_model = self.word_input.get_model()
            hist_model.foreach(self.history_to_list, history_list)
            save_app_state(State(self.dict.file_name, self.font, word, history_list, self.recent_menu_items.keys()))
        except Exception, ex:
            print 'Failed to store settings:', ex        
        gtk.main_quit()  
        
    def history_to_list(self, model, path, iter, history_list):
        history_list.append(model.get_value(iter, 0))
        
    def word_input_callback(self, widget, data = None):
        if not self.dict:
            print "No dictionary opened"
            return        
        word = self.word_input.child.get_text()         
        self.process_word_input(word)
          
    def schedule_word_lookup(self, word):
         self.schedule(self.process_word_input, 200, word)
        
    def schedule(self, f, timeout, *args):
        if self.current_word_handler:
            gobject.source_remove(self.current_word_handler)
            self.current_word_handler = None
        self.current_word_handler = gobject.timeout_add(timeout, f, *args)                
                
    def process_word_input(self, word):
        if not word or word == '':
            return
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
            self.article_format.apply(word, article, self.article_view, self.word_ref_clicked)
            self.article_view.show_all()
            self.article_view.scroll_to_iter(buffer.get_start_iter(), 0)
            self.add_to_history(word)            
            return True           
        else:
            buffer.set_text('Word not found')        
            return False    
    
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
            [model.append([word]) for word in word_list]
            if len(word_list) == 1:
                self.word_input.child.set_text(word_list[0])
                self.word_input.child.set_position(-1)
                self.word_input.child.activate()
        self.word_completion.set_model(model)
        self.word_completion.handler_unblock(self.cursor_changed_handler_id)
        
        
    def __init__(self):
        self.dict = None
        self.current_word_handler = None                               
        self.window = self.create_top_level_widget()                               
        self.font = None
        self.article_format = ArticleFormat()
        self.recent_menu_items = {}
                                 
        contentBox = gtk.VBox(False, 0)
        self.add_menu(contentBox)
                                        
        box = gtk.VBox()        
        
        self.word_input = self.create_word_input()
        
        input_box = gtk.HBox()
        input_box.pack_start(self.word_input, True, True, 0)
        clear_input = self.create_clear_button()
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
        
        try:
            app_state = load_app_state()     
            if app_state:   
                self.open_dict(app_state.dict_file)
                self.word_input.child.set_text(app_state.word)                
                app_state.history.reverse()
                [self.add_to_history(w) for w in app_state.history]
                self.set_phonetic_font(app_state.phonetic_font)
                [self.add_to_recent(r[0], r[1], r[2]) for r in app_state.recent]
        except Exception, ex:
            print 'Failed to load application state:', ex        

    def create_clear_button(self):
        clear_input = gtk.Button(stock = gtk.STOCK_CLEAR)
        settings = clear_input.get_settings()
        settings.set_property( "gtk-button-images", True )        
        clear_input.set_label('')
        clear_input.set_image(gtk.image_new_from_stock(gtk.STOCK_CLEAR, gtk.ICON_SIZE_SMALL_TOOLBAR))
        clear_input.set_relief(gtk.RELIEF_NONE)
        clear_input.set_focus_on_click(False)
        clear_input.connect("clicked", self.clear_word_input);
        return clear_input        
   
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
        [menu_bar.append(menu) for menu in self.create_menus()]
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
        
        self.mn_recent = gtk.Menu()
        mn_recent_item = gtk.MenuItem("Recent")
        mn_recent_item.set_submenu(self.mn_recent)                        
        
        mn_dict = gtk.Menu()
        mn_dict_item = gtk.MenuItem("Dictionary")
        mn_dict_item.set_submenu(mn_dict)        
        
        mn_dict.append(mi_open)        
        mn_dict.append(mi_info)
        mn_dict.append(mn_recent_item)
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
        
        mi_select_phonetic_font = gtk.MenuItem("Phonetic Font...")
        mi_select_phonetic_font.connect("activate", self.select_phonetic_font)
        mn_options.append(mi_select_phonetic_font)
        mn_options.show_all()
        return (mn_dict_item, mn_options_item, mn_help_item)        

    def add_dict_to_recent(self, dict):
        self.add_to_recent(dict.title, dict.version, dict.file_name)
            
    def add_to_recent(self, title, version, file_name):
        mi_dict = gtk.MenuItem("%s %s" % (title, version))                 
        key = (title, version, file_name)
        if self.recent_menu_items.has_key(key):
            old_mi = self.recent_menu_items[key]
            self.mn_recent.remove(old_mi)
            del self.recent_menu_items[key]
        self.recent_menu_items[key] = mi_dict;        
        self.mn_recent.prepend(mi_dict)
        mi_dict.connect("activate", lambda f: self.open_dict(file_name))
        children = self.mn_recent.get_children()        
        child_count = len(children)
        if child_count > 4:
            self.mn_recent.remove(children[child_count-1])
        mi_dict.show_all()

    def get_dialog_parent(self):
        return self.window

    def update_title(self):
        if self.dict:        
            dict_title = self.dict.title
        else:
            dict_title = "No dictionary"
        title = "%s - SDict Viewer" % dict_title        
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
        fileChooser = self.create_file_chooser_dlg()
        fileChooser.set_title("Open Dictionary")
        if fileChooser.run() == gtk.RESPONSE_OK:
            fileName = fileChooser.get_filename()
            self.open_dict(fileName)
        fileChooser.destroy()        
        
    def create_file_chooser_dlg(self):
        dlg = gtk.FileChooserDialog(parent = self.window, action = gtk.FILE_CHOOSER_ACTION_OPEN)        
        dlg.add_button( gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        dlg.add_button( gtk.STOCK_OPEN, gtk.RESPONSE_OK)        
        if self.dict:
            dlg.set_filename(self.dict.file_name)        
        return dlg
    
    def open_dict(self, file):
        status_display = self.create_dict_loading_status_display(file)
        worker = BackgroundWorker(lambda : sdict.SDictionary(file), status_display, self.set_dict_callback)
        worker.start()
        
    def create_dict_loading_status_display(self, dict_name):            
        return DialogStatusDisplay("Loading...", dict_name, self.get_dialog_parent())
    
    def set_dict_callback(self, dict, error):
        if not error:
            self.set_dict(dict)
        else:
            print "Failed to open dictionary: ", error
            try: 
                raise error
            except IOError:
                self.show_error("Dictionary Open Failed", "%s: %s" % (error.strerror, error.filename))
            except sdict.DictFormatError:
                self.show_error("Dictionary Open Failed", error.value)
    
    def show_error(self, title, text):
        dlg = gtk.MessageDialog(parent=self.window, flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_CLOSE, message_format=text)
        dlg.set_title(title)
        dlg.run()
        dlg.destroy()
    
    def set_dict(self, dict):     
        if self.dict:
            self.dict.close() 
            self.word_completion.get_model().clear()
            self.article_view.get_buffer().set_text('')
            self.dict = None
        self.dict = dict   
        self.update_completion(self.word_input.child.get_text())
        self.process_word_input(self.word_input.child.get_text())
        self.update_title()
        self.add_dict_to_recent(self.dict)

    def show_dict_info(self, widget):
        dialog = gtk.AboutDialog()
        dialog.set_position(gtk.WIN_POS_CENTER)
        dialog.set_name(self.dict.title)
        dialog.set_version(self.dict.version)
        dialog.set_copyright(self.dict.copyright)
        comments = "Contains %d words, packed with %s\nRead from %s" % (self.dict.header.num_of_words, self.dict.compression, self.dict.file_name)        
        dialog.set_comments(comments)        
        dialog.run()
        dialog.destroy()
        
    def show_about(self, widget):
        dialog = gtk.AboutDialog()
        dialog.set_position(gtk.WIN_POS_CENTER)
        dialog.set_name("SDict Viewer")
        dialog.set_version(version)
        dialog.set_copyright("Igor Tkach")
        dialog.set_website("http://sdictviewer.sf.net/")
        comments = "SDict Viewer is viewer for dictionaries in open format described at http://sdict.com\nDistributed under terms and conditions of GNU Public License\nSee http://www.gnu.org/licenses/gpl.txt for details"
        dialog.set_comments(comments)        
        dialog.run()     
        dialog.destroy()
        
    def select_phonetic_font(self, widget):
        dialog = gtk.FontSelectionDialog("Select Phonetic Font")        
        if self.font:
            dialog.set_font_name(self.font)                        
        if dialog.run() == gtk.RESPONSE_OK:
            self.set_phonetic_font(dialog.get_font_name())
        dialog.destroy()
                
    def set_phonetic_font(self, font_name):
        self.font = font_name                    
        font_desc = pango.FontDescription(self.font)
        if font_desc: 
            text_buffer = self.article_view.get_buffer()
            tag_table = text_buffer.get_tag_table()
            tag_table.lookup("t").set_property("font-desc", font_desc)
        
    def main(self):
        gtk.main()            