# This file is part of Aard Dictionary <http://aarddict.org>.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3
# as published by the Free Software Foundation. 
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License <http://www.gnu.org/licenses/gpl-3.0.txt>
# for more details.
#
# Copyright (C) 2006-2009  Jeremy Mortis, Igor Tkach

import aarddict.ui
import aarddict.dictionary

import threading

import gobject 
import gtk
import pango

def tag(name, **props):
    t = gtk.TextTag(name)
    t.set_properties(**props)
    return t

def strwidth(text):
    view = gtk.TextView()
    layout = view.create_pango_layout(text)
    layout.set_font_description(pango.FontDescription(table_font_family))
    attributes = pango.AttrList()
    attributes.insert(pango.AttrScale(font_scale, 0, len(text)))
    layout.set_attributes(attributes)
    width = layout.get_size()[0]
    return width

font_scale = pango.SCALE_MEDIUM
phonetic_font = 'serif'
table_font_family = 'monospace'

def maketabs(rawtabs):
    char_width = strwidth(' ')
    tabs = pango.TabArray(len(rawtabs), 
                                positions_in_pixels=False)
    for i in range(tabs.get_size()):
        pos = rawtabs[i]
        tabs.set_tab(i, pango.TAB_LEFT, pos*char_width+5*int(font_scale*pango.SCALE))    
    return tabs    


class FormattingStoppedException(Exception):
    def __init__(self):
        self.value = "Formatting stopped"
    def __str__(self):
        return repr(self.value)   

