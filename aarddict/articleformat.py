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

import gobject 
import gtk
import pango

def strwidth(text):
    view = gtk.TextView()
    row_tag = TAGS_TABLE.lookup('row')
    layout = view.create_pango_layout(text)
    layout.set_font_description(row_tag.get_property('font-desc'))
    attributes = pango.AttrList()
    attributes.insert(pango.AttrScale(get_scale(), 0, len(text)))
    layout.set_attributes(attributes)
    width = layout.get_size()[0]
    return width

def get_scale():    
    return TAGS_TABLE.lookup('ar').get_property('scale')

def set_scale(value):
    TAGS_TABLE.lookup('ar').set_property('scale', value)

class TagTable(gtk.TextTagTable):
    
    def __init__(self):
        gtk.TextTagTable.__init__(self)
        
        tag = gtk.TextTag('b')
        tag.set_properties(weight=pango.WEIGHT_BOLD)
        self.add(tag)

        tag = gtk.TextTag('strong')
        tag.set_properties(weight=pango.WEIGHT_BOLD)
        self.add(tag)        

        tag = gtk.TextTag('small')
        tag.set_properties(scale=pango.SCALE_SMALL)
        self.add(tag)        

        tag = gtk.TextTag('big')
        tag.set_properties(scale=pango.SCALE_LARGE)
        self.add(tag)        

        tag = gtk.TextTag('h1')
        tag.set_properties(weight=pango.WEIGHT_ULTRABOLD, 
                          scale=pango.SCALE_X_LARGE, 
                          pixels_above_lines=12, 
                          pixels_below_lines=6)
        self.add(tag)        


        tag = gtk.TextTag('h2')
        tag.set_properties(weight=pango.WEIGHT_BOLD, 
                          scale=pango.SCALE_LARGE, 
                          pixels_above_lines=6, 
                          pixels_below_lines=3)
        self.add(tag)

        tag = gtk.TextTag('h3')
        tag.set_properties(weight=pango.WEIGHT_BOLD, 
                          scale=pango.SCALE_MEDIUM, 
                          pixels_above_lines=3, 
                          pixels_below_lines=2)
        self.add(tag)

        tag = gtk.TextTag('h4')
        tag.set_properties(weight=pango.WEIGHT_SEMIBOLD, 
                          scale=pango.SCALE_MEDIUM, 
                          pixels_above_lines=3, 
                          pixels_below_lines=2)
        self.add(tag)

        tag = gtk.TextTag('h5')
        tag.set_properties(weight=pango.WEIGHT_SEMIBOLD, 
                          scale=pango.SCALE_MEDIUM, 
                          style=pango.STYLE_ITALIC, 
                          pixels_above_lines=3, 
                          pixels_below_lines=2)
        self.add(tag)

        tag = gtk.TextTag('h6')
        tag.set_properties(scale=pango.SCALE_MEDIUM, 
                          underline=pango.UNDERLINE_SINGLE, 
                          pixels_above_lines=3, 
                          pixels_below_lines=2)
        self.add(tag)

        tag = gtk.TextTag('row')
        tag.set_properties(background='#eeeeee',
                           pixels_above_lines=1,
                           pixels_below_lines=1,
                           family='monospace'
                           )
        self.add(tag)

        tag = gtk.TextTag('td')
        tag.set_properties(background='#00ee00', pixels_below_lines=2)
        self.add(tag)

        tag = gtk.TextTag('i')
        tag.set_properties(style=pango.STYLE_ITALIC)
        self.add(tag)

        tag = gtk.TextTag('em')
        tag.set_properties(style=pango.STYLE_ITALIC)
        self.add(tag)

        tag = gtk.TextTag('u')
        tag.set_properties(underline=True)
        self.add(tag)

        tag = gtk.TextTag('ref')
        tag.set_properties(underline=True, 
                           rise=6*pango.SCALE,                           
                           scale=pango.SCALE_X_SMALL, 
                           foreground='blue')
        self.add(tag)

        tag = gtk.TextTag('tt')
        tag.set_properties(family='monospace')
        self.add(tag)

        tag = gtk.TextTag('pos')
        tag.set_properties(style=pango.STYLE_ITALIC, 
                           weight=pango.WEIGHT_SEMIBOLD,
                           foreground='darkgreen')
        self.add(tag)

        tag = gtk.TextTag('r')
        tag.set_properties(underline=pango.UNDERLINE_SINGLE, 
                           foreground="brown4")
        self.add(tag)

        tag = gtk.TextTag('url')
        tag.set_properties(underline=pango.UNDERLINE_SINGLE, 
                           foreground="steelblue4")
        self.add(tag)

        tag = gtk.TextTag('tr')
        tag.set_properties(weight=pango.WEIGHT_BOLD, 
                           foreground="darkred")
        self.add(tag)

        tag = gtk.TextTag('p')
        tag.set_properties(pixels_above_lines=3, 
                           pixels_below_lines=3)
        self.add(tag)

        tag = gtk.TextTag('div')
        tag.set_properties(pixels_above_lines=3, 
                           pixels_below_lines=3)
        self.add(tag)
                
        tag = gtk.TextTag('sup')
        tag.set_properties(rise=6*pango.SCALE, 
                           scale=pango.SCALE_X_SMALL)
        self.add(tag)

        tag = gtk.TextTag('sub')
        tag.set_properties(rise=-6*pango.SCALE, 
                           scale=pango.SCALE_X_SMALL)
        self.add(tag)

        tag = gtk.TextTag('blockquote')
        tag.set_properties(indent=6)
        self.add(tag)

        tag = gtk.TextTag('cite')
        tag.set_properties(style=pango.STYLE_ITALIC, 
                           family='serif', 
                           indent=6)
        self.add(tag)


        #Key phrase
        tag = gtk.TextTag('k')
        tag.set_properties(weight=pango.WEIGHT_BOLD, 
                           scale=pango.SCALE_LARGE, 
                           pixels_above_lines=6, 
                           pixels_below_lines=3)
        self.add(tag)
        
        #Direct translation of the key-phrase
        tag = gtk.TextTag('dtrn')
        self.add(tag)        
        

        #Marks the text of an editorial comment
        tag = gtk.TextTag('co')
        tag.set_properties(foreground="slategray4",
                           scale=pango.SCALE_SMALL)
        self.add(tag)        
                        
        #Marks the text of an example
        tag = gtk.TextTag('ex')
        tag.set_properties(style=pango.STYLE_ITALIC,
                           family='serif',
                           foreground="darkblue")
        self.add(tag)        

        #Marks an abbreviation that is listed in the <abbreviations> section
        tag = gtk.TextTag('abr')
        tag.set_properties(weight=pango.WEIGHT_SEMIBOLD,
                           style = pango.STYLE_ITALIC,
                           foreground = "darkred")
        self.add(tag)        

        #Tag that marks the whole article
        tag = gtk.TextTag('ar')
        self.add(tag)        

