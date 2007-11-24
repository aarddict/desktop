import sdictviewer
from . import sdict

def can_open(file_name):
    before, sep, after = file_name.rpartition(".")
    return after == 'dct'

def open(file_name):
    return sdict.SDictionary(file_name)

def create_article_formatter(text_buffer_factory, internal_link_callback, external_link_callback):
    return sdictviewer.articleformat.ArticleFormat(text_buffer_factory, internal_link_callback, external_link_callback)
