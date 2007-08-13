import re
import time
import gobject
from HTMLParser import HTMLParser
from htmlentitydefs import name2codepoint

class ArticleParser(HTMLParser):
    
    def __init__(self):
        HTMLParser.__init__(self)
        self.replace_map_start = {"t":"[", "br" : "\n", "p" : "\n\t"}
        self.replace_map_end = {"t" : "]", "br" : "\n", "p" : "\n\t"}
        self.replace_only_tags = ["br", "p"]
    
    def prepare(self, word, dict, text_buffer, word_ref_callback):
        self.text_buffer = text_buffer
        self.word_ref_callback = word_ref_callback
        self.word = word
        self.dict = dict
        self.reset()     
        
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        replacement_length = 0
        if self.replace_map_start.has_key(tag):
            replacement = self.replace_map_start.get(tag)
            replacement_length = len(replacement)
            self.append(replacement)
        if tag not in self.replace_only_tags:
            iter = self.text_buffer.get_end_iter()
            iter.backward_chars(replacement_length)
            self.text_buffer.create_mark(tag, iter, True)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.replace_map_end.has_key(tag):
            self.append(self.replace_map_end.get(tag))  
        start_mark = self.text_buffer.get_mark(tag)    
        if start_mark:
            tag_start = self.text_buffer.get_iter_at_mark(start_mark)
            tag_end = self.text_buffer.get_end_iter()
            if tag == "r":
                self.create_ref(tag_start, tag_end)
            self.text_buffer.apply_tag_by_name(tag, tag_start, tag_end)
            self.text_buffer.delete_mark(start_mark)
           
    def handle_data(self, data):
        self.append(data)

    def handle_entityref(self, name):
        if name2codepoint.has_key(name):
            self.append(unichr(name2codepoint[name]))
        else:
            self.append("&"+name)
        
    def append(self, text):
        self.text_buffer.insert(self.text_buffer.get_end_iter(), text)
        
    def create_ref(self, start, end):
        text = self.text_buffer.get_text(start, end)
        ref_text = text.replace("~", self.word)
        ref_tag = self.text_buffer.create_tag()
        ref_tag.connect("event", self.word_ref_callback, ref_text, self.dict)
        self.text_buffer.apply_tag(ref_tag, start, end) 
        
    def error(self, message):
        print "HTML parsing error in article:\n", self.rawdata
        HTMLParser.error(self, message) 
        
import threading

class ArticleFormat:
    class Worker(threading.Thread):        
        def __init__(self, formatter, dict, word, article, article_view, word_ref_callback):
            super(ArticleFormat.Worker, self).__init__()
            self.dict = dict
            self.word = word
            self.article = article
            self.article_view = article_view
            self.word_ref_callback = word_ref_callback
            self.formatter = formatter
            self.stopped = True

        def run(self):
            self.stopped = False
            t0 = time.clock()
            text_buffer = self.formatter.get_formatted_text_buffer_safe(self.dict, self.word, self.article, self.article_view, self.word_ref_callback)
            print "formatting time: ", time.clock() - t0
            if not self.stopped:
                gobject.idle_add(self.article_view.set_buffer, text_buffer)
                del self.formatter.workers[self.dict]
            
        def stop(self):
            self.stopped = True
            del self.formatter.workers[self.dict]
            
    def __init__(self, text_buffer_factory, external_link_callback):
        self.invalid_start_tag_re = re.compile('<\s*[\'\"\w]+\s+')
        self.invalid_end_tag_re = re.compile('\s+[\'\"\w]+\s*>')
        self.text_buffer_factory = text_buffer_factory
        self.external_link_callback = external_link_callback
        self.http_link_re = re.compile("http://[^\s]+", re.UNICODE)
        self.workers = {}
   
    def repl_invalid_end(self, match):
        text = match.group(0)
        return text.replace(">", "&gt;")

    def repl_invalid_start(self, match):
        text = match.group(0)
        return text.replace("<", "&lt;")
   
    def apply(self, dict, word, article, article_view, word_ref_callback):
        if self.workers.has_key(dict):
            self.workers[dict].stop();
        self.article_view = article_view
        loading = self.text_buffer_factory.create_article_text_buffer()
        loading.set_text("Loading...")
        article_view.set_buffer(loading)
        self.workers[dict] = self.Worker(self, dict, word, article, article_view, word_ref_callback)
        self.workers[dict].start()
        
    
    def get_formatted_text_buffer_safe(self, dict, word, article, article_view, word_ref_callback):
        try:
            text_buffer = self.get_formatted_text_buffer(dict, word, article, article_view, word_ref_callback)
        except: 
            article, invalid_start_count = re.subn(self.invalid_start_tag_re, self.repl_invalid_start, article)
            article, invalid_end_count = re.subn(self.invalid_end_tag_re, self.repl_invalid_end, article)
            print "invalid start count: ", invalid_start_count, " invalid end count: ", invalid_end_count, "\n", article     
            try:
                text_buffer = self.get_formatted_text_buffer(dict, word, article, article_view, word_ref_callback)
            except Exception, e:
                text_buffer = self.text_buffer_factory.create_article_text_buffer()
                text_buffer.set_text("(Error occured while formatting this article):\n"+str(e)+"\n"+article)  
        return text_buffer   
        
    def get_formatted_text_buffer(self, dict, word, article, article_view, word_ref_callback):
        text_buffer = self.text_buffer_factory.create_article_text_buffer()
        text_buffer.insert_with_tags_by_name(text_buffer.get_end_iter(), word, "b")
        text_buffer.insert(text_buffer.get_end_iter(), "\n")
        parser =  ArticleParser()          
        parser.prepare(word, dict, text_buffer, word_ref_callback)
        parser.feed(article);
        t0 = time.clock();
        self.parse_http_links(text_buffer)
        print "parsing http links took: ", time.clock() - t0
        return text_buffer
    
    def parse_http_links(self, text_buffer):
        start, end = text_buffer.get_bounds()
        text = text_buffer.get_text(start, end)
        for m in self.http_link_re.finditer(text.decode('utf-8')):
            tag_start = text_buffer.get_iter_at_offset(m.start())
            tag_end = text_buffer.get_iter_at_offset(m.end())
            text_buffer.apply_tag_by_name("url", tag_start, tag_end)
            self.create_external_ref(text_buffer, tag_start, tag_end)
            
    def create_external_ref(self, text_buffer, start, end):
        text = text_buffer.get_text(start, end)
        ref_tag = text_buffer.create_tag()
        ref_tag.connect("event", self.external_link_callback , text)
        text_buffer.apply_tag(ref_tag, start, end)  
