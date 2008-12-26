"""
This file is part of AardDict (http://code.google.com/p/aarddict) - 
a dictionary for Nokia Internet Tablets. 

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2006-2008 Igor Tkach
"""
import logging

import functools
import webbrowser 
import time
import os
from xml.sax.saxutils import escape
from threading import Thread
from Queue import Queue
from math import fabs
from collections import defaultdict
from itertools import groupby
from ConfigParser import ConfigParser

from PyICU import Locale, Collator

import pygtk
pygtk.require('2.0')
import gtk 
import pango
import gobject
from gtk.gdk import (_2BUTTON_PRESS, _3BUTTON_PRESS, BUTTON_PRESS, 
                    MOTION_NOTIFY, BUTTON_RELEASE, NO_EXPOSE, EXPOSE, 
                    VISIBILITY_NOTIFY)

import dictinfo 
import articleformat
import dictionary
from dictionary import Dictionary, key

gobject.threads_init()

version = "0.7.0"
app_name = "Aard Dictionary"

class Config(ConfigParser):
        
    def getlist(self, section):
        return ([item[1] for item in sorted(self.items(section), 
                                            key = lambda i: int(i[0]))] 
                if self.has_section(section) else [])
    
    def setlist(self, section, value):
        if self.has_section(section):
            self.remove_section(section)
        self.add_section(section)
        for i, element in enumerate(value):
            self.set(section, str(i), str(element))    
                
def create_scrolled_window(widget):
    scrolled_window = gtk.ScrolledWindow()
    scrolled_window.set_shadow_type(gtk.SHADOW_IN)
    scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    scrolled_window.add(widget)                                
    return scrolled_window

def create_button(stock_id, action, data=None):
    button = gtk.Button(stock = stock_id)
    settings = button.get_settings()
    settings.set_property( "gtk-button-images", True )        
    button.set_label('')
    button.set_image(gtk.image_new_from_stock(stock_id, 
                                              gtk.ICON_SIZE_SMALL_TOOLBAR))
    button.set_relief(gtk.RELIEF_NONE)
    button.set_focus_on_click(False)
    button.connect("clicked", action, data);
    return button  

def block(widget, handler):
    def wrap(f):
        def newFunction(*args, **kw):
            widget.handler_block(handler)
            result = f(*args, **kw)
            widget.handler_unblock(handler)
            return result 
        return newFunction
    return wrap

            

class LangNotebook(gtk.Notebook):
    
    label_pattern = '%s (%d)'
    
    def __init__(self, word_selection_changed):
        gtk.Notebook.__init__(self)
        self.set_tab_pos(gtk.POS_TOP)
        self.set_show_border(True)
        self.word_selection_changed = word_selection_changed
        self.connect("switch-page", self.__page_switched)
    
    def __getitem__(self, index):
        return self.get_nth_page(index)

    def current(self):
        return self[self.get_current_page()]
    
    def word_list(self, lang):
        if lang is None:
            return None
        page = self.__page(lang)
        return page.child if page else None
    
    def langs(self):
        return [page.lang for page in self]
    
    def has_lang(self, lang):
        page = self.__page(lang)
        return True if page else False
    
    def add_lang(self, lang):
        if not self.has_lang(lang):
            word_list = self.__create_word_list()
            model = word_list.get_model()
            label = gtk.Label()
            self.__update_label(label, lang, len(model))
            model.connect("row-inserted", self.__row_inserted, label, lang)
            model.connect("row-deleted", self.__row_deleted, label, lang)
            handler = word_list.get_selection().connect("changed", 
                                                        self.word_selection_changed, 
                                                        lang)
            word_list.selection_changed_handler = handler
            page = create_scrolled_window(word_list)
            page.lang = lang
            self.append_page(page, label)  
            self.set_tab_reorderable(page, True)
        self.show_all()

    def __clear_word_list(self, tab):
        word_list = tab.child
        selection = word_list.get_selection()
        iscurrent = tab == self.current()
        if not iscurrent:
            selection.handler_block(word_list.selection_changed_handler)
        model = word_list.get_model()
        word_list.set_model(None)
        word_list.freeze_child_notify()
        model.clear()
        word_list.set_model(model)
        word_list.thaw_child_notify()
        if not iscurrent:         
            selection.handler_unblock(word_list.selection_changed_handler)

    def clear(self):                        
        self.foreach(self.__clear_word_list)

    def __row_inserted(self, model, path, iter, label, lang):
        self.__update_label(label, lang, len(model))

    def __row_deleted(self, model, path, label, lang):
        self.__update_label(label, lang, len(model))
        
    def __update_label(self, label, lang, count):
        label.set_text(self.label_pattern % (lang, count))
        
    def __page(self, lang):
        for page in self: 
            if page.lang == lang: return page        
                
    def remove_lang(self, lang):
        for page in self:
            if page.lang == lang:
                self.remove_page(self.page_num(page))
                self.queue_draw_area(0,0,-1,-1)
                return
            
    def current_lang(self):
        current = self.current()
        return current.lang if current else None
    
    def set_current_lang(self, lang):
        page = self.__page(lang)
        self.set_current_page(self.page_num(page))
    
    def __create_word_list(self):
        word_list = gtk.TreeView(gtk.ListStore(object))
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(None, cell)
        column.set_cell_data_func(cell, self.__wordlookup_to_text)
        word_list.set_headers_visible(False)
        word_list.append_column(column)
        return word_list

    def __wordlookup_to_text(self, treeviewcolumn, cell_renderer, model, iter):
        wordlookup = model[iter][0]
        cell_renderer.set_property('text', str(wordlookup))
        return  
    
    def __page_switched(self, notebook, page_gpointer, page_num):
        page = self.get_nth_page(page_num)
        self.word_selection_changed(page.child.get_selection(), page.lang)
        
    