TAGS_TABLE = TagTable()

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
        loading = self.create_article_text_buffer()
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
        text_buffer = self.create_article_text_buffer()
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

    def maketabs(self, rawtabs):
        char_width = strwidth(' ')
        scale = get_scale()
        tabs = pango.TabArray(len(rawtabs), 
                                    positions_in_pixels=False)
        for i in range(tabs.get_size()):
            pos = rawtabs[i]
            tabs.set_tab(i, pango.TAB_LEFT, pos*char_width+5*int(scale*pango.SCALE))    
        return tabs    

    def create_table(self, dictionary, article_view, text_buffer, tag, start, end, reftable):
        tabletxt = tag.attributes['text']        
        tabletags = tag.attributes['tags']
        tags = [aarddict.dictionary.to_tag(tagtuple) for tagtuple in tabletags]
        tabletabs = tag.attributes['tabs']
        rawglobaltabs = tabletabs.get('') 
        
        globaltabs = self.maketabs(rawglobaltabs)        
        tableview = aarddict.ui.ArticleView(article_view.drag_handler, 
                                            article_view.selection_changed_callback, 
                                            top_article_view=article_view.top_article_view)
        tableview.set_wrap_mode(gtk.WRAP_NONE)
        tableview.set_tabs(globaltabs)
        
        buff, tables = self.create_tagged_text_buffer(dictionary, tabletxt, 
                                                      tags, tableview, reftable)
        
        rowtags = [tag for tag in tags if tag.name == 'row']
        for i, rowtag in enumerate(rowtags):
            strindex = str(i)
            if strindex in tabletabs:
                tabs = self.maketabs(tabletabs[strindex])    
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
        
        
    def create_article_text_buffer(self):
        return gtk.TextBuffer(TAGS_TABLE)
