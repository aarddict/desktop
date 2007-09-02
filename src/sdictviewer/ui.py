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
import pygtk
pygtk.require('2.0')
import gtk
import pango
import sdict
import dictinfo
import util
import articleformat
from appstate import *
import gobject
import string
import xml.sax.saxutils
import re
import time
import webbrowser
from threading import Thread
from Queue import Queue

gobject.threads_init()

version = "0.4.5"
app_name = "SDict Viewer"

UPDATE_COMPLETION_TIMEOUT_S = 120.0
UPDATE_COMPLETION_TIMEOUT_CHECK_MS = 5000
STATUS_MESSAGE_TRUNCATE_LEN = 60

class SDictViewer(object):
             
    def __init__(self):
        self.update_completion_stopped = True
        self.lookup_stop_requested = False
        self.update_completion_t0 = None
        self.status_display = None
        self.dictionaries = sdict.SDictionaryCollection()
        self.current_word_handler = None                               
        self.window = self.create_top_level_widget()                               
        self.font = None
        self.last_dict_file_location = None
        self.article_format = articleformat.ArticleFormat(self, self.external_link_callback)
        self.recent_menu_items = {}
        self.dict_key_to_tab = {}
        self.file_chooser_dlg = None
        
        self.statusbar = gtk.Statusbar()
        self.statusbar.set_has_resize_grip(False)
        self.update_completion_ctx_id = self.statusbar.get_context_id("update completion")
        self.update_completion_timeout_ctx_id = self.statusbar.get_context_id("update completion timeout")

        self.start_worker_threads()
                                 
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
        box.pack_start(util.create_scrolled_window(self.word_completion), True, True, 0)

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
        
        contentBox.pack_start(self.statusbar, False, True, 0)
                        
        self.add_content(contentBox)
        self.update_title()
        self.window.show_all()
        self.word_input.child.grab_focus()
        try:
            self.select_word_on_open = None
            app_state = load_app_state()     
            if app_state: 
                self.select_word_on_open = app_state.selected_word
                self.set_word_input(app_state.word)
                self.open_dicts(app_state.dict_files)
                app_state.history.reverse()
                [self.add_to_history(w, l) for w, l in app_state.history]
                self.set_phonetic_font(app_state.phonetic_font)
                self.last_dict_file_location = app_state.last_dict_file_location
                
        except Exception, ex:
            print 'Failed to load application state:', ex                     
    
    def start_worker_threads(self):
        self.open_q = Queue()
        open_dict_worker_thread = Thread(target = self.open_dict_worker)
        open_dict_worker_thread.setDaemon(True)
        open_dict_worker_thread.start()
        self.update_completion_q = Queue(1)
        update_completion_thread = Thread(target = self.update_completion_worker)
        update_completion_thread.setDaemon(True)
        update_completion_thread.start()
        gobject.timeout_add(UPDATE_COMPLETION_TIMEOUT_CHECK_MS, self.check_update_completion_timeout)
         
    def update_copy_article_mi(self, notebook = None, child = None, page_num = None):
        self.mi_copy_article_to_clipboard.set_sensitive(notebook.get_n_pages() > 0)
             
    def destroy(self, widget, data=None):
        self.stop_lookup()
        Thread(target = self.save_state_worker).start()
        self.show_status_display("Saving application state...", "Exiting")
        
    def save_state_worker(self):
        time.sleep(0)
        word = self.word_input.child.get_text()
        history_list = []
        hist_model = self.word_input.get_model()
        time.sleep(0)
        hist_model.foreach(self.history_to_list, history_list)
        time.sleep(0)
        selected_word, selected_word_lang = self.get_selected_word()
        selected = (str(selected_word), selected_word_lang)
        dict_files = [dict.file_name for dict in self.dictionaries.get_dicts()]
        state = State(self.font, word, selected, history_list, self.recent_menu_items.keys(), dict_files, self.last_dict_file_location)
        errors = []
        for dict in self.dictionaries.get_dicts():
            try:
                dict.close()
            except Exception, e:
                errors.append(e)
        try:
            save_app_state(state)
        except Exception, e:
            errors.append(e)
        gobject.idle_add(self.shutdown_ui, errors)
        
    def shutdown_ui(self, errors):     
        self.hide_status_display()                    
        if len(errors) > 0:
            msg = self.errors_to_text(errors)
            self.show_error("Failed to Save State", msg)
        gtk.main_quit() 
        
    def errors_to_text(self, errors):
        text = ""
        for e in errors:
            text += str(e) + "\n"  
        return text     
        
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
        
    def do_show_word_article(self, word, lang):
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
                        
    def word_ref_clicked(self, tag, widget, event, iter, word, dict):
        #print "word_ref_clicked", event.type, event.get_coords(), word
        if self.is_link_click(widget, event, word):
            self.set_word_input(word)
            self.update_completion(word, (word, dict.header.word_lang))
            
    def external_link_callback(self, tag, widget, event, iter, url):
        #print "external_link_callback", event.type, event.get_coords(), url
        if self.is_link_click(widget, event, url):
            self.open_external_link(url)
  
    def open_external_link(self, url):
        webbrowser.open(url)
    
    def is_link_click(self, widget, event, reference):
        result = False
        if event.type == gtk.gdk.BUTTON_PRESS:
            widget.armed_link = (reference, event.get_coords())
        if hasattr(widget, "armed_link") and widget.armed_link:        
            if event.type == gtk.gdk.MOTION_NOTIFY:
                armed_ref, armed_coords = widget.armed_link
                armed_x, armed_y = armed_coords
                evt_x, evt_y = event.get_coords()
                if armed_x != evt_x or armed_y != evt_y:  
                    widget.armed_link = None
            if event.type == gtk.gdk.BUTTON_RELEASE:
                armed_ref, armed_coords = widget.armed_link
                if armed_ref == reference:
                    result = True
                widget.armed_link = None
        return result
            
    def set_word_input(self, word, supress_update = True):
        if supress_update: self.word_input.handler_block(self.word_change_handler)
        self.word_input.child.set_text(word)
        self.word_input.child.set_position(-1)    
        if supress_update: self.word_input.handler_unblock(self.word_change_handler) 
                
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
        self.article_format.stop()
        return False 
    
    def remove_handlers(self, obj):
        handlers = obj.get_data("handlers")
        for handler in handlers:
            obj.disconnect(handler)
        obj.set_data("handlers", None)
    
    def show_article_for(self, wordlookup, lang = None):
        if lang:
            langs = [lang]
        else:
            langs = None
        articles = wordlookup.read_articles()
        word = str(wordlookup)
        self.clear_tabs()
        result = False
        for dict, article in articles:        
            if article: 
                article_view = self.create_article_view()
                article_view.set_property("can-focus", False)
                scrollable_view = util.create_scrolled_window(article_view)                
                scrollable_view.set_property("can-focus", False)
                label = gtk.Label(dict.title)
                label.set_width_chars(6)
                label.set_ellipsize(pango.ELLIPSIZE_START)
                self.tabs.append_page(scrollable_view, label)
                self.dict_key_to_tab[dict.key()] = scrollable_view
                self.tabs.set_tab_label_packing(scrollable_view, True,True,gtk.PACK_START)
                self.article_format.apply(dict, word, article, article_view, self.word_ref_clicked)
                self.add_to_history(word, lang)            
                result = True           
        self.update_copy_article_mi(self.tabs)
        self.tabs.show_all()
        return result  
            
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
        self.schedule(self.do_show_word_article, 200, word, lang)
    
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
        selected_lang, selected_word = None, None
        if selected and not current_model.iter_has_child(selected):
            selected_word = current_model[selected][0]
            selected_lang = current_model[current_model.iter_parent(selected)][0]                            
        return (selected_word, selected_lang)
    
    def stop_lookup(self):
        if not self.update_completion_stopped:
            message_id = self.statusbar.push(self.update_completion_ctx_id, 'Stopping current lookup...')
            self.lookup_stop_requested = True
            self.update_completion_q.join()
            self.lookup_stop_requested = False
            self.statusbar.remove(self.update_completion_ctx_id, message_id)

    def check_update_completion_timeout(self):
        if self.update_completion_t0:
            elapsed = time.time() - self.update_completion_t0
            if elapsed > UPDATE_COMPLETION_TIMEOUT_S:
                self.stop_lookup()
                self.statusbar.push(self.update_completion_timeout_ctx_id, 'Lookup stopped: it was taking too long')
        return True     
    
    def update_completion_worker(self):
        while True:
            print "[update_completion_worker] Waiting for next update completion task"
            start_word, to_select = self.update_completion_q.get()
            self.update_completion_t0 = time.time()
            self.update_completion_stopped = False
            print '[update_completion_worker] Will look for "%s" in %d dictionaries' % (start_word, self.dictionaries.size())
            lang_word_list, interrupted = self.do_lookup(start_word, to_select)
            if not interrupted:
                gobject.idle_add(self.update_completion_callback, lang_word_list, to_select, start_word, time.time() - self.update_completion_t0)
            else:
                print '[update_completion_worker] === Lookup for "%s" interrupted' % start_word
            self.update_completion_t0 = None
            self.update_completion_stopped = True
            self.update_completion_q.task_done()
    
    def do_lookup(self, start_word, to_select):
        interrupted = False
        lang_word_list = {}
        skipped = util.ListMap()
        for lang in self.dictionaries.langs():
            word_lookups = sdict.WordLookupByWord()
            for item in self.dictionaries.get_word_list_iter(lang, start_word):
                time.sleep(0)
                if self.lookup_stop_requested:
                    interrupted = True
                    return (lang_word_list, interrupted)
                if isinstance(item, sdict.WordLookup):
                    word_lookups[item.word].add_articles(item)
                else:
                    skipped[item.dict].append(item)
            word_list = word_lookups.values()
            word_list.sort(key=str)
            if len (word_list) > 0: lang_word_list[lang] = word_list
            for dict, skipped_words in skipped.iteritems():
                print "[update_completion_worker] Skipped %d words in %s" % (len(skipped_words), dict)
                for stats in dict.index(skipped_words):
                    time.sleep(0)
                    if self.lookup_stop_requested:
                        interrupted = True
                        print "[update_completion_worker] === Indexing of", len(skipped_words), "in",dict, "stopped"
                        return (lang_word_list, interrupted)
        return (lang_word_list, interrupted)
                                        
    def update_completion(self, word, to_select = None):
        self.statusbar.pop(self.update_completion_ctx_id) 
        self.statusbar.pop(self.update_completion_timeout_ctx_id)
        self.word_completion.set_model(None)   
        self.stop_lookup()
        word = word.lstrip()
        print "[update_completion] requested for '%s'" % word 
        if word and len(word) > 0:
            self.statusbar.push(self.update_completion_ctx_id, 'Looking up "%s"...' % word)
            self.update_completion_q.put((word, to_select))  
        return False
    
    def update_completion_callback(self, lang_word_list, to_select, start_word, lookup_time):
        self.statusbar.pop(self.update_completion_ctx_id)  
        msg_params = (start_word, lookup_time) 
        statusmsg = '%s: looked up in %.2f s' % msg_params
        count = 0  
        for word_list in lang_word_list.itervalues():
            count += len(word_list)       
        if count == 0: statusmsg += ', nothing found'
        self.statusbar.push(self.update_completion_ctx_id, statusmsg) 
        model = gtk.TreeStore(object)
        for lang in lang_word_list.iterkeys():
            print "[update_completion_callback] %d words in %s" % (len(lang_word_list[lang]), lang)
            iter = model.append(None, [lang])
            [model.append(iter, [word]) for word in lang_word_list[lang]]                    
        self.word_completion.set_model(model)            
        self.word_completion.expand_all()
        selected = False
        if to_select:
            word, lang = to_select
            selected = self.select_word(word, lang)
        if not selected and len (lang_word_list) == 1 and len(lang_word_list.values()[0]) == 1:
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
        window.connect("event", self.window_event)  
        window.set_border_width(2)                
        window.resize(640, 480)
        window.set_position(gtk.WIN_POS_CENTER)        
        window.connect("key-press-event", self.on_key_press)
        return window
    
    def window_event(self, window, event, data = None):
        if event.type == gtk.gdk.DELETE:
            self.destroy(window, data)
            return True
    
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
        column = gtk.TreeViewColumn("", renderer)
        column.set_cell_data_func(renderer, self.get_word_from_wordlookup, data=None)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        word_completion.append_column(column)            
        word_completion.set_fixed_height_mode(True)
        return word_completion

    def get_word_from_wordlookup(self, treeviewcolumn, cell_renderer, model, iter):
        wordlookup = model[iter][0]
        cell_renderer.set_property('text', str(wordlookup))
        return        

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
        word, lang  = model[iter]
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
        word, lang = self.word_input.get_model()[active]
        #use schedule instead of direct call to interrupt already scheduled update if any
        self.schedule(self.update_completion, 0, word, (word, lang))        
        
    def select_word(self, word, lang):        
        model = self.word_completion.get_model()
        if len (model) == 0:
            return False
        lang_iter = current_lang_iter = model.get_iter_first()
        if len (model) > 1:
            while current_lang_iter and model[current_lang_iter][0] != lang:
                current_lang_iter = model.iter_next(current_lang_iter)
            if current_lang_iter and model[current_lang_iter][0] == lang:
                lang_iter = current_lang_iter
        if lang_iter:                    
            word_iter = model.iter_children(lang_iter)
            while word_iter and str(model[word_iter][0]) != str(word):
                word_iter = model.iter_next(word_iter)
            if word_iter and str(model[word_iter][0]) == str(word):
                self.word_completion.get_selection().select_iter(word_iter)            
                word_path = model.get_path(word_iter)
                self.word_completion.scroll_to_cell(word_path)
                return True
        return False

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
        article_view.set_buffer(self.create_article_text_buffer())
        handler = article_view.connect("motion_notify_event", self.on_mouse_motion)        
        article_view.set_data("handlers", [handler])
        return article_view            
    
    def create_article_text_buffer(self):
        buffer = gtk.TextBuffer()
        buffer.create_tag("b", weight = pango.WEIGHT_BOLD)
        buffer.create_tag("i", style = pango.STYLE_ITALIC)
        buffer.create_tag("u", underline = True)
        buffer.create_tag("f", style = pango.STYLE_ITALIC, foreground = "darkgreen")
        buffer.create_tag("r", underline = pango.UNDERLINE_SINGLE, foreground = "brown4")
        buffer.create_tag("url", underline = pango.UNDERLINE_SINGLE, foreground = "steelblue4")
        tag_t = buffer.create_tag("t", weight = pango.WEIGHT_BOLD, foreground = "darkred")
        if self.font:
            font_desc = pango.FontDescription(self.font)
            if font_desc:
                tag_t.set_property("font-desc", font_desc)
        buffer.create_tag("sup", rise = 2, scale = pango.SCALE_XX_SMALL)
        handler1 = buffer.connect("mark-set", self.article_text_selection_changed)
        handler2 = buffer.connect("mark-deleted", self.article_text_selection_changed)
        buffer.set_data("handlers", (handler1, handler2))
        tag_sub = buffer.create_tag("sub", rise = -2, scale = pango.SCALE_XX_SMALL)
        return buffer     
    
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
            tag_name = tag.get_property("name")
            if tag_name == "r" or tag_name == "url":
                is_ref = True
                break
        cursor = gtk.gdk.Cursor(gtk.gdk.HAND2) if is_ref else None
        text_window.set_cursor(cursor)
        return False
        
    def select_dict_file(self, widget):
        if not self.file_chooser_dlg:
            self.file_chooser_dlg = self.create_file_chooser_dlg()
            self.file_chooser_dlg.set_title("Open Dictionary")
        response = self.file_chooser_dlg.run()
        self.file_chooser_dlg.hide()        
        if response == gtk.RESPONSE_OK:
            fileName = self.file_chooser_dlg.get_filename()
            self.open_dict(fileName)
        
    def create_file_chooser_dlg(self):
        dlg = gtk.FileChooserDialog(parent = self.window, action = gtk.FILE_CHOOSER_ACTION_OPEN)        
        dlg.add_button( gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        dlg.add_button( gtk.STOCK_OPEN, gtk.RESPONSE_OK)        
        if self.last_dict_file_location:
            dlg.set_filename(self.last_dict_file_location)        
        return dlg
    
    def open_dict_worker(self):
        while True:
            file = self.open_q.get()
            try:
                dict = sdict.SDictionary(file)
                gobject.idle_add(self.update_status_display, dict.title)
                dict.load()
                self. add_dict(dict)
            except Exception, e:
                self.report_open_error(e)
            finally:
                self.open_q.task_done()
    
    def report_open_error(self, error):
        self.open_errors.append(error)
    
    def open_dicts_thread(self, *files):
        for file in files:
            self.open_q.put(file)
        self.open_q.join()
        gobject.idle_add(self.open_dicts_done)
    
    def open_dicts_done(self):
        self.hide_status_display()
        if len(self.open_errors) > 0:
            self.show_error("Open Failed", self.errors_to_text(self.open_errors))
            self.open_errors = None        
        if self.select_word_on_open:
            word, lang = self.select_word_on_open
            self.select_word_on_open = None
        else:
            word, lang = self.get_selected_word()
        self.update_completion(self.word_input.child.get_text(), (word, lang))
        
    def open_dict(self, file):
        self.open_dicts([file])
                
    def open_dicts(self, files):
        self.open_errors = []
        open_dict_thread = Thread(target = self.open_dicts_thread, args = files)
        open_dict_thread.setDaemon(True)
        open_dict_thread.start()
        self.show_status_display('Please wait...', 'Loading')
    
    def show_status_display(self, message, title = None):
        self.status_display = gtk.MessageDialog(self.get_dialog_parent())  
        self.status_display.set_title(title)   
        self.status_display.set_markup(message)
        self.status_display.set_position(gtk.WIN_POS_CENTER_ALWAYS)
        #for reasons unknown the label used for text is selectable, shows cursor and comes up with text selected
        self.make_labels_unselectable(self.status_display.vbox)
        self.status_display.run()
        
    def make_labels_unselectable(self, container):
        for child in container.get_children():
            if isinstance(child, gtk.Label):
                child.set_selectable(False)
            if isinstance(child, gtk.Container):
                self.make_labels_unselectable(child) 
        
    def update_status_display(self, message):
        if self.status_display:
            self.status_display.set_markup(message)
            
    def hide_status_display(self):
        self.status_display.destroy();
        self.status_display = None

    def show_error(self, title, text):
        dlg = gtk.MessageDialog(parent=self.window, flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_CLOSE, message_format=text)
        dlg.set_title(title)
        dlg.run()
        dlg.destroy()
    
    def add_dict(self, dict):
        if (self.dictionaries.has(dict)):
            print "Dictionary is already open"
            return
        self.last_dict_file_location = dict.file_name
        self.dictionaries.add(dict)
        gobject.idle_add(self.add_to_menu_remove, dict)
        gobject.idle_add(self.update_title)
        
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
        dict.close(save_index = False)
        dict.remove_index_cache_file()
        self.update_completion(self.word_input.child.get_text(), (word, lang))
        self.update_title()
        
    def get_tab_for_dict(self, dict_key):
        if self.dict_key_to_tab.has_key(dict_key):
            tab_child = self.dict_key_to_tab[dict_key]
            return self.tabs.page_num(tab_child)
        return None

    def show_dict_info(self, widget):        
        info_dialog = dictinfo.DictInfoDialog(self.dictionaries.get_dicts(), parent = self.window)
        info_dialog.run()
        info_dialog.destroy()
        
    def show_about(self, widget):
        dialog = gtk.AboutDialog()
        dialog.set_position(gtk.WIN_POS_CENTER)
        dialog.set_name(app_name)
        dialog.set_version(version)
        dialog.set_copyright("(C) 2006-2007 Igor Tkach\nPortions contributed by Sam Tygier")
        dialog.set_website("http://sdictviewer.sf.net/")
        dialog.set_comments("Distributed under terms and conditions of GNU Public License Version 3")
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
        