class ArticleView(gtk.TextView):

    def __init__(self, drag_handler, selection_changed_callback, 
                 top_article_view=None):
        gtk.TextView.__init__(self)
        self.article = None
        self.drag_handler = drag_handler
        self.set_wrap_mode(gtk.WRAP_WORD)
        self.set_editable(False)        
        self.set_cursor_visible(False)
        self.set_data("handlers", [])
        self.last_drag_coords = None
        self.selection_changed_callback = selection_changed_callback
        self.connect("motion_notify_event", self.on_mouse_motion)
        if not top_article_view:
            self.top_article_view=self
        else:
            self.top_article_view = top_article_view
    
    def set_buffer(self, buffer):
        handlers = self.get_data("handlers")
        if handlers == None:
            #this article view is already discarded
            return
        handler1 = buffer.connect("mark-set", self.selection_changed_callback)
        handler2 = buffer.connect("mark-deleted", self.selection_changed_callback)
        buffer.set_data("handlers", (handler1, handler2))        
        gtk.TextView.set_buffer(self, buffer)
        handler = self.connect_after("event", self.drag_handler)
        handlers.append(handler)

    def connect(self, signal, callback, *userparams):
        handlers = self.get_data("handlers")
        if handlers == None:
            #this article view is already discarded
            return        
        handler = gtk.TextView.connect(self, signal, callback, *userparams)
        handlers.append(handler)
    
    def clear_selection(self):
        b = self.get_buffer()
        b.move_mark(b.get_selection_bound(), b.get_iter_at_mark(b.get_insert()))
    
    def remove_handlers(self):
        self.__remove_handlers(self)
        self.__remove_handlers(self.get_buffer())
        
    def __remove_handlers(self, obj):
        handlers = obj.get_data("handlers")
        for handler in handlers:
            obj.disconnect(handler)
        obj.set_data("handlers", None)
        
    def on_mouse_motion(self, widget, event, data = None):
        cursor = gtk.gdk.Cursor(gtk.gdk.HAND2) if self.pointer_over_ref(widget) else None
        widget.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(cursor)
        return False
    
    def pointer_over_ref(self, textview):
        x, y = textview.get_pointer()                    
        x, y = textview.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, x, y)
        tags = textview.get_iter_at_location(x, y).get_tags()
        for tag in tags:
            tag_name = tag.get_property("name")
            if tag_name == "r" or tag_name == "url" or tag_name == "ref":
                return True
        return False        

class WordLookup(object):
    def __init__(self, read_funcs, lookup_func):
        if read_funcs:            
            self.word = read_funcs[0].title
        else:
            self.word = u''  
        self.read_funcs = read_funcs
        self.lookup_func = lookup_func
                
    def __str__(self):
        return self.word.encode('utf8')

    def __repr__(self):
        return str(self)
    
    def __unicode__(self):
        return self.word

    def notfound(self, article):
        narticle = dictionary.Article(article.title, 
                                  'Redirect to %s not found' % article.redirect, 
                                  dictionary=article.dictionary)        
        return narticle

    def redirect(self, article, level=0):
        redirect = article.redirect
        if redirect:
            logging.debug('Redirect %s ==> %s (level %d)', 
                          article.title, redirect, level)
            if level > 5:
                logging.warn("Can't resolve redirect %s, too many levels", redirect)
                return article            
            for result in self.lookup_func(redirect, uuid=article.dictionary.uuid):
                a = result()
                a.title = result.title
                if a.title == article.title: continue
                return self.redirect(a, level=level+1)
        else:
            return article                

    def do_redirect(self, read_func):
        article = read_func()
        article.title = read_func.title
        rarticle = self.redirect(article)
        return rarticle if rarticle else self.notfound(article)
        
    def articles(self):                    
        return [self.do_redirect(func) for func in self.read_funcs]
    
class LookupCanceled(Exception):        
    pass

class DictViewer(object):

    def blah(self, widget, event, *args):
        if event.keyval == gtk.keysyms.Down:
            self.select_next_word_in_completion()
            return True
        if event.keyval == gtk.keysyms.Up:
            self.select_prev_word_in_completion()
            return True
             
    def __init__(self):
                    
        self.select_word_exact = functools.partial(self.__select_word, eq_func = self.__exact_eq)
        self.select_word_weak = functools.partial(self.__select_word, eq_func = self.__weak_eq)
        self.lookup_stop_requested = False
        self.update_completion_t0 = None
        self.status_display = None
        self.dictionaries = dictionary.DictionaryCollection()
        self.current_word_handler = None                               
        self.window = self.create_top_level_widget()
        
        self.phonetic_font_desc = None
        self.last_dict_file_location = None
        self.recent_menu_items = {}
        self.file_chooser_dlg = None
        self.window_in_fullscreen = False
        self.article_formatter = articleformat.ArticleFormat(self.word_ref_clicked, 
                                                             self.external_link_callback, 
                                                             self.footnote_callback)
        
        self.start_worker_threads()
                                 
        contentBox = gtk.VBox(False, 0)
        self.create_menu_items()
        self.add_menu(contentBox)
                                        
        box = gtk.VBox()        
        
        input_box = gtk.HBox()
        btn_paste = self.actiongroup.get_action('Paste').create_tool_item()
        
        input_box.pack_start(btn_paste, False, False, 0)
        self.word_input = self.create_word_input()
        input_box.pack_start(self.word_input, True, True, 0)
        btn_clear_input = self.actiongroup.get_action('NewLookup').create_tool_item()        
        input_box.pack_start(btn_clear_input, False, False, 2)
        
        box.pack_start(input_box, False, False, 4)
        
        self.word_completion = LangNotebook(self.word_selection_changed)
        box.pack_start(self.word_completion, True, True, 0)

        self.split_pane = gtk.HPaned() 
        contentBox.pack_start(self.split_pane, True, True, 2)                        
        self.split_pane.add(box)
        
        self.tabs = gtk.Notebook()
        self.tabs.set_scrollable(True)
        self.tabs.popup_enable()
        self.tabs.connect("page-added", self.update_copy_article_mi)
        self.tabs.connect("page-removed", self.update_copy_article_mi)
        self.split_pane.add(self.tabs)
        
        self.add_content(contentBox)
        self.update_title()
        self.window.show_all()
        self.word_input.child.grab_focus()
        self.word_input.child.connect("key-press-event", self.blah)
        self.load_app_state()
    
    def _get_word_list(self):
        return self.split_pane.get_child1()
        
    word_list = property(_get_word_list) 
    
    def load_defaults(self):
        import pkgutil
        loader = pkgutil.find_loader(__name__)
        confpath = os.path.join(os.path.dirname(__file__), 'defaults.cfg')
        confdata = loader.get_data(confpath)
        from StringIO import StringIO
        self.config.readfp(StringIO(confdata))
        
    def load_app_state(self, filename = '~/.aarddict/aarddict.cfg'):
        try:                        
            self.config = Config()            
            self.load_defaults()
            self.config.read(os.path.expanduser(filename))                                
            if self.config.has_option('ui', 'input-word'):            
                self.set_word_input(self.config.get('ui', 'input-word'))
            if self.config.has_option('ui', 'article-font-scale'):            
                articleformat.set_scale(self.config.getfloat('ui', 'article-font-scale'))                
            self.lookup_delay = self.config.getint('ui', 'lookup-delay')
            self.article_delay = self.config.getint('ui', 'article-delay')
            self.max_words_per_dict = self.config.getint('ui', 'max-words-per-dict')
            dict_files = self.config.getlist('dictionaries')
            self.open_dicts(dict_files)
            history = self.config.getlist('history')
            history = [s.split(' ', 1) for s in history]            
            [self.add_to_history(w, l) for l, w in history[::-1]]
            self.set_phonetic_font(self.config.get('ui', 'phonetic-font'))
            self.last_dict_file_location = self.config.get('ui', 'last-dict-file-location')
            
            action = self.actiongroup.get_action('ToggleDragSelects')
            action.set_active(self.config.getboolean('ui', 'drag-selects'))
            
            action = self.actiongroup.get_action('ToggleWordList')
            action.set_active(self.config.getboolean('ui', 'show-word-list'))
            self.update_word_list_visibility(action)
