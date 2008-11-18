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

Copyright (C) 2008  Jeremy Mortis and Igor Tkach
"""
import aarddict.ui
import aarddict.dictionary

import threading
from collections import defaultdict

import gobject 
import gtk
import pango

WRAP_TBL_CLASSES = frozenset(('messagebox', 'metadata', 'ambox'))

class FormattingStoppedException(Exception):
    def __init__(self):
        self.value = "Formatting stopped"
    def __str__(self):
        return repr(self.value)   

def size_allocate(widget, allocation, table):
    w = min(int(0.95*allocation.width), allocation.width - 1)
    table.set_size_request(w, -1)

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
            text_buffer, tables = self.formatter.create_tagged_text_buffer(self.dict, self.article, self.article_view)                        
            
            def set_buffer(view, buffer, tables):
                view.set_buffer(buffer)
                for tbl, anchor in tables:
                    if tbl.fit_to_width:
                        view.connect('size-allocate', size_allocate, tbl)
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
   
    def apply(self, dict, word, article, article_view):
        current_worker = self.workers.pop(dict, None)
        if current_worker:
            current_worker.stop()
        self.article_view = article_view
        loading = self.create_article_text_buffer()
        loading.set_text("Loading...")
        article_view.set_buffer(loading)
        self.workers[dict] = self.Worker(self, dict, word, article, article_view)
        self.workers[dict].start()
        
    def create_ref(self, dict, text_buffer, start, end, target):
        ref_tag = text_buffer.create_tag()
        if target.startswith("http://"):
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
        
    def create_tagged_text_buffer(self, dictionary, raw_article, article_view):
        text_buffer = self.create_article_text_buffer()
        text_buffer.set_text(raw_article.text)
        tags = raw_article.tags
        
        reftable = dict([((tag.attributes['group'], tag.attributes['id']), tag.start)
                          for tag in tags if tag.name=='note'])
        
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
            elif tag.name == 'table':
                tbl = self.create_table(dictionary, article_view, 
                                                text_buffer, tag, start, end)
                if tbl:                
                    tables.append(tbl)
            elif tag.name == "c":
                if 'c' in tag.attributes:
                    color_code = tag.attributes['c']
                    t = text_buffer.create_tag(None, foreground = color_code)                    
                    text_buffer.apply_tag(t, start, end)
            else:
                text_buffer.apply_tag_by_name(tag.name, start, end)
        return text_buffer, tables


    def create_cell_view(self, dictionary, article_view, text, tags, wrap):
        class A(object):
            def __init__(self, text, tags):
                self.text = text
                self.tags = tags
        raw_article = A(text, [aarddict.dictionary.Tag(name, start, end, attrs) 
                               for name, start, end, attrs in tags])
        
        cell_view = aarddict.ui.ArticleView(article_view.drag_handler, 
                                   article_view.selection_changed_callback, 
                                   article_view.phonetic_font_desc)
        buff, tables = self.create_tagged_text_buffer(dictionary, raw_article, article_view)
        cell_view.set_buffer(buff)
        cell_view.set_wrap_mode(wrap)
        for tbl, anchor in tables:
            cell_view.add_child_at_anchor(tbl, anchor)
        cell_view.show_all()
        
        return cell_view

    def create_table(self, dictionary, article_view, text_buffer, tag, start, end):
        tabledata = tag.attributes['rows']
        tableattrs = tag.attributes['attrs']
        tableclasses = tableattrs.get('class', '').split()
        if 'navbox' in tableclasses:
            return None
        
        table = gtk.Table()
        table.set_property('column-spacing', 5)
        table.set_property('row-spacing', 5)        
        
        i = 0
        rowspanmap = defaultdict(int)
        for row in tabledata:
            rowdata, rowtags = row
            j = 0            
            for cell in rowdata:
                while rowspanmap[j] > 0:
                    rowspanmap[j] = rowspanmap[j] - 1
                    j += 1                    
                text, tags  = cell   
                
                if any((tableclass in WRAP_TBL_CLASSES 
                        for tableclass in tableclasses)):
                    wrap = gtk.WRAP_WORD_CHAR
                    table.fit_to_width = True
                else:
                    wrap = gtk.WRAP_NONE
                    table.fit_to_width = False
                cellwidget = self.create_cell_view(dictionary, article_view, text, tags, wrap)
                cellattrs = [attrs for name, s, e, attrs in tags if name == 'cell'][0]
                cellspan = cellattrs.get('colspan', 1)
                rowspan = cellattrs.get('rowspan', 1)
                for k in range(j, j+cellspan):
                    rowspanmap[k] = rowspan - 1
                table.attach(cellwidget, j, j+cellspan, i, i+rowspan, 
                             xoptions=gtk.EXPAND|gtk.FILL, 
                             yoptions=gtk.EXPAND|gtk.FILL, 
                             xpadding=0, ypadding=0)
                j = j + cellspan                                             
            i = i + 1        
                                      
        text_buffer.delete(start, end)            
        anchor = text_buffer.create_child_anchor(start)
        
        return table, anchor        
        
        
    def create_article_text_buffer(self):
        buffer = gtk.TextBuffer()
        buffer.create_tag("b", weight = pango.WEIGHT_BOLD)        
        buffer.create_tag("strong", weight = pango.WEIGHT_BOLD)
        buffer.create_tag("small", scale = pango.SCALE_SMALL)
        buffer.create_tag("big", scale = pango.SCALE_LARGE)
        
        buffer.create_tag("h1", 
                          weight = pango.WEIGHT_ULTRABOLD, 
                          scale = pango.SCALE_X_LARGE, 
                          pixels_above_lines = 12, 
                          pixels_below_lines = 6)
        buffer.create_tag("h2", 
                          weight = pango.WEIGHT_BOLD, 
                          scale = pango.SCALE_LARGE, 
                          pixels_above_lines = 6, 
                          pixels_below_lines = 3)        
        buffer.create_tag("h3", 
                          weight = pango.WEIGHT_BOLD, 
                          scale = pango.SCALE_MEDIUM, 
                          pixels_above_lines = 3, 
                          pixels_below_lines = 2)
        buffer.create_tag("h4", 
                          weight = pango.WEIGHT_SEMIBOLD, 
                          scale = pango.SCALE_MEDIUM, 
                          pixels_above_lines = 3, 
                          pixels_below_lines = 2)
        buffer.create_tag("h5", 
                          weight = pango.WEIGHT_SEMIBOLD, 
                          scale = pango.SCALE_MEDIUM, 
                          style = pango.STYLE_ITALIC, 
                          pixels_above_lines = 3, 
                          pixels_below_lines = 2)
        buffer.create_tag("h6", 
                          scale = pango.SCALE_MEDIUM, 
                          underline = pango.UNDERLINE_SINGLE, 
                          pixels_above_lines = 3, 
                          pixels_below_lines = 2)
        
        buffer.create_tag("i", style = pango.STYLE_ITALIC)
        buffer.create_tag("em", style = pango.STYLE_ITALIC)
        buffer.create_tag("u", underline = True)
        buffer.create_tag("ref", underline=True, rise=8*pango.SCALE,                           
                          scale=pango.SCALE_XX_SMALL, foreground='blue')
        buffer.create_tag("tt", family = 'monospace')        
        
        buffer.create_tag("pos", 
                          style = pango.STYLE_ITALIC, 
                          weight = pango.WEIGHT_SEMIBOLD,
                          foreground = "darkgreen")
        
        buffer.create_tag("r", 
                          underline = pango.UNDERLINE_SINGLE, 
                          foreground = "brown4")
        
        buffer.create_tag("url", 
                          underline = pango.UNDERLINE_SINGLE, 
                          foreground = "steelblue4")
        
        buffer.create_tag("tr", 
                          weight = pango.WEIGHT_BOLD, 
                          foreground = "darkred")
        
        buffer.create_tag("p", pixels_above_lines=3, pixels_below_lines=3)
        buffer.create_tag("div", pixels_above_lines=3, pixels_below_lines=3)
        
        buffer.create_tag("sup", rise=8*pango.SCALE, scale=pango.SCALE_XX_SMALL)
        buffer.create_tag("sub", rise=-8*pango.SCALE, scale=pango.SCALE_XX_SMALL)
        
        buffer.create_tag("blockquote", indent = 6)
        buffer.create_tag("cite", style=pango.STYLE_ITALIC, 
                          family = 'serif', indent=6)
        
        'Key phrase'
        buffer.create_tag('k', 
                          weight = pango.WEIGHT_BOLD, 
                          scale = pango.SCALE_LARGE, 
                          pixels_above_lines = 6, 
                          pixels_below_lines = 3)        

        'Direct translation of the key-phrase'
        buffer.create_tag('dtrn')
                
        'Marks the text of an editorial comment'
        buffer.create_tag('co',
                          foreground = "slategray4",
                          scale = pango.SCALE_SMALL)
        
        'Marks the text of an example'
        buffer.create_tag('ex',
                          style = pango.STYLE_ITALIC,
                          family = 'serif',
                          foreground = "darkblue")

        'Marks an abbreviation that is listed in the <abbreviations> section'
        buffer.create_tag('abr',
                          weight = pango.WEIGHT_BOLD,
                          style = pango.STYLE_ITALIC,
                          foreground = "darkred")
        
        'Tag that marks the whole article'
        buffer.create_tag('ar')
        
        return buffer                
