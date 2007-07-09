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
import xml.sax.saxutils

gobject.threads_init()

version = "0.4.1"
settings_dir  = ".sdictviewer"
app_state_file = "app_state"
old_settings_file_name = ".sdictviewer"
app_name = "SDict Viewer"

def save_app_state(app_state):
    home_dir = os.path.expanduser('~')
    settings_dir_path = os.path.join(home_dir, settings_dir)
    if not os.path.exists(settings_dir_path):
        try:
            os.mkdir(settings_dir_path)
        except:
            pass        
    settings = os.path.join(home_dir, settings_dir, app_state_file)
    try:
        settings_file = file(settings, "w")
        pickle.dump(app_state, settings_file)
        return
    except IOError:
        pass    
    
def load_app_state():
    home_dir = os.path.expanduser('~')
    settings = os.path.join(home_dir, settings_dir, app_state_file)
    old_settings = False
    app_state = None
    if not os.path.exists(settings):
        #If there is no new style setting, try to read the old one.
        settings = os.path.join(home_dir, old_settings_file_name)        
        old_settings = True
    if os.path.exists(settings):        
        settings_file = file(settings, "r")
        app_state = pickle.load(settings_file)
        if old_settings:
            try:
                os.remove(settings)
                save_app_state(app_state)
            except:
                pass                    
    return app_state
    
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
    
    def __init__(self, parent):
        self.loading_dialog = None        
        self.parent = parent
        self.loading_dialog = gtk.MessageDialog(parent=self.parent, flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_INFO)        
        self.shown = False
        
    def show(self):        
        self.shown = True
        self.loading_dialog.run()
        
    def set_message(self, message, title):
        self.title = title
        self.loading_dialog.set_title(self.title)
        self.loading_dialog.set_markup(message)
            
    def dismiss(self):
        if self.loading_dialog:
            self.loading_dialog.destroy()
            self.loading_dialog = None            
            
    def before_task_start(self):
        if not self.shown:
            self.show()
            
    def after_task_end(self):
        ''
            

class ArticleFormat: 
    
    def __init__(self):
        self.template = string.Template("$word\n$text")
       
    def apply(self, dict, word, article, article_view, word_ref_callback):
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
        [self.create_ref(mark, buffer, dict, word, word_ref_callback, article_view) for mark in ref_regions]                            
        [self.apply_tag(mark, buffer, "sup") for mark in sup_regions]
        [self.apply_tag(mark, buffer, "sub") for mark in sub_regions]
        
    def create_ref(self, mark, buffer, dict, word, word_ref_callback, article_view):
        start = buffer.get_iter_at_mark(mark[0])
        end = buffer.get_iter_at_mark(mark[1])
        text = buffer.get_text(start, end)
        ref_text = text.replace("~", word)
        ref_tag = buffer.create_tag()
        ref_tag.connect("event", word_ref_callback, ref_text, dict)
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

class SDictViewer(object):
             
    def __init__(self):
        self.status_display = None
        self.dictionaries = sdict.SDictionaryCollection()
        self.current_word_handler = None                               
        self.window = self.create_top_level_widget()                               
        self.font = None
        self.last_dict_file_location = None
        self.article_format = ArticleFormat()
        self.recent_menu_items = {}
        self.dict_key_to_tab = {}
        self.file_chooser_dlg = None
                                 
        contentBox = gtk.VBox(False, 0)
        self.create_menu_items()
        self.add_menu(contentBox)
                                        
        box = gtk.VBox()        
        
        input_box = gtk.HBox()
        btn_paste = self.create_paste_button()
        input_box.pack_start(btn_paste, False, False, 0)
        self.word_input = self.create_word_input()
        input_box.pack_start(self.word_input, True, True, 0)
        btn_clear_input = self.create_clear_button()
        input_box.pack_start(btn_clear_input, False, False, 2)
        
        box.pack_start(input_box, False, False, 4)
        
        self.word_completion = self.create_word_completion()
        box.pack_start(ui_util.create_scrolled_window(self.word_completion), True, True, 0)

        split_pane = gtk.HPaned()        
        contentBox.pack_start(split_pane, True, True, 2)                        
        split_pane.add(box)
        
        self.tabs = gtk.Notebook()
        self.tabs.set_scrollable(True)
        self.tabs.popup_enable()
        self.tabs.set_property("can-focus", False)