#            self.mi_show_word_list.set_active(self.config.getboolean('ui', 'show-word-list'))
#            self.update_word_list_visibility()
        except:
            logging.exception('Failed to load application state')                     
    
    def start_worker_threads(self):
        self.open_q = Queue()
        open_dict_worker_thread = Thread(target = self.open_dict_worker)
        open_dict_worker_thread.setDaemon(True)
        open_dict_worker_thread.start()
        self.update_completion_q = Queue(1)
        update_completion_thread = Thread(target = self.update_completion_worker)
        update_completion_thread.setDaemon(True)
        update_completion_thread.start()
                 
    def update_copy_article_mi(self, notebook = None, child = None, page_num = None):
        copy_article_action = self.actiongroup.get_action('CopyArticle')
        copy_article_action.set_sensitive(notebook.get_n_pages() > 0)
             
    def destroy(self, widget, data=None):
        self.stop_lookup()
        Thread(target = self.save_state_worker).start()
        self.show_status_display("Saving application state...", "Exiting")
        
    def save_state_worker(self):
        
        history = []
        self.word_input.get_model().foreach(self.history_to_list, history)
        self.config.setlist('history', [' '.join((lang, word)) 
                                        for word, lang in history])
        
        dict_files = [dict.file_name for dict in self.dictionaries]
        if not self.config.has_section('ui'):
            self.config.add_section('ui')
        if self.phonetic_font_desc:
            self.config.set('ui', 'phonetic-font', self.phonetic_font_desc.to_string())
        
        word = self.word_input.child.get_text()
        self.config.set('ui', 'input-word', word)

        selected_word, selected_word_lang = self.get_selected_word()
        if self.config.has_section('selection'):
            self.config.remove_section('selection') 
        if selected_word and selected_word_lang:
            self.config.add_section('selection')
            self.config.set('selection', selected_word_lang, str(selected_word))
                
        self.config.setlist('dictionaries', dict_files)
        self.config.set('ui', 'last-dict-file-location', self.last_dict_file_location)
        self.config.set('ui', 'drag-selects', self.actiongroup.get_action('ToggleDragSelects').get_active())
        self.config.set('ui', 'show-word-list', self.actiongroup.get_action('ToggleWordList').get_active())
        self.config.set('ui', 'article-font-scale', articleformat.get_scale())
        langs = [(self.word_completion.page_num(page), page.lang) 
                          for page in self.word_completion]
        langs = [item[1] for item in sorted(langs, key = lambda x: x[0])]
        self.config.set('ui', 'langs', ' '.join(langs))
        
        d = os.path.expanduser('~/.aarddict')
        if not os.path.exists(d):
            os.makedirs(d)
        f = open(os.path.join(d, 'aarddict.cfg'), 'w')        
        self.config.write(f)
        f.close()
        
        errors = []
        for dict in self.dictionaries:
            try:
                dict.close()
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
        return '\n'.join([str(e) for e in errors])
        
    def history_to_list(self, model, path, iter, history_list):
        word, lang = model[iter]
        history_list.append((word, lang))
        
    def schedule(self, f, timeout, *args):
        if self.current_word_handler:
            gobject.source_remove(self.current_word_handler)
            self.current_word_handler = None
        self.current_word_handler = gobject.timeout_add(timeout, f, *args)                
                        
    def select_first_word_in_completion(self):
        word_list = self.word_completion.current().child
        model = word_list.get_model()
        first_word = model.get_iter_first()
        if first_word: 
            word_list.get_selection().select_iter(first_word)

    def select_next_word_in_completion(self, grab_focus=False):
        self._select_next_completion(self._next_iter_to_select, grab_focus)
        
    def select_prev_word_in_completion(self, grab_focus=False):
        self._select_next_completion(self._prev_iter_to_select, grab_focus)

    def _select_next_completion(self, next_iter_func, grab_focus):
        word_list = self.word_completion.current().child
        model, itr = word_list.get_selection().get_selected()
        to_select = next_iter_func(model, itr)
        if to_select: 
            word_list.get_selection().select_iter(to_select)
        if grab_focus:
            self.word_completion.current().child.grab_focus()        

    def _next_iter_to_select(self, model, itr):
        return model.iter_next(itr) if itr else model.get_iter_first()

    def _prev_iter_to_select(self, model, itr):
        if itr:
            path = model.get_path(itr)
            path_prev = (path[0]-1,)
            return model.get_iter(path_prev)            
        else:
            return model.get_iter(len(model) - 1)
                        
    def word_ref_clicked(self, tag, widget, event, iter, word, dict):
        if self.is_link_click(widget, event, word):
            self.set_word_input(word)
            self.update_completion(word, (word, dict.index_language))
        
    def external_link_callback(self, tag, widget, event, iter, url):
        if self.is_link_click(widget, event, url):
            self.open_external_link(url)

    def footnote_callback(self, tag, widget, event, iter, target_pos):
        top = widget.top_article_view
        if self.is_link_click(top, event, target_pos):
            if hasattr(top, 'backbtn') and top.backbtn:
                top.remove(top.backbtn.parent)
                top.backbtn = None

            r = top.get_visible_rect()
            scroll_window = top.parent
            hval = scroll_window.get_hadjustment().value
            vval = scroll_window.get_vadjustment().value
            scrolled = top.scroll_to_iter(top.get_buffer().get_iter_at_offset(target_pos), 
                                  0.0, use_align=True, xalign=0.0, yalign=0.0)

            if scrolled:                
                def goback(btnwidget, adjustment_values):
                    hval, vval = adjustment_values
                    scroll_window.get_hadjustment().value = hval
                    scroll_window.get_vadjustment().value = vval
                    top.remove(btnwidget.parent)
                    top.backbtn = None
                                                
                backbtn = create_button(gtk.STOCK_GO_UP, goback, (hval, vval))
                child = gtk.EventBox()
                child.add(backbtn)
                 
                w, h = widget.buffer_to_window_coords(gtk.TEXT_WINDOW_WIDGET, 
                                                      r.width, r.height)            
                top.add_child_in_window(child, gtk.TEXT_WINDOW_WIDGET, w - 32 - 2, 2)
                top.backbtn = backbtn
                child.show_all()
  
    def open_external_link(self, url):
        webbrowser.open(url)
    
    def is_link_click(self, widget, event, reference):
        if event.type == BUTTON_PRESS:
            widget.armed_link = (reference, event.get_coords(), event.get_time())
        elif hasattr(widget, "armed_link") and widget.armed_link:
            if event.type == BUTTON_RELEASE and widget.armed_link:
                armed_ref, armed_coords, t0 = widget.armed_link
                x, y = event.get_coords()
                x0, y0 = armed_coords
                widget.armed_link = None
                dt = event.get_time() - t0
                result = (50 < dt < 200 and 
                          fabs(x - x0) < 3 and
                          fabs(y - y0) < 3 and
                          armed_ref is reference)
                return result 
                       
    def set_word_input(self, word, supress_update = True):
        if supress_update: self.word_input.handler_block(self.word_change_handler)
        self.word_input.child.set_text(word)
        self.word_input.child.set_position(-1)    
        if supress_update: self.word_input.handler_unblock(self.word_change_handler) 
    
    def add_to_history(self, word, lang):
        self.word_input.handler_block(self.word_change_handler)        
        model = self.word_input.get_model()
        insert = True;
        for i, row in enumerate(model):
            if word == row[0] and lang == row[1]:
                insert = False;
                break;
        if insert:
            model.insert(None, 0, [word, lang])  
            #self.word_input.set_active(0)
            i = model.get_iter_first()
            i = model.iter_next(i)
            for j in xrange(1, self.word_input.previous_active + 1):
                if i and model.iter_is_valid(i): model.remove(i)            
