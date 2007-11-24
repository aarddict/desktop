import sdictviewer
from . import pdi

def can_open(file_name):
    before, sep, after = file_name.rpartition(".")
    return after == 'pdi'

def open(file_name):
    return pdi.Dictionary(file_name)

def create_article_formatter(text_buffer_factory, internal_link_callback, external_link_callback):
    return sdictviewer.articleformat.ArticleFormat(text_buffer_factory, internal_link_callback, external_link_callback)