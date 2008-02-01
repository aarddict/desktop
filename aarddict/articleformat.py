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

import gobject, gtk, pango

class FormattingStoppedException(Exception):

     def __init__(self):
         self.value = "Formatting stopped"
     def __str__(self):
         return repr(self.value)   

import threading

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
            text_buffer = self.formatter.create_tagged_text_buffer(self.dict, self.article, self.article_view)
            if not self.stopped:
                gobject.idle_add(self.article_view.set_buffer, text_buffer)
                self.formatter.workers.pop(self.dict, None)
        
        def stop(self):
            self.stopped = True
            
    def __init__(self, internal_link_callback, external_link_callback):
        self.internal_link_callback = internal_link_callback
        self.external_link_callback = external_link_callback
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
        if str(target).startswith("http://"):
            ref_tag.connect("event", self.external_link_callback , target)
            text_buffer.apply_tag_by_name("url", start, end)
        else:
            ref_tag.connect("event", self.internal_link_callback, target, dict)
            text_buffer.apply_tag_by_name("r", start, end)
        text_buffer.apply_tag(ref_tag, start, end) 
        
    def create_tagged_text_buffer(self, dict, article, article_view):
        text_buffer = self.create_article_text_buffer()
        text_buffer.set_text(article.text)
        tags = article.tags
        for tag in tags:
            start = text_buffer.get_iter_at_offset(tag.start)
            end = text_buffer.get_iter_at_offset(tag.end)
            if tag.name == "a":
                self.create_ref(dict, text_buffer, start, end, tag.attributes['href'])
            else:
                text_buffer.apply_tag_by_name(tag.name, start, end)
        return text_buffer
        
    def create_article_text_buffer(self):
        buffer = gtk.TextBuffer()
        buffer.create_tag("b", weight = pango.WEIGHT_BOLD)
        buffer.create_tag("strong", weight = pango.WEIGHT_BOLD)
        buffer.create_tag("h1", weight = pango.WEIGHT_ULTRABOLD, scale = pango.SCALE_X_LARGE, pixels_above_lines = 12, pixels_below_lines = 6)
        buffer.create_tag("h2", weight = pango.WEIGHT_BOLD, scale = pango.SCALE_LARGE, pixels_above_lines = 6, pixels_below_lines = 3)
        buffer.create_tag("h3", weight = pango.WEIGHT_BOLD, scale = pango.SCALE_MEDIUM, pixels_above_lines = 3, pixels_below_lines = 2)
        buffer.create_tag("h4", weight = pango.WEIGHT_SEMIBOLD, scale = pango.SCALE_MEDIUM, pixels_above_lines = 3, pixels_below_lines = 2)
        buffer.create_tag("h5", weight = pango.WEIGHT_SEMIBOLD, scale = pango.SCALE_MEDIUM, style = pango.STYLE_ITALIC, pixels_above_lines = 3, pixels_below_lines = 2)
        buffer.create_tag("h6", scale = pango.SCALE_MEDIUM, underline = pango.UNDERLINE_SINGLE, pixels_above_lines = 3, pixels_below_lines = 2)
        buffer.create_tag("i", style = pango.STYLE_ITALIC)
        buffer.create_tag("u", underline = True)
        buffer.create_tag("f", style = pango.STYLE_ITALIC, foreground = "darkgreen")
        buffer.create_tag("r", underline = pango.UNDERLINE_SINGLE, foreground = "brown4")
        buffer.create_tag("url", underline = pango.UNDERLINE_SINGLE, foreground = "steelblue4")
        buffer.create_tag("t", weight = pango.WEIGHT_BOLD, foreground = "darkred")
        buffer.create_tag("sup", rise = 2, scale = pango.SCALE_XX_SMALL)
        buffer.create_tag("sub", rise = -2, scale = pango.SCALE_XX_SMALL)
        return buffer                