class ArticleFormat:
    class Worker(threading.Thread):        
        def __init__(self, formatter, dict, word, article, article_view):
            super(ArticleFormat.Worker, self).__init__()
            self.dict = dict
            self.word = word
            self.article = article
            self.article_view = article_view
            self.formatter = formatter
            self.stopped = True

        def run(self):
            self.stopped = False
            reftable = dict([((tag.attributes['group'], tag.attributes['id']), tag.start)
                                  for tag in self.article.tags if tag.name=='note'])
            
            text_buffer, tables = self.formatter.create_tagged_text_buffer(self.dict,
                                                                           self.article.text, 
                                                                           self.article.tags,
                                                                           self.article_view, reftable)
            def set_buffer(view, buffer, tables):
                view.set_buffer(buffer)
                for tbl, anchor in tables:
                    view.add_child_at_anchor(tbl, anchor)
                view.show_all()
                            
            if not self.stopped:
                gobject.idle_add(set_buffer, self.article_view, text_buffer, tables)
                self.formatter.workers.pop(self.dict, None)
        
        def stop(self):
            self.stopped = True
            
    def __init__(self, internal_link_callback, external_link_callback, footnote_callback):
        self.internal_link_callback = internal_link_callback
        self.external_link_callback = external_link_callback
        self.footnote_callback = footnote_callback
        self.workers = {}
   
    def stop(self):
        [worker.stop() for worker in self.workers.itervalues()]
        self.workers.clear()
   
    def apply(self, article, article_view):
        article_view.article = article
        dict = article.dictionary
        word = article.title.encode('utf8')        
        current_worker = self.workers.pop(dict, None)
        if current_worker:
            current_worker.stop()
        self.article_view = article_view
        loading = create_article_text_buffer()
        loading.set_text("Loading...")
        article_view.set_buffer(loading)
        self.workers[dict] = self.Worker(self, dict, word, article, article_view)
        self.workers[dict].start()
        
    def create_ref(self, dict, text_buffer, start, end, target):
        ref_tag = text_buffer.create_tag()
        if (target.lower().startswith("http://") or 
            target.lower().startswith("https://")):
            ref_tag.connect("event", self.external_link_callback , target)
            text_buffer.apply_tag_by_name("url", start, end)
        else:
            ref_tag.connect("event", self.internal_link_callback, target, dict)
            text_buffer.apply_tag_by_name("r", start, end)
        text_buffer.apply_tag(ref_tag, start, end) 

    def create_footnote_ref(self, dict, article_view, text_buffer, start, end, target_pos):
        ref_tag = text_buffer.create_tag()
        ref_tag.connect("event", self.footnote_callback , target_pos)
        text_buffer.apply_tag_by_name("ref", start, end)
        text_buffer.apply_tag(ref_tag, start, end) 
        
    def create_tagged_text_buffer(self, dictionary, text, tags, article_view, reftable):
        text_buffer = create_article_text_buffer()
        text_buffer.set_text(text)
                
        tables = []
        for tag in tags:
            start = text_buffer.get_iter_at_offset(tag.start)
            end = text_buffer.get_iter_at_offset(tag.end)
            if tag.name in ('a', 'iref'):
                self.create_ref(dictionary, text_buffer, start, end, 
                                str(tag.attributes['href']))
            elif tag.name == 'kref':
                self.create_ref(dictionary, text_buffer, start, end, 
                                text_buffer.get_text(start, end))
            elif tag.name == 'ref':
                footnote_group = tag.attributes['group']
                footnote_id = tag.attributes['id']
                footnote_key = (footnote_group, footnote_id)
                if footnote_key in reftable:                
                    self.create_footnote_ref(dictionary, article_view, 
                                             text_buffer, start, end, 
                                             reftable[footnote_key])
            elif tag.name == 'tbl':
                tbl = self.create_table(dictionary, article_view, 
                                                text_buffer, tag, start, end, reftable)
                if tbl:                
                    tables.append(tbl)
            elif tag.name == "c":
                if 'c' in tag.attributes:
                    color_code = tag.attributes['c']
                    t = text_buffer.create_tag(None, foreground = color_code)                    
                    text_buffer.apply_tag(t, start, end)
            else:
                text_buffer.apply_tag_by_name(tag.name, start, end)
        text_buffer.apply_tag_by_name('ar', *text_buffer.get_bounds())
        return text_buffer, tables

    def create_table(self, dictionary, article_view, text_buffer, tag, start, end, reftable):
        tabletxt = tag.attributes['text']        
        tabletags = tag.attributes['tags']
        tags = [aarddict.dictionary.to_tag(tagtuple) for tagtuple in tabletags]
        tabletabs = tag.attributes['tabs']
        rawglobaltabs = tabletabs.get('') 
        
        globaltabs = maketabs(rawglobaltabs)        
        tableview = aarddict.ui.ArticleView(article_view.drag_handler, 
                                            article_view.selection_changed_callback)
        tableview.set_wrap_mode(gtk.WRAP_NONE)
        tableview.set_tabs(globaltabs)
        
        buff, tables = self.create_tagged_text_buffer(dictionary, tabletxt, 
                                                      tags, tableview, reftable)
        
        rowtags = [tag for tag in tags if tag.name == 'row']
        for i, rowtag in enumerate(rowtags):
            strindex = str(i)
            if strindex in tabletabs:
                tabs = maketabs(tabletabs[strindex])    
                t = buff.create_tag(tabs=tabs)
                buff.apply_tag(t, 
                                 buff.get_iter_at_offset(rowtag.start), 
                                 buff.get_iter_at_offset(rowtag.end))                
        
        tableview.set_buffer(buff)
        for tbl, anchor in tables:
            tableview.add_child_at_anchor(tbl, anchor)
        
        text_buffer.delete(start, end)            
        anchor = text_buffer.create_child_anchor(start)
        
        return tableview, anchor        
        
        