#        else:
#            self.word_input.set_active(i)
        self.word_input.previous_active = self.word_input.get_active()
        history_size = model.iter_n_children(None)
        if history_size > 10:
            del model[history_size - 1]
        self.word_input.handler_unblock(self.word_change_handler)
    
    def history_back(self):
        model = self.word_input.get_model()
        active = self.word_input.get_active()
        if active == -1:
            sword, slang = self.get_selected_word()
            sword = str(sword)
            logging.debug('selected: %s (%s)', sword, slang)
            for i, (word, lang) in enumerate(model):
                logging.debug('history_back: %s %s (%s)', i, word, lang)
                logging.debug('%s == %s and %s == %s?', sword, word, slang, lang)
                if sword == word and slang == lang:                    
                    active = i
                    logging.debug('Yes')
                    logging.debug('Current position in history: %s %s (%s)', i, word, lang)
                    break
                else:
                    logging.debug('No')
        if active + 1 < len(model):  
            self.word_input.set_active(active + 1)     
            
    def history_forward(self):           
        active = self.word_input.get_active()
        if active > 0:
            self.word_input.set_active(active - 1)                
                
    def clear_tabs(self):
        self.article_formatter.stop()
        while self.tabs.get_n_pages() > 0:            
            last_page = self.tabs.get_nth_page(self.tabs.get_n_pages() - 1)
            article_view = last_page.get_child()
            article_view.remove_handlers()
            self.tabs.remove_page(-1)        
        return False 
        
    def show_article_for(self, wordlookup, lang = None):
        articles = wordlookup.articles()
        self.clear_tabs()
        tooltips = gtk.Tooltips()
        for article in articles:
            article_view = self.create_article_view()            
            scrollable_view = create_scrolled_window(article_view)                
            label = gtk.Label(article.dictionary.title)
            label.set_width_chars(8)
            label.set_ellipsize(pango.ELLIPSIZE_END)
            event_box = gtk.EventBox()
            event_box.add(label)
            event_box.connect("event", self.dict_label_callback)
            event_box.show_all()
            tooltips.set_tip(event_box, article.dictionary.title)
            self.tabs.append_page(scrollable_view, event_box)
            self.tabs.set_tab_label_packing(scrollable_view, 
                                            True, True, gtk.PACK_START)
            self.tabs.set_menu_label_text(scrollable_view, article.dictionary.title)
            self.article_formatter.apply(article, article_view)
            self.add_to_history(str(wordlookup), lang)            
        self.tabs.show_all()
    
    def dict_label_callback(self, widget, event):
        if event.type == _2BUTTON_PRESS:
            action = self.actiongroup.get_action('ToggleWordList')
            action.set_active(not action.get_active())
                
    def update_word_list_visibility(self, action):
        if not action.get_active():
            self.word_list.hide()
        else:
            self.word_list.show()    
                        
    def word_selection_changed(self, selection, lang):
        if selection.count_selected_rows() == 0:
            self.clear_tabs()
            return
        model, iter = selection.get_selected()        
        word = model[iter][0]
        self.schedule(self.show_article_for, self.article_delay, word, lang)
    
    def clear_word_input(self, btn, data = None):
        self.word_input.child.set_text('')
        self.word_input.child.grab_focus()
        
    def paste_to_word_input(self, btn, data = None): 
        clipboard = gtk.clipboard_get(gtk.gdk.SELECTION_CLIPBOARD)
        def set_text(clipboard, text, data):
            if text:
                self.word_input.child.set_text(text)
        clipboard.request_text(set_text)
        self.word_input.child.grab_focus()
          
    def get_selected_word(self):
        selected_lang = self.word_completion.current_lang()
        current_word_list = self.word_completion.word_list(selected_lang)
        selected_word = None
        if current_word_list:
            selection = current_word_list.get_selection()
            current_model, selected = selection.get_selected()
            if selected:
                selected_word = current_model[selected][0]
        return (selected_word, selected_lang)
    
    def stop_lookup(self):
        self.lookup_stop_requested = True
        self.update_completion_q.join()
        self.lookup_stop_requested = False
    
    def update_completion_worker(self):
        while True:
            start_word, to_select = self.update_completion_q.get()
            self.update_completion_t0 = time.time()
            try:
                lang_word_list = self.do_lookup(start_word, to_select)
            except LookupCanceled:
                pass
            else:                                
                gobject.idle_add(self.update_completion_callback, 
                                 lang_word_list, to_select, start_word, 
                                 time.time() - self.update_completion_t0)
            self.update_completion_t0 = None
            self.update_completion_q.task_done()

    def do_lookup(self, start_word, to_select):
        lang_word_list = defaultdict(list)

        for item in self.dictionaries.lookup(start_word, 
                                             max_from_one_dict=self.max_words_per_dict):
            time.sleep(0)
            if self.lookup_stop_requested:
                raise LookupCanceled()
            lang_word_list[item.source.index_language].append(item)
        
        for lang, articles in lang_word_list.iteritems():
            collator = Collator.createInstance(Locale(lang))
            collator.setStrength(Collator.QUATERNARY)
            key = lambda a: collator.getCollationKey(a.title).getByteArray()
            articles.sort(key=key)
            lang_word_list[lang] =  [WordLookup(list(g), self.dictionaries.lookup) 
                                     for k, g in groupby(articles, key)] 
        return lang_word_list
            
    def update_completion(self, word, to_select = None):
        self.word_completion.clear()
        self.stop_lookup()
        word = word.lstrip()
        self.update_completion_q.put((word, to_select))  
        return False
    
    def update_completion_callback(self, lang_word_list, to_select, 
                                   start_word, lookup_time):
        for lang in lang_word_list.iterkeys():
            word_list = self.word_completion.word_list(lang)
            model = word_list.get_model()
            word_list.freeze_child_notify()
            word_list.set_model(None)
            [model.append((word,)) for word in lang_word_list[lang]]
            word_list.set_model(model)
            word_list.thaw_child_notify() 
        selected = False
        if to_select:
            word, lang = to_select
            selected = self.select_word(word, lang)
        if (not selected 
            and len(lang_word_list) == 1 
            and len(lang_word_list.values()[0]) == 1):
            self.select_first_word_in_completion()
            selected = True
        if to_select and not selected:
            self.adjust_history()
            
    def adjust_history(self):
        self.word_input.handler_block(self.word_change_handler)
        model = self.word_input.get_model()
        i = model.get_iter_first()
        if i:                
            for j in xrange(0, self.word_input.previous_active):
                model.remove(i)
            self.word_input.set_active(-1)
            self.word_input.previous_active = self.word_input.get_active()
        self.word_input.handler_unblock(self.word_change_handler)            
          

    def create_top_level_widget(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)  
        window.connect("event", self.window_event)  
        window.set_border_width(2)                
        window.resize(640, 480)
        window.set_position(gtk.WIN_POS_CENTER)        
        window.connect("window-state-event", self.on_window_state_change)        
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

    def create_word_input(self):
        word_input = gtk.ComboBoxEntry(gtk.TreeStore(str, str))
        word_input.previous_active = -1
        word_input.clear()
        cell1 = gtk.CellRendererText()
        word_input.pack_start(cell1, False)        
        word_input.set_cell_data_func(cell1, self.format_history_item)
        word_input.child.connect("activate", 
                                 lambda x: self.select_next_word_in_completion(grab_focus=True))
        self.word_change_handler = word_input.connect("changed", 
                                                      self.word_selected_in_history)        
        return word_input
    
    def format_history_item(self, celllayout, cell, model, iter, user_data = None):
        word, lang  = model[iter]
        word = escape(word)
        cell.set_property('markup', '<span>%s</span> <span foreground="darkgrey">(<i>%s</i>)</span>' % (word, lang)) 
        
    def word_selected_in_history(self, widget, data = None):       
        active = self.word_input.get_active()
        if active == -1:
            self.clear_tabs();
            self.schedule(self.update_completion, 
                          self.lookup_delay, 
                          self.word_input.child.get_text())            
            return
        word, lang = self.word_input.get_model()[active]
        #use schedule instead of direct call to interrupt already scheduled update if any
        self.schedule(self.update_completion, 0, word, (word, lang))        
        
    def select_word(self, word, lang):  
        return True if self.select_word_exact(word, lang)\
                    else self.select_word_weak(word, lang)

    def __select_word(self, word, lang, eq_func):     
        word_list = self.word_completion.word_list(lang)
        if word_list:                    
            model = word_list.get_model()
            word_iter = model.get_iter_first()
            while word_iter:
                if eq_func(model[word_iter][0], word):
                    word_list.get_selection().select_iter(word_iter)            
                    word_path = model.get_path(word_iter)
                    word_list.scroll_to_cell(word_path)
                    self.word_completion.set_current_lang(lang)
                    return True
                word_iter = model.iter_next(word_iter)
        return False
    
    def __exact_eq(self, word_lookup1, word_lookup2):
        return str(word_lookup1) == str(word_lookup2)
    
    def __weak_eq(self, word_lookup1, word_lookup2):
        u1 = unicode(word_lookup1)
        u2 = unicode(word_lookup2)
        return key(u1) == key(u2)

    def create_menu_items(self):
        
        accelgroup = gtk.AccelGroup()
        self.window.add_accel_group(accelgroup)
        actiongroup = gtk.ActionGroup('AarddictActionGroup')
        self.actiongroup = actiongroup              
        
        actiongroup.add_toggle_actions([('ToggleWordList', None, '_Word List', '<Control>m',
                                         'Toggles word list', self.update_word_list_visibility),
                                         ('ToggleDragSelects', None, 'Drag _Selects', '<Control>S',
                                         'Toggles drag gesture between select text and article scroll', self.toggle_drag_selects),
                                        ('FullScreen', gtk.STOCK_FULLSCREEN, '_Full Screen',
                                         'F11', 'Toggle full screen mode', self.toggle_full_screen),                                 
                                        ])
        
        actiongroup.add_actions([('Open', gtk.STOCK_OPEN, '_Open...',
                                  '<Control>o', 'Open a dictionary', self.select_dict_file),
                                 ('Info', gtk.STOCK_INFO, '_Info...',
                                  '<Control>i', 'Information about dictionaries', self.show_dict_info),
                                 ('Quit', gtk.STOCK_CLOSE, '_Quit',
                                  '<Control>q', 'Close application', self.destroy),
                                 ('Back', gtk.STOCK_GO_BACK, '_Back',
                                  '<Alt>Left', 'Go back to previous word in history', lambda action: self.history_back()),
                                 ('Forward', gtk.STOCK_GO_FORWARD, '_Forward',
                                  '<Alt>Right', 'Go forward to next word in history', lambda action: self.history_forward()),
                                 ('NextArticle', None, '_Next Article',
                                  '<Alt>bracketright', 'Show next article', lambda action: self.tabs.next_page()),
                                 ('PrevArticle', None, '_Previous Article',
                                  '<Alt>bracketleft', 'Show previous article', lambda action: self.tabs.prev_page()),
                                 ('NextLang', None, 'N_ext Language',
                                  '<Alt>braceright', 'Show next language word list', lambda action: self.word_completion.next_page()),
                                 ('PrevLang', None, 'P_revious Language',
                                  '<Alt>braceleft', 'Show previous language word list', lambda action: self.word_completion.prev_page()),
                                 ('CopyArticle', None, '_Article',
                                  None, 'Copy article text to clipboard', self.copy_article_to_clipboard),
                                 ('CopySelected', gtk.STOCK_COPY, '_Selected Text',
                                  '<Control>c', 'Copy selected text to clipboard', self.copy_selected_to_clipboard),
                                 ('Paste', gtk.STOCK_PASTE, '_Paste',
                                  '<Control>v', 'Paste text from clipboard as word to look up', self.paste_to_word_input),
                                 ('NewLookup', gtk.STOCK_CLEAR, '_New Lookup',
                                  '<Control>n', 'Move focus to word input and clear it', self.clear_word_input),
                                 ('PhoneticFont', None, '_Phonetic Font...',
                                  None, 'Select font for displaying phonetic transcription', self.select_phonetic_font),
                                 ('IncreaseTextSize', None, '_Increase Text Size',
                                  '<Control>equal', 'Increase size of article text', self.increase_text_size),
                                 ('DecreaseTextSize', None, '_Decrease Text Size',
                                  '<Control>minus', 'Decrease size of article text', self.decrease_text_size),
                                 ('ResetTextSize', None, '_Reset Text Size',
                                  '<Control>0', 'Reset size of article text to default', self.reset_text_size),
                                 ('About', gtk.STOCK_ABOUT, '_About',
                                  None, 'About %s' % app_name, self.show_about),
                                 
                                 ])
        
        for action in actiongroup.list_actions():
            action.set_accel_group(accelgroup)
                    
        self.mi_open = actiongroup.get_action('Open').create_menu_item()

        self.mn_remove = gtk.Menu()
        self.mn_remove_item = gtk.MenuItem("_Remove")
        self.mn_remove_item.set_submenu(self.mn_remove)                        
        
        self.mi_info = actiongroup.get_action('Info').create_menu_item()
        self.mi_exit = actiongroup.get_action('Quit').create_menu_item()
        self.mi_about = actiongroup.get_action('About').create_menu_item()
        self.mi_select_phonetic_font = actiongroup.get_action('PhoneticFont').create_menu_item()
        self.mi_increase_text_size = actiongroup.get_action('IncreaseTextSize').create_menu_item()
        self.mi_decrease_text_size = actiongroup.get_action('DecreaseTextSize').create_menu_item()        
        self.mi_reset_text_size = actiongroup.get_action('ResetTextSize').create_menu_item()
        
        self.mi_drag_selects = actiongroup.get_action('ToggleDragSelects').create_menu_item()
        self.mi_show_word_list = actiongroup.get_action('ToggleWordList').create_menu_item()
        self.mi_back = actiongroup.get_action('Back').create_menu_item()
        self.mi_forward = actiongroup.get_action('Forward').create_menu_item()

        self.mi_next_article = actiongroup.get_action('NextArticle').create_menu_item()
        self.mi_prev_article = actiongroup.get_action('PrevArticle').create_menu_item()

        self.mi_next_lang = actiongroup.get_action('NextLang').create_menu_item()
        self.mi_prev_lang = actiongroup.get_action('PrevLang').create_menu_item()

        self.mn_copy = gtk.Menu()
        self.mn_copy_item =gtk.MenuItem("_Copy")
        self.mn_copy_item.set_submenu(self.mn_copy)

        copy_article_action = actiongroup.get_action('CopyArticle')
        copy_article_action.set_sensitive(False);
        self.mi_copy_article_to_clipboard = copy_article_action.create_menu_item()
        
        copy_selected_action = actiongroup.get_action('CopySelected')
        copy_selected_action.set_sensitive(False)
        self.mi_copy_to_clipboard = copy_selected_action.create_menu_item()
        
        self.mn_copy.append(self.mi_copy_article_to_clipboard)
        self.mn_copy.append(self.mi_copy_to_clipboard)

        self.mi_paste = actiongroup.get_action('Paste').create_menu_item()
        self.mi_new_lookup = actiongroup.get_action('NewLookup').create_menu_item()
        full_screen_action = actiongroup.get_action('FullScreen')
        full_screen_action.set_active(self.window_in_fullscreen)
        self.mi_full_screen = full_screen_action.create_menu_item()

    def create_menus(self):           
        mn_dict = gtk.Menu()
        mn_dict_item = gtk.MenuItem("_Dictionary")
        mn_dict_item.set_submenu(mn_dict)        
        
        mn_dict.append(self.mi_open)        
        mn_dict.append(self.mn_remove_item)
        mn_dict.append(self.mi_info)
        mn_dict.append(self.mn_copy_item)
        mn_dict.append(self.mi_paste)
        mn_dict.append(self.mi_new_lookup)
        mn_dict.append(self.mi_exit)

        mn_nav = gtk.Menu()
        mn_nav_item = gtk.MenuItem("_Navigate")
        mn_nav_item.set_submenu(mn_nav)
        mn_nav.add(self.mi_back)
        mn_nav.add(self.mi_forward)
        mn_nav.add(self.mi_prev_article)
        mn_nav.add(self.mi_next_article)
        mn_nav.add(self.mi_prev_lang)
        mn_nav.add(self.mi_next_lang)
        
        mn_help = gtk.Menu()
        mn_help_item = gtk.MenuItem("_Help")
        mn_help_item.set_submenu(mn_help)
        mn_help.add(self.mi_about)
                
        mn_options = gtk.Menu()
        mn_options_item = gtk.MenuItem("_View")
        mn_options_item.set_submenu(mn_options)
        
        mn_options.append(self.mi_select_phonetic_font)
        mn_options.append(self.mi_increase_text_size)
        mn_options.append(self.mi_decrease_text_size)
        mn_options.append(self.mi_reset_text_size)
        mn_options.append(self.mi_drag_selects)
        mn_options.append(self.mi_show_word_list)
        mn_options.append(self.mi_full_screen)
        return (mn_dict_item, mn_nav_item, mn_options_item, mn_help_item)        

    def _update_article_view_children(self, page):
        article_view = page.child
        if article_view.get_children():
            article = article_view.article
            self.article_formatter.apply(article, article_view)
           
    def increase_text_size(self, action):
        scale = articleformat.get_scale()
        self._apply_font_scale(scale*1.1)
        
    def decrease_text_size(self, action):
        scale = articleformat.get_scale()
        self._apply_font_scale(scale*0.9)

    def reset_text_size(self, action):
        self._apply_font_scale(pango.SCALE_MEDIUM)

    def _apply_font_scale(self, new_scale):
        scale = articleformat.get_scale()
        if new_scale < pango.SCALE_SMALL:
            new_scale = pango.SCALE_SMALL
        if new_scale > pango.SCALE_XX_LARGE:
            new_scale = pango.SCALE_XX_LARGE            
        if new_scale != scale:
            articleformat.set_scale(new_scale)
            self.tabs.foreach(self._update_article_view_children)            

    def on_window_state_change(self, widget, event, *args):             
        if event.new_window_state & gtk.gdk.WINDOW_STATE_FULLSCREEN:
            self.window_in_fullscreen = True
        else:
            self.window_in_fullscreen = False
        full_screen_action = self.actiongroup.get_action('FullScreen')
        full_screen_action.set_active(self.window_in_fullscreen)
    
    def toggle_full_screen(self, action):
        if self.window_in_fullscreen:
            self.window.unfullscreen()
        else:
            self.window.fullscreen()

    def copy_selected_to_clipboard(self, action):
        page_num = self.tabs.get_current_page()
        if page_num < 0:
            return        
        article_view = self.tabs.get_nth_page(page_num).get_child()
        text_buffer = article_view.get_buffer()
        text_buffer.copy_clipboard(gtk.clipboard_get(gtk.gdk.SELECTION_CLIPBOARD))

    def copy_article_to_clipboard(self, action):
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
        if key in self.recent_menu_items:
            old_mi = self.recent_menu_items[key]
            self.mn_remove.remove(old_mi)
            del self.recent_menu_items[key]
        self.recent_menu_items[key] = mi_dict;        
        self.mn_remove.append(mi_dict)
        mi_dict.connect("activate", lambda f: self.remove_dict(dict))
        mi_dict.show_all()

    def update_title(self):
        dict_title = self.create_dict_title()
        title = "%s - %s" % (app_name, dict_title)
        self.window.set_title(title)
        
    def create_dict_title(self):
        size = len(self.dictionaries)
        if size == 0:
            return "No dictionaries"
        return ("%d dictionary") % size if size == 1 else ("%d dictionaries") % size
        
    def create_article_view(self):
        article_view = ArticleView(self.article_drag_handler, 
                                   self.article_text_selection_changed)
