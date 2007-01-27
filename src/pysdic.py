"""
This file is part of SDict Viewer (http://sdictviewer.sf.net) - dictionary that uses 
data bases in AXMASoft's open dictionary format. SDict Viewer is distributed under terms 
and conditions of GNU General Public License Version 2. See http://www.gnu.org/licenses/gpl.html
for license details.
Copyright (C) 2006-2007 Igor Tkach
"""
import pygtk
pygtk.require('2.0')
import gtk
import pango
import sdict
import dict_info_ui
import ui_util
import os.path
import gobject
import pickle
import string
import locale

gobject.threads_init()

version = "0.3.0"
settings_file_name = ".sdictviewer"
app_name = "SDict Viewer"

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
    
class State:    
    def __init__(self, dict_file = None, phonetic_font = None, word = None, history = [], recent = [], dict_files = [], last_dict_file_location = None):
        self.dict_file = dict_file
        self.phonetic_font = phonetic_font
        self.word = word
        self.history = history
        self.recent = recent
        self.dict_files = dict_files
        self.last_dict_file_location = last_dict_file_location
             
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
        sup_regions = self.find_tag_bounds(buffer, "<sup>", "</sup>", regions_to_remove)
        sub_regions = self.find_tag_bounds(buffer, "<sub>", "</sub>", regions_to_remove)
        
        [buffer.delete(buffer.get_iter_at_mark(mark[0]), buffer.get_iter_at_mark(mark[1])) for mark in regions_to_remove]
        [self.apply_tag(mark, buffer, "t", "[", "]") for mark in transcript_regions]
        [self.apply_tag(mark, buffer, "i") for mark in italic_regions]
        [self.apply_tag(mark, buffer, "b") for mark in bold_regions]
        [self.apply_tag(mark, buffer, "u") for mark in underline_regions]
        [self.apply_tag(mark, buffer, "f") for mark in forms_regions]
        [self.apply_tag(mark, buffer, "r") for mark in ref_regions]
        [self.create_ref(mark, buffer, word, word_ref_callback, article_view) for mark in ref_regions]                            
        [self.apply_tag(mark, buffer, "sup") for mark in sup_regions]
        [self.apply_tag(mark, buffer, "sub") for mark in sub_regions]
        
    def create_ref(self, mark, buffer, word, word_ref_callback, article_view):
        start = buffer.get_iter_at_mark(mark[0])
        end = buffer.get_iter_at_mark(mark[1])
        text = buffer.get_text(start, end)
        ref_text = text.replace("~", word)
        ref_tag = buffer.create_tag()
        ref_tag.connect("event", word_ref_callback, ref_text)
        buffer.apply_tag(ref_tag, start, end)        
                    
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
            f_search_result = current_iter.forward_search(end_tag, gtk.TEXT_SEARCH_TEXT_ONLY)
            try:
                match_start, match_end = f_search_result
            except TypeError:
                print 'Formatting error: possible missing start or end tag for tag pair %s%s' % (start_tag, end_tag)
                match_start = f_search_result
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
             
    def __init__(self):
        self.dictionaries = sdict.SDictionaryCollection()
        self.current_word_handler = None                               
        self.window = self.create_top_level_widget()                               
        self.font = None
        self.last_dict_file_location = None
        self.article_format = ArticleFormat()
        self.recent_menu_items = {}
        self.dict_key_to_tab = {}
                                 
        contentBox = gtk.VBox(False, 0)
        self.create_menu_items()
        self.add_menu(contentBox)
                                        
        box = gtk.VBox()        
        
        self.word_input = self.create_word_input()
        
        input_box = gtk.HBox()
        input_box.pack_start(self.word_input, True, True, 0)
        clear_input = self.create_clear_button()
        input_box.pack_start(clear_input, False, False, 2)
        
        box.pack_start(input_box, False, False, 4)
        
        self.word_completion = self.create_word_completion()
        box.pack_start(ui_util.create_scrolled_window(self.word_completion), True, True, 0)

        split_pane = gtk.HPaned()        
        contentBox.pack_start(split_pane, True, True, 2)                        
        split_pane.add(box)
        
        self.tabs = gtk.Notebook()
        self.tabs.set_scrollable(True)
        split_pane.add(self.tabs)
                        
        self.add_content(contentBox)
        self.update_title()
        self.window.show_all()
        
        try:
            app_state = load_app_state()     
            if app_state:   
                #self.open_dict(app_state.dict_file)
                self.open_dicts(app_state.dict_files)
                self.word_input.child.set_text(app_state.word)                
                app_state.history.reverse()
                [self.add_to_history(w) for w in app_state.history]
                self.set_phonetic_font(app_state.phonetic_font)
                self.last_dict_file_location = app_state.last_dict_file_location
                #[self.add_to_recent(r[0], r[1], r[2]) for r in app_state.recent]
        except Exception, ex:
            print 'Failed to load application state:', ex                     
             
    def destroy(self, widget, data=None):
        try:
            word = self.word_input.child.get_text()
            history_list = []
            hist_model = self.word_input.get_model()
            hist_model.foreach(self.history_to_list, history_list)
            dict_files = [dict.file_name for dict in self.dictionaries.get_dicts()] 
            save_app_state(State(None, self.font, word, history_list, self.recent_menu_items.keys(), dict_files, self.last_dict_file_location))
        except Exception, ex:
            print 'Failed to store settings:', ex        
        gtk.main_quit()  
        
    def history_to_list(self, model, path, iter, history_list):
        history_list.append(model.get_value(iter, 0))
        
    def word_input_callback(self, widget, data = None):        
        if self.dictionaries.is_empty():
            print "No dictionaries opened"
            return        
        word = self.word_input.child.get_text()         
        self.process_word_input(word)
          
    def schedule_word_lookup(self, word, lang):
         self.schedule(self.process_word_input, 200, word, lang)
        
    def schedule(self, f, timeout, *args):
        if self.current_word_handler:
            gobject.source_remove(self.current_word_handler)
            self.current_word_handler = None
        self.current_word_handler = gobject.timeout_add(timeout, f, *args)                
                
    def process_word_input(self, word, lang = None):
        print 'process word input: ', word, ' ' , lang
        if not word or word == '':
            return
        word = word.strip()
        if not self.show_article_for(word, lang):                        
            model = self.word_completion.get_model()
            first_completion = model.get_iter_first()
            if first_completion:                        
                word = model[first_completion][0]
                self.show_article_for(word)        
        
                        
    def word_ref_clicked(self, tag, widget, event, iter, word):
        if event.type == gtk.gdk.BUTTON_RELEASE:
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
            del model[history_size - 1]
                
    def clear_tabs(self):
        while self.tabs.get_n_pages() > 0:
            self.tabs.remove_page(-1)        
        self.dict_key_to_tab.clear()       
        return False 
    
    def show_article_for(self, word, lang = None):
        articles = self.dictionaries.lookup(word, (lang))
        self.clear_tabs()
        result = False
        for dict, article in articles:        
            if article: 
                article_view = self.create_article_view()
                scrollable_view = ui_util.create_scrolled_window(article_view)                
                label = gtk.Label(dict.title)
                label.set_width_chars(6)
                label.set_ellipsize(pango.ELLIPSIZE_START)
                self.tabs.append_page(scrollable_view, label)
                self.dict_key_to_tab[dict.key()] = scrollable_view
                self.tabs.set_tab_label_packing(scrollable_view, True,True,gtk.PACK_START)
                self.apply_phonetic_font()
                #self.remove_anonymous_tags()
                self.article_format.apply(word, article, article_view, self.word_ref_clicked)
                gobject.idle_add(lambda : article_view.scroll_to_iter(article_view.get_buffer().get_start_iter(), 0))
                self.add_to_history(word)            
                result = True           
        self.tabs.show_all()
        return result  
        
    #Anonymous tags are used to implement word references
    #when new article is loaded into text buffer old anonymous tags are no longer needed
    def remove_anonymous_tags(self):
        buffer = self.article_view.get_buffer()
        tag_table = buffer.get_tag_table()
        anon_tags = []
        tag_table.foreach(self.collect_anonymous_tags, anon_tags)        
        [tag_table.remove(tag) for tag in anon_tags]        
    
    def collect_anonymous_tags(self, tag, list):
        if tag.get_property('name') == None:
            list.append(tag)
    
    def word_selection_changed(self, selection):
        if selection.count_selected_rows() == 0:
            self.schedule(self.clear_tabs, 200)
            return
        model, iter = selection.get_selected()        
        if model.iter_has_child(iter):
            #language name, not a word
            self.schedule(self.clear_tabs, 200)
            return
        #model = tree_view.get_model()
        word = model[iter][0]
        lang = None
        lang_iter = model.iter_parent(iter)
        if lang_iter:
            lang = model[lang_iter]
        self.schedule_word_lookup(word, lang)
    
    def clear_word_input(self, btn, data = None):
        self.word_input.child.set_text('')
        gobject.idle_add(self.word_input.child.grab_focus)
                        
    def word_input_changed(self, editable, data = None):
        #self.update_completion(editable.get_text())                
        self.schedule(self.update_completion, 600, editable.get_text())        
                
    def update_completion(self, word, n = 20):
        word = word.strip()
        self.word_completion.set_model(None)        
        lang_word_list = self.dictionaries.get_word_list(word, n)
        if len(lang_word_list) == 1:
            model = gtk.ListStore(str)
            word_list = lang_word_list.values()[0]
            [model.append([word]) for word in word_list]
            self.word_completion.set_model(model)
            if len(word_list) == 1:
                path = model.get_path(model.get_iter_first())
                self.word_completion.set_cursor(path)
        else:
            model = gtk.TreeStore(str)
            for lang in lang_word_list.keys():
                iter = model.append(None, [lang])
                [model.append(iter, [word]) for word in lang_word_list[lang]]                
            self.word_completion.set_model(model)
            
        self.word_completion.expand_all()
        

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
        menu_bar.show_all()
        content_box.pack_start(menu_bar, False, False, 2)           

    def create_word_completion(self):
        word_completion = gtk.TreeView(gtk.ListStore(str))        
        word_completion.set_headers_visible(False)
        ##self.cursor_changed_handler_id = word_completion.connect("cursor-changed", self.word_selected)
        ##word_completion.connect("row-activated", self.word_selected)        
        word_completion.get_selection().connect("changed", self.word_selection_changed)
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

    def create_menu_items(self):
        self.mi_open = gtk.MenuItem("Add...")
        self.mi_open.connect("activate", self.select_dict_file)

        self.mn_remove = gtk.Menu()
        self.mn_remove_item = gtk.MenuItem("Remove")
        self.mn_remove_item.set_submenu(self.mn_remove)                        
        
        self.mi_info = gtk.MenuItem("Info...")
        self.mi_info.connect("activate", self.show_dict_info)
        
        self.mi_exit = gtk.MenuItem("Close")
        self.mi_exit.connect("activate", self.destroy)
        
                        
        self.mi_about = gtk.MenuItem("About %s..." % app_name)
        self.mi_about.connect("activate", self.show_about)
                        
        self.mi_select_phonetic_font = gtk.MenuItem("Phonetic Font...")
        self.mi_select_phonetic_font.connect("activate", self.select_phonetic_font)

    def create_menus(self):           
        mn_dict = gtk.Menu()
        mn_dict_item = gtk.MenuItem("Dictionary")
        mn_dict_item.set_submenu(mn_dict)        
        
        mn_dict.append(self.mi_open)        
        mn_dict.append(self.mn_remove_item)
        mn_dict.append(self.mi_info)
        mn_dict.append(self.mi_exit)
                
        mn_help = gtk.Menu()
        mn_help_item = gtk.MenuItem("Help")
        mn_help_item.set_submenu(mn_help)
        
        mn_help.append(self.mi_about)
                
        mn_options = gtk.Menu()
        mn_options_item = gtk.MenuItem("Options")
        mn_options_item.set_submenu(mn_options)
        
        mn_options.append(self.mi_select_phonetic_font)
        return (mn_dict_item, mn_options_item, mn_help_item)        

    def add_to_menu_remove(self, dict):        
        key = dict.key()
        title, version, file_name = key
        mi_dict = gtk.MenuItem("%s %s" % (title, version))                 
        if self.recent_menu_items.has_key(key):
            old_mi = self.recent_menu_items[key]
            self.mn_remove.remove(old_mi)
            del self.recent_menu_items[key]
        self.recent_menu_items[key] = mi_dict;        
        self.mn_remove.append(mi_dict)
        mi_dict.connect("activate", lambda f: self.remove_dict(dict))
        mi_dict.show_all()

    def get_dialog_parent(self):
        return self.window

    def update_title(self):
        if self.dictionaries.is_empty():        
            dict_title = "No dictionaries"
        else:            
            if self.dictionaries.size() == 1:
                dict_title = ("%d dictionary") % self.dictionaries.size()
            else:
                dict_title = ("%d dictionaries") % self.dictionaries.size()
        title = "%s - %s" % (dict_title, app_name)
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
        buffer.create_tag("r", underline = True, foreground = "blue")
        buffer.create_tag("t", weight = pango.WEIGHT_BOLD, foreground = "darkred")
        buffer.create_tag("sup", rise = 2, scale = pango.SCALE_XX_SMALL)
        tag_sub = buffer.create_tag("sub", rise = -2, scale = pango.SCALE_XX_SMALL)
        article_view.connect("motion_notify_event", self.on_mouse_motion)        
        return article_view            
    
    def on_mouse_motion(self, widget, event, data = None):
        text_window = widget.get_window(gtk.TEXT_WINDOW_TEXT)
        x, y, flags = text_window.get_pointer()                    
        x, y = widget.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, x, y)
        tags = widget.get_iter_at_location(x, y).get_tags()
        is_ref = False
        for tag in tags:
            if tag.get_property("name") == "r":
                is_ref = True
        if is_ref:
            text_window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))            
        else:
            text_window.set_cursor(None)
        return False
        
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
        if not self.dictionaries.is_empty():
            dlg.set_filename(self.last_dict_file_location)        
        return dlg
    
    def open_dict(self, file):
        self.open_dicts([file])
        
    def open_dicts(self, files):
        if len(files) == 0:
            return
        file = files.pop(0)
        if len(files) > 0:
            message = "%s (%d more to go)" % (file, len(files))
        else:
            message = file
        status_display = self.create_dict_loading_status_display(message)
        worker = ui_util.BackgroundWorker(lambda : (sdict.SDictionary(file), files), status_display, self.collect_dict_callback)
        worker.start()
        
    def collect_dict_callback(self, dict_and_files, error):
        dict, files = dict_and_files
        if not error:
            self.add_dict(dict)
        else:
            print "Failed to open dictionary: ", error
        self.open_dicts(files)
        
        
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
        self.add_dict(dict)

    def add_dict(self, dict):
        if (self.dictionaries.has(dict)):
            print "Dictionary is already open"
            return
        self.last_dict_file_location = dict.file_name
        self.dictionaries.add(dict)
        self.add_to_menu_remove(dict)
        self.update_completion(self.word_input.child.get_text())
        self.process_word_input(self.word_input.child.get_text())
        self.update_title()  
        
    def remove_dict(self, dict):          
        key = dict.key()
        title, version, file_name = key
        if self.recent_menu_items.has_key(key):
            old_mi = self.recent_menu_items[key]
            self.mn_remove.remove(old_mi)
            del self.recent_menu_items[key]                
        self.dictionaries.remove(dict)       
        self.tabs.remove_page(self.get_tab_for_dict(key)) 
        dict.close()
        self.word_completion.get_model().clear()
        self.update_completion(self.word_input.child.get_text())
        self.update_completion(self.word_input.child.get_text())
        self.update_title()
        
    def get_tab_for_dict(self, dict_key):
        if self.dict_key_to_tab.has_key(dict_key):
            tab_child = self.dict_key_to_tab[dict_key]
            return self.tabs.page_num(tab_child)
        return None


    def show_dict_info(self, widget):        
        info_dialog = dict_info_ui.DictInfoDialog(self.dictionaries.get_dicts())
        info_dialog.run()
        info_dialog.destroy()
        
    def show_about(self, widget):
        dialog = gtk.AboutDialog()
        dialog.set_position(gtk.WIN_POS_CENTER)
        dialog.set_name(app_name)
        dialog.set_version(version)
        dialog.set_copyright("Igor Tkach")
        dialog.set_website("http://sdictviewer.sf.net/")
        comments = "%s is viewer for dictionaries in open format described at http://sdict.com\nDistributed under terms and conditions of GNU Public License\nSee http://www.gnu.org/licenses/gpl.txt for details" % app_name
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
        self.apply_phonetic_font()
    
    def apply_phonetic_font(self):
        font_desc = pango.FontDescription(self.font)
        if font_desc: 
            count = self.tabs.get_n_pages()
            for n in xrange(0,count):
                page = self.tabs.get_nth_page(n)
                text_buffer = page.get_child().get_buffer()            
                #text_buffer = self.article_view.get_buffer()
                tag_table = text_buffer.get_tag_table()
                tag_table.lookup("t").set_property("font-desc", font_desc)
        
    def main(self):
        gtk.main()            
        