#        page-added and page-removed is only available in PyGTK 2.10, doesn't work in Maemo
#        self.tabs.connect("page-added", self.update_copy_article_mi)
#        self.tabs.connect("page-removed", self.update_copy_article_mi)
        split_pane.add(self.tabs)
                        
        self.add_content(contentBox)
        self.update_title()
        self.window.show_all()
        self.word_input.child.grab_focus()
        try:
            app_state = load_app_state()     
            if app_state:   
                self.open_dicts(app_state.dict_files)
                self.word_input.child.set_text(app_state.word)                
                app_state.history.reverse()
                [self.add_to_history(w, l) for w, l in app_state.history]
                self.set_phonetic_font(app_state.phonetic_font)
                self.last_dict_file_location = app_state.last_dict_file_location
                
        except Exception, ex:
            print 'Failed to load application state:', ex                     
             
    def update_copy_article_mi(self, notebook = None, child = None, page_num = None):
        self.mi_copy_article_to_clipboard.set_sensitive(notebook.get_n_pages() > 0)
             
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
            raise
        gtk.main_quit()                  
        
    def on_key_press(self, widget, event, *args):
        if event.keyval == gtk.keysyms.Escape:
            self.clear_word_input(None, None)
        if event.keyval == gtk.keysyms.F7:
            self.tabs.prev_page()
        if event.keyval == gtk.keysyms.F8:
            self.tabs.next_page()
        
        
    def history_to_list(self, model, path, iter, history_list):
        word, lang = model[iter]
        history_list.append((word, lang))
        
    def do_word_lookup(self, word, lang):
        self.show_article_for(word, lang)
        return False
                    
    def schedule(self, f, timeout, *args):
        if self.current_word_handler:
            gobject.source_remove(self.current_word_handler)
            self.current_word_handler = None
        self.current_word_handler = gobject.timeout_add(timeout, f, *args)                
                        
    def select_first_word_in_completion(self):
        model = self.word_completion.get_model()
        if not model:
            return
        first_lang = model.get_iter_first()
        if first_lang: 
            word_iter = model.iter_children(first_lang)
            self.word_completion.get_selection().select_iter(word_iter)
            self.word_completion.grab_focus()                
                        
    def word_ref_clicked(self, tag, widget, event, iter, word, dict):
        if event.type == gtk.gdk.BUTTON_RELEASE:
            self.word_input.handler_block(self.word_change_handler) 
            self.word_input.child.set_text(word)
            self.word_input.handler_unblock(self.word_change_handler) 
            self.update_completion_and_select(word, word, dict.header.word_lang)
                
    def add_to_history(self, word, lang):        
        model = self.word_input.get_model()
        insert = True;
        for row in model:
            if word == row[0] and lang == row[1]:
                insert = False;
                break;
        if insert:
            model.insert(None, 0, [word, lang])  
        history_size = model.iter_n_children(None)
        if history_size > 10:
            del model[history_size - 1]
                
    def clear_tabs(self):
        while self.tabs.get_n_pages() > 0:            
            last_page = self.tabs.get_nth_page(self.tabs.get_n_pages() - 1)
            article_view = last_page.get_child()
            self.remove_handlers(article_view)
            text_buffer = article_view.get_buffer()
            self.remove_handlers(text_buffer)
            self.tabs.remove_page(-1)        
        self.dict_key_to_tab.clear()       
        self.update_copy_article_mi(self.tabs)
        return False 
    
    def remove_handlers(self, obj):
        handlers = obj.get_data("handlers")
        for handler in handlers:
            obj.disconnect(handler)
        obj.set_data("handlers", None)
    
    def show_article_for(self, word, lang = None):
        if lang:
            langs = [lang]
        else:
            langs = None
        articles = self.dictionaries.lookup(word, langs)
        self.clear_tabs()
        result = False
        for dict, article in articles:        
            if article: 
                article_view = self.create_article_view()
                article_view.set_property("can-focus", False)
                scrollable_view = ui_util.create_scrolled_window(article_view)                
                scrollable_view.set_property("can-focus", False)
                label = gtk.Label(dict.title)
                label.set_width_chars(6)
                label.set_ellipsize(pango.ELLIPSIZE_START)
                self.tabs.append_page(scrollable_view, label)
                self.dict_key_to_tab[dict.key()] = scrollable_view
                self.tabs.set_tab_label_packing(scrollable_view, True,True,gtk.PACK_START)
                self.apply_phonetic_font()
                self.article_format.apply(dict, word, article, article_view, self.word_ref_clicked)
                gobject.idle_add(lambda : article_view.scroll_to_iter(article_view.get_buffer().get_start_iter(), 0))
                self.add_to_history(word, lang)            
                result = True           
        self.update_copy_article_mi(self.tabs)
        self.tabs.show_all()
        return result  
            
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
        word = model[iter][0]
        lang = None
        lang_iter = model.iter_parent(iter)
        if lang_iter:
            lang = model[lang_iter][0]
        self.schedule(self.do_word_lookup, 200, word, lang)
    
    def clear_word_input(self, btn, data = None):
        self.word_input.child.set_text('')
        self.word_input.child.grab_focus()
        
    def paste_to_word_input(self, btn, data = None): 
        clipboard = gtk.clipboard_get(gtk.gdk.SELECTION_CLIPBOARD)
        clipboard.request_text(lambda clipboard, text, data : self.word_input.child.set_text(text))
        self.word_input.child.grab_focus()
          
    def get_selected_word(self):
        selection = self.word_completion.get_selection()
        current_model, selected = selection.get_selected()
        selected_lang = None
        selected_word = None
        if selected:
            if not current_model.iter_has_child(selected):
                selected_word = current_model[selected][0]
                selected_lang = current_model[current_model.iter_parent(selected)][0]                            
        return (selected_word, selected_lang)
                                        
    def update_completion(self, word, n = 20, select_if_one = True):        
        word = word.lstrip()
        self.word_completion.set_model(None)        
        lang_word_list = self.dictionaries.get_word_list(word, n)
        model = gtk.TreeStore(str)
        for lang in lang_word_list.keys():
            iter = model.append(None, [lang])
            [model.append(iter, [word]) for word in lang_word_list[lang]]                    
        self.word_completion.set_model(model)            
        self.word_completion.expand_all()
        if select_if_one and len (lang_word_list) == 1 and len(lang_word_list.values()[0]) == 1:
            self.select_first_word_in_completion()  

    def create_clear_button(self):
        return self.create_button(gtk.STOCK_CLEAR, self.clear_word_input) 

    def create_paste_button(self):
        return self.create_button(gtk.STOCK_PASTE, self.paste_to_word_input)
    
    def create_button(self, stock_id, action):
        button = gtk.Button(stock = stock_id)
        settings = button.get_settings()
        settings.set_property( "gtk-button-images", True )        
        button.set_label('')
        button.set_image(gtk.image_new_from_stock(stock_id, gtk.ICON_SIZE_SMALL_TOOLBAR))
        button.set_relief(gtk.RELIEF_NONE)
        button.set_focus_on_click(False)
        button.connect("clicked", action);
        return button                
   
    def create_top_level_widget(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)    
        window.connect("destroy", self.destroy)
        window.set_border_width(2)                
        window.resize(640, 480)
        window.set_position(gtk.WIN_POS_CENTER)        
        window.connect("key-press-event", self.on_key_press)
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
        word_completion = gtk.TreeView()        
        word_completion.set_headers_visible(False)
        word_completion.get_selection().connect("changed", self.word_selection_changed)
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn("", renderer, text=0)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        word_completion.append_column(column)            
        word_completion.set_fixed_height_mode(True)
        return word_completion

    def create_word_input(self):
        word_input = gtk.ComboBoxEntry(gtk.TreeStore(str, str))
        word_input.clear()
        cell1 = gtk.CellRendererText()
        word_input.pack_start(cell1, False)        
        word_input.set_cell_data_func(cell1, self.format_history_item)
        word_input.child.connect("activate", lambda x: self.select_first_word_in_completion())                
        self.word_change_handler = word_input.connect("changed", self.word_selected_in_history)
        return word_input
    
    def format_history_item(self, celllayout, cell, model, iter, user_data = None):
        word  = model[iter][0]
        lang  = model[iter][1]
        word = xml.sax.saxutils.escape(word)
        cell.set_property('markup', '<span>%s</span> <span foreground="darkgrey">(<i>%s</i>)</span>' % (word, lang)) 
        
        
    def word_selected_in_history(self, widget, data = None):                
        active = self.word_input.get_active()
        if active == -1:
            #removing selection prevents virtual keaboard from disapppearing
            self.clear_tabs();
            self.word_completion.get_selection().unselect_all()
            self.schedule(self.update_completion, 600, self.word_input.child.get_text())            
            #self.update_completion(self.word_input.child.get_text())
            return
        active_row = self.word_input.get_model()[active]
        word = active_row[0]
        lang = active_row[1]
        #use schedule instead of direct call to interrupt already scheduled update if any
        self.schedule(self.update_completion_and_select, 0, word, word, lang)        
        self.update_completion(word, select_if_one = False)
        self.select_word(word, lang)        
        
    def update_completion_and_select(self, completion_word, word, lang):
        self.update_completion(completion_word, select_if_one = False)
        self.select_word(word, lang)        
        return False
        
    def select_word(self, word, lang):        
        model = self.word_completion.get_model()
        if len (model) == 0:
            return
        lang_iter = None
        current_lang_iter = model.get_iter_first()
        while current_lang_iter and model[current_lang_iter][0] != lang:
            current_lang_iter = model.iter_next(current_lang_iter)
        if current_lang_iter and model[current_lang_iter][0] == lang:
            lang_iter = current_lang_iter
        if lang_iter:                    
            word_iter = model.iter_children(lang_iter)
            while word_iter and model[word_iter][0] != word:
                word_iter = model.iter_next(word_iter)
            if word_iter and model[word_iter][0] == word:
                self.word_completion.get_selection().select_iter(word_iter)            
                word_path = model.get_path(word_iter)
                self.word_completion.scroll_to_cell(word_path)

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

        self.mn_copy = gtk.Menu()
        self.mn_copy_item =gtk.MenuItem("Copy")
        self.mn_copy_item.set_submenu(self.mn_copy)

        self.mi_copy_article_to_clipboard = gtk.MenuItem("Article")
        self.mi_copy_article_to_clipboard.set_sensitive(False)
        self.mi_copy_article_to_clipboard.connect("activate", self.copy_article_to_clipboard)
        
        self.mi_copy_to_clipboard = gtk.MenuItem("Selected Text")
        self.mi_copy_to_clipboard.set_sensitive(False)
        self.mi_copy_to_clipboard.connect("activate", self.copy_selected_to_clipboard)
        
        self.mn_copy.append(self.mi_copy_article_to_clipboard)
        self.mn_copy.append(self.mi_copy_to_clipboard)

    def create_menus(self):           
        mn_dict = gtk.Menu()
        mn_dict_item = gtk.MenuItem("Dictionary")
        mn_dict_item.set_submenu(mn_dict)        
        
        mn_dict.append(self.mi_open)        
        mn_dict.append(self.mn_remove_item)
        mn_dict.append(self.mi_info)
        mn_dict.append(self.mn_copy_item)
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

    def copy_selected_to_clipboard(self, widget):
        page_num = self.tabs.get_current_page()
        if page_num < 0:
            return        
        article_view = self.tabs.get_nth_page(page_num).get_child()
        text_buffer = article_view.get_buffer()
        text_buffer.copy_clipboard(gtk.clipboard_get(gtk.gdk.SELECTION_CLIPBOARD))

    def copy_article_to_clipboard(self, widget):
        clipboard = gtk.clipboard_get(gtk.gdk.SELECTION_CLIPBOARD)        
        page_num = self.tabs.get_current_page()
        if page_num < 0:
            return        
        article_view = self.tabs.get_nth_page(page_num).get_child()
        text_buffer = article_view.get_buffer()
        text = text_buffer.get_text(*text_buffer.get_bounds())
        clipboard.set_text(text)                

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
        handler1 = buffer.connect("mark-set", self.article_text_selection_changed)
        handler2 = buffer.connect("mark-deleted", self.article_text_selection_changed)
        buffer.set_data("handlers", (handler1, handler2))
        tag_sub = buffer.create_tag("sub", rise = -2, scale = pango.SCALE_XX_SMALL)
        handler = article_view.connect("motion_notify_event", self.on_mouse_motion)        
        article_view.set_data("handlers", [handler])
        return article_view            
    
    def article_text_selection_changed(self, *args):
        page_num = self.tabs.get_current_page() 
        sensitive = False       
        if page_num >= 0:            
            article_view = self.tabs.get_nth_page(page_num).get_child()
            text_buffer = article_view.get_buffer()
            sensitive = len(text_buffer.get_selection_bounds()) > 0
        self.mi_copy_to_clipboard.set_sensitive(sensitive)
    
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
        if not self.file_chooser_dlg:
            self.file_chooser_dlg = self.create_file_chooser_dlg()
            self.file_chooser_dlg.set_title("Open Dictionary")
        if self.file_chooser_dlg.run() == gtk.RESPONSE_OK:
            fileName = self.file_chooser_dlg.get_filename()
            self.open_dict(fileName)
        self.file_chooser_dlg.hide()        
        
    def create_file_chooser_dlg(self):
        dlg = gtk.FileChooserDialog(parent = self.window, action = gtk.FILE_CHOOSER_ACTION_OPEN)        
        dlg.add_button( gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        dlg.add_button( gtk.STOCK_OPEN, gtk.RESPONSE_OK)        
        if self.last_dict_file_location:
            dlg.set_filename(self.last_dict_file_location)        
        return dlg
    
    def open_dict(self, file):
        self.open_dicts([file])
                
    def open_dicts(self, files):
        if len(files) == 0:
            if self.status_display:
                self.status_display.dismiss()
                self.status_display = None
            return
        if not self.status_display:
            self.status_display = self.create_dict_loading_status_display()            
            self.status_display.total_files = len(files)
        file = files.pop(0)
        self.status_display.set_message(file, "Loading %d of %d" % (self.status_display.total_files - len(files), self.status_display.total_files))
        worker = ui_util.BackgroundWorker(lambda : sdict.SDictionary(file), self.status_display, self.collect_dict_callback, files)
        worker.start()
        
    def collect_dict_callback(self, dict, error, files):
        if not error:
            self.add_dict(dict)
        else:
            print "Failed to open dictionary: ", error
            try: 
                raise error
            except IOError:
                self.show_error("Dictionary Open Failed", "%s: %s" % (error.strerror, error.filename))
            except sdict.DictFormatError:
                self.show_error("Dictionary Open Failed", str(error))
            except ValueError:
                self.show_error("Dictionary Open Failed", str(error))
        self.open_dicts(files)
        
        
    def create_dict_loading_status_display(self):            
        return DialogStatusDisplay(self.get_dialog_parent())
        
    def show_error(self, title, text):
        dlg = gtk.MessageDialog(parent=self.window, flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_CLOSE, message_format=text)
        dlg.set_title(title)
        dlg.run()
        dlg.destroy()
    
    def add_dict(self, dict):
        if (self.dictionaries.has(dict)):
            print "Dictionary is already open"
            return
        word, lang = self.get_selected_word()
        self.last_dict_file_location = dict.file_name
        self.dictionaries.add(dict)
        self.add_to_menu_remove(dict)
        self.schedule(self.update_completion_and_select, 600, self.word_input.child.get_text(), word, lang)
        self.update_title()  
        
    def remove_dict(self, dict):          
        word, lang = self.get_selected_word()
        key = dict.key()
        title, version, file_name = key
        if self.recent_menu_items.has_key(key):
            old_mi = self.recent_menu_items[key]
            self.mn_remove.remove(old_mi)
            del self.recent_menu_items[key]                
        self.dictionaries.remove(dict)       
        tab = self.get_tab_for_dict(key)
        if tab:
            self.tabs.remove_page(tab) 
            del self.dict_key_to_tab[key]
        dict.close()
        dict.remove_index_cache_file()
        self.update_completion_and_select(self.word_input.child.get_text(), word, lang)
        self.update_title()
        
    def get_tab_for_dict(self, dict_key):
        if self.dict_key_to_tab.has_key(dict_key):
            tab_child = self.dict_key_to_tab[dict_key]
            return self.tabs.page_num(tab_child)
        return None

    def show_dict_info(self, widget):        
        info_dialog = dict_info_ui.DictInfoDialog(self.dictionaries.get_dicts(), parent = self.window)
        info_dialog.run()
        info_dialog.destroy()
        
    def show_about(self, widget):
        dialog = gtk.AboutDialog()
        dialog.set_position(gtk.WIN_POS_CENTER)
        dialog.set_name(app_name)
        dialog.set_version(version)
        dialog.set_copyright("Igor Tkach, Sam Tygier")
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
                tag_table = text_buffer.get_tag_table()
                tag_table.lookup("t").set_property("font-desc", font_desc)
        
    def main(self):
        gtk.main()            
        