#        if self.supports_cursor_changes():        
#            article_view.connect("motion_notify_event", self.on_mouse_motion)
        return article_view   
    
#    def supports_cursor_changes(self):
#        return True         
    
    def article_drag_handler(self, widget, event):
        if self.actiongroup.get_action('ToggleDragSelects').get_active():
            return False        
        
        widget = widget.top_article_view
#        while not isinstance(widget.get_parent(), gtk.ScrolledWindow):
#            widget = widget.get_parent()
        
        type = event.type        
        x, y = coords = widget.get_pointer()        
        if type in (BUTTON_PRESS, _2BUTTON_PRESS, _3BUTTON_PRESS):
            widget.last_drag_coords = coords
            return True
        if type == BUTTON_RELEASE:
            widget.last_drag_coords = None
            return False
        if not widget.last_drag_coords:
            return False
        
        x0, y0 = widget.last_drag_coords
        widget.last_drag_coords = coords        
        scroll_window = widget.get_parent()
        
        hstep = x0 - x
        h = scroll_window.get_hadjustment()
        hvalue = h.get_value() + hstep
        maxhvalue = h.upper - h.page_size
        if hvalue > maxhvalue: hvalue = maxhvalue
        if hvalue < h.lower: hvalue = h.lower
        h.set_value(hvalue)
        
        vstep = y0 - y
        v = scroll_window.get_vadjustment()
        vvalue = v.get_value() + vstep
        maxvvalue = v.upper - v.page_size
        if vvalue > maxvvalue: vvalue = maxvvalue
        if vvalue < v.lower: vvalue = v.lower
        v.set_value(vvalue)
        return type == MOTION_NOTIFY
    
    def article_text_selection_changed(self, *args):
        page_num = self.tabs.get_current_page() 
        sensitive = False       
        if page_num >= 0:            
            article_view = self.tabs.get_nth_page(page_num).get_child()
            text_buffer = article_view.get_buffer()
            sensitive = len(text_buffer.get_selection_bounds()) > 0
        self.actiongroup.get_action('CopySelected').set_sensitive(sensitive)
    
    def on_mouse_motion(self, widget, event, data = None):
        if isinstance(widget.get_parent(), gtk.Table):
            widget = widget.get_parent().get_parent()        
        cursor = gtk.gdk.Cursor(gtk.gdk.HAND2) if self.pointer_over_ref(widget) else None
        widget.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(cursor)
        return False
    
    def pointer_over_ref(self, textview):
        x, y = textview.get_pointer()                    
        x, y = textview.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, x, y)
        tags = textview.get_iter_at_location(x, y).get_tags()
        for tag in tags:
            tag_name = tag.get_property("name")
            if tag_name == "r" or tag_name == "url" or tag_name == "ref":
                return True
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
        dlg = gtk.FileChooserDialog(parent = self.window, 
                                    action = gtk.FILE_CHOOSER_ACTION_OPEN)        
        dlg.add_button( gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        dlg.add_button( gtk.STOCK_OPEN, gtk.RESPONSE_OK)        
        if self.last_dict_file_location:
            dlg.set_filename(self.last_dict_file_location)        
        return dlg
    
    def open_dict_worker(self):
        while True:
            file = self.open_q.get()
            try:
                dict = Dictionary(file)
                gobject.idle_add(self.update_status_display, dict.title)
                self.add_dict(dict)
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
            self.show_error("Open Failed", 
                            self.errors_to_text(self.open_errors))
            self.open_errors = None
        
        if self.config.has_option('ui', 'langs'):
            langs = self.config.get('ui', 'langs').split()           
            self.config.remove_option('ui', 'langs')     
            for page in self.word_completion:
                try:
                    self.word_completion.reorder_child(page, 
                                                   langs.index(page.lang))
                except:
                    logging.warn('Failed to set position for %s', page.lang, 
                                 exc_info=1)                            
        
        if self.config.has_section('selection'):
            for lang in self.config.options('selection'):
                word = self.config.get('selection', lang)                        
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
        self.status_display = gtk.MessageDialog(self.window)  
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
        dlg = gtk.MessageDialog(parent=self.window, 
                                flags=gtk.DIALOG_MODAL, 
                                type=gtk.MESSAGE_ERROR, 
                                buttons=gtk.BUTTONS_CLOSE, 
                                message_format=text)
        dlg.set_title(title)
        dlg.run()
        dlg.destroy()
    
    def add_dict(self, dict):
        if dict in self.dictionaries: 
            return
        self.dictionaries.append(dict)
        def add():
            self.last_dict_file_location = dict.file_name
            self.word_completion.add_lang(dict.index_language)
            self.add_to_menu_remove(dict)
            self.update_title()
        gobject.idle_add(add)
        
    def remove_dict(self, dict):          
        word, lang = self.get_selected_word()
        key = dict.key()
        if key in self.recent_menu_items:
            old_mi = self.recent_menu_items[key]
            self.mn_remove.remove(old_mi)
            del self.recent_menu_items[key]                
        self.dictionaries.remove(dict) 
        current_langs = self.dictionaries.langs()
        view_langs = self.word_completion.langs()
        
        for l in view_langs:
            if l not in current_langs:
                self.word_completion.remove_lang(l)

        dict.close()
        self.update_completion(self.word_input.child.get_text(), (word, lang))
        self.update_title()
        

    def show_dict_info(self, widget):        
        info_dialog = dictinfo.DictInfoDialog(self.dictionaries, 
                                              parent = self.window)
        info_dialog.run()
        info_dialog.destroy()
        
    def show_about(self, action):
        dialog = gtk.AboutDialog()
        dialog.set_position(gtk.WIN_POS_CENTER)
        dialog.set_name(app_name)
        dialog.set_version(version)
        dialog.set_copyright("(C) 2006-2008 Igor Tkach, Jeremy Mortis")
        dialog.set_website("http://code.google.com/p/aarddict")
        dialog.set_comments("Distributed under terms and conditions of GNU Public License Version 3")
        dialog.run()     
        dialog.destroy()
        
    def select_phonetic_font(self, action):
        dialog = gtk.FontSelectionDialog("Select Phonetic Font")        
        if self.phonetic_font_desc:
            dialog.set_font_name(self.phonetic_font_desc.to_string())                        
        if dialog.run() == gtk.RESPONSE_OK:
            self.set_phonetic_font(dialog.get_font_name())
        dialog.destroy()
                
    def set_phonetic_font(self, font_name):
        if font_name:
            self.phonetic_font_desc = pango.FontDescription(font_name)
            articleformat.TAGS_TABLE.lookup('tr').set_property('font-desc', self.phonetic_font_desc)
    
    def toggle_drag_selects(self, action):
        if not action.get_active():
            self.tabs.foreach(lambda scroll_window: 
                              scroll_window.get_child().clear_selection())
    
    def main(self):
        gtk.main()