def create_article_text_buffer():    

    tags = (tag('b',
                weight=pango.WEIGHT_BOLD),
            
            tag('strong',
                weight=pango.WEIGHT_BOLD),
            
            tag('small',
                scale=pango.SCALE_SMALL),
            
            tag('big',
                scale=pango.SCALE_LARGE),
            
            tag('h1',
                weight=pango.WEIGHT_ULTRABOLD, 
                scale=pango.SCALE_X_LARGE, 
                pixels_above_lines=12, 
                pixels_below_lines=6),
            
            tag('h2',
                weight=pango.WEIGHT_BOLD, 
                scale=pango.SCALE_LARGE, 
                pixels_above_lines=6, 
                pixels_below_lines=3),
            
            tag('h3',
                weight=pango.WEIGHT_BOLD, 
                scale=pango.SCALE_MEDIUM, 
                pixels_above_lines=3, 
                pixels_below_lines=2),
            
            tag('h4',
                weight=pango.WEIGHT_SEMIBOLD, 
                scale=pango.SCALE_MEDIUM, 
                pixels_above_lines=3, 
                pixels_below_lines=2),
            
            tag('h5',
                weight=pango.WEIGHT_SEMIBOLD, 
                scale=pango.SCALE_MEDIUM, 
                style=pango.STYLE_ITALIC, 
                pixels_above_lines=3, 
                pixels_below_lines=2),
            
            tag('h6',
                scale=pango.SCALE_MEDIUM, 
                underline=pango.UNDERLINE_SINGLE, 
                pixels_above_lines=3, 
                pixels_below_lines=2),
            
            tag('row',
                background='#eeeeee',
                pixels_above_lines=1,
                pixels_below_lines=1,
                family=table_font_family),
            
            tag('td',
                background='#00ee00',
                pixels_below_lines=2),
            
            tag('i',
                style=pango.STYLE_ITALIC),
            
            tag('em',
                style=pango.STYLE_ITALIC),
            
            tag('u',
                underline=True),
            
            tag('ref',
                underline=True, 
                rise=6*pango.SCALE,                           
                scale=pango.SCALE_X_SMALL, 
                foreground='blue'),
            
            tag('note',
                scale=pango.SCALE_SMALL),
            
            tag('tt',
                family='monospace'),
            
            tag('pos',
                style=pango.STYLE_ITALIC, 
                weight=pango.WEIGHT_SEMIBOLD,
                foreground='darkgreen'),
            
            tag('r',
                underline=pango.UNDERLINE_SINGLE, 
                foreground="brown4"),
            
            tag('url',
                 underline=pango.UNDERLINE_SINGLE, 
                 foreground="steelblue4"),
            
            tag('tr',
                weight=pango.WEIGHT_BOLD, 
                foreground="darkred",
                font=phonetic_font),
            
            tag('p', 
                pixels_above_lines=3, 
                pixels_below_lines=3),
            
            tag('div',
                pixels_above_lines=3, 
                pixels_below_lines=3),
            
            tag('sup',
                rise=6*pango.SCALE, 
                scale=pango.SCALE_X_SMALL),
            
            tag('sub',
                rise=-6*pango.SCALE, 
                scale=pango.SCALE_X_SMALL),
            
            tag('blockquote',
                indent=6),
            
            tag('cite',
                style=pango.STYLE_ITALIC, 
                family='serif', 
                indent=6),
            
            #Key phrase
            tag('k',
                weight=pango.WEIGHT_BOLD, 
                scale=pango.SCALE_LARGE, 
                pixels_above_lines=6, 
                pixels_below_lines=3),
            
            #Direct translation of the key-phrase
            tag('dtrn'),
            
            #Marks the text of an editorial comment
            tag('co',
                foreground="slategray4",
                scale=pango.SCALE_SMALL),
            
            #Marks the text of an example
            tag('ex',
                style=pango.STYLE_ITALIC,
                family='serif',
                foreground="darkblue"),
            
            #Marks an abbreviation that is listed in the <abbreviations> section
            tag('abr',
                weight=pango.WEIGHT_SEMIBOLD,
                style=pango.STYLE_ITALIC,
                foreground="darkred"),
            
            #Tag that marks the whole article
            tag('ar',
                scale=font_scale),
            
            tag('highlight',
                background='#99ccff')
            )            
    
    tagtable = gtk.TextTagTable()
    
    for t in tags:
        tagtable.add(t)
        
    return gtk.TextBuffer(tagtable)
