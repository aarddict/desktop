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

import gtk
import pango

class FormatStop(Exception): pass

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
table_bgcolor = gtk.gdk.color_parse('#eeeeee')
int_link_fgcolor = gtk.gdk.color_parse('brown4')
ext_link_fgcolor = gtk.gdk.color_parse('steelblue4')
highlight_bgcolor = gtk.gdk.color_parse('#99ccff')
footnote_fgcolor = gtk.gdk.color_parse('blue')

def maketabs(rawtabs):
    char_width = strwidth(' ')
    tabs = pango.TabArray(len(rawtabs),
                                positions_in_pixels=False)
    for i in range(tabs.get_size()):
        pos = rawtabs[i]
        tabs.set_tab(i, pango.TAB_LEFT, pos*char_width+5*int(font_scale*pango.SCALE))
    return tabs

def create_buffer(article, intcallback, extcallback, footcallback):
    lang = article.dictionary.index_language
    text = article.text
    tags = article.tags
    reftable = dict([((tag.attributes['group'], tag.attributes['id']), tag.start)
                     for tag in article.tags if tag.name=='note'])
    return _new_tagged_buffer(text, tags, reftable, lang, intcallback, extcallback, footcallback)

def _new_tagged_buffer(text, tags, reftable, wordlang, intcallback, extcallback, footcallback, texttagtable=None):
    if interrupted:
        raise FormatStop
    buff = create_article_text_buffer(texttagtable)
    buff.set_text(text)

    tables = []
    for tag in tags:

        if interrupted:
            raise FormatStop

        start = buff.get_iter_at_offset(tag.start)
        end = buff.get_iter_at_offset(tag.end)
        if tag.name in ('a', 'iref'):
            target = str(tag.attributes['href'])
            if (target.lower().startswith("http://") or
                target.lower().startswith("https://")):
                _extref(buff, start, end, target, extcallback)
            else:
                _intref(buff, start, end, target,  wordlang, intcallback)
        elif tag.name == 'kref':
            _intref(buff, start, end, buff.get_text(start, end), wordlang, intcallback)
        elif tag.name == 'ref':
            footnote_group = tag.attributes['group']
            footnote_id = tag.attributes['id']
            footnote_key = (footnote_group, footnote_id)
            if footnote_key in reftable:
                _footref(buff, start, end, reftable[footnote_key], footcallback)
        elif tag.name == 'tbl':
            tabletxt = tag.attributes['text']
            tabletags = tag.attributes['tags']
            tabletabs = tag.attributes['tabs']

            tbl = _new_table(tabletxt, tabletags, tabletabs,
                             buff, start, end, reftable, wordlang, intcallback, extcallback, footcallback, buff.get_tag_table())
            if tbl:
                tables.append(tbl)
        elif tag.name == "c":
            if 'c' in tag.attributes:
                color_code = tag.attributes['c']
                t = buff.create_tag(None, foreground=color_code)
                buff.apply_tag(t, start, end)
        else:
            buff.apply_tag_by_name(tag.name, start, end)
    buff.apply_tag_by_name('ar', *buff.get_bounds())
    return buff, tables

class Table(object):

    def __init__(self, tablebuff, tables, globaltabs, anchor):
        self.tablebuff = tablebuff
        self.tables = tables
        self.globaltabs = globaltabs
        self.anchor = anchor

    def makeview(self, viewfactory):
        tableview = viewfactory()
        tableview.set_wrap_mode(gtk.WRAP_NONE)
        tableview.set_tabs(self.globaltabs)
        tableview.set_buffer(self.tablebuff)
        for table in self.tables:
            tableview.add_child_at_anchor(table.makeview(viewfactory),
                                          table.anchor)
        return tableview

def _new_table(tabletxt, tabletags, tabletabs, buff, start, end,
               reftable, wordlang, intcallback, extcallback, footcallback, texttagtable):
    if interrupted:
        raise FormatStop
    tags = [aarddict.dictionary.to_tag(tagtuple) for tagtuple in tabletags]
    rawglobaltabs = tabletabs.get('')

    globaltabs = maketabs(rawglobaltabs)
    tablebuff, tables = _new_tagged_buffer(tabletxt, tags,
                                           reftable, wordlang, intcallback, extcallback, footcallback, texttagtable=texttagtable)

    rowtags = [tag for tag in tags if tag.name == 'row']
    for i, rowtag in enumerate(rowtags):
        if interrupted:
            raise FormatStop
        strindex = str(i)
        if strindex in tabletabs:
            tabs = maketabs(tabletabs[strindex])
            t = tablebuff.create_tag(tabs=tabs)
            tablebuff.apply_tag(t,
                                tablebuff.get_iter_at_offset(rowtag.start),
                                tablebuff.get_iter_at_offset(rowtag.end))

    buff.delete(start, end)
    anchor = buff.create_child_anchor(start)

    return Table(tablebuff, tables, globaltabs, anchor)


def _intref(buff, start, end, target, targetlang, callback):
    ref_tag = buff.create_tag()
    ref_tag.connect("event", callback, target, targetlang)
    buff.apply_tag_by_name("r", start, end)
    buff.apply_tag(ref_tag, start, end)

def _extref(buff, start, end, target, callback):
    ref_tag = buff.create_tag()
    ref_tag.connect("event", callback , target)
    buff.apply_tag_by_name("url", start, end)
    buff.apply_tag(ref_tag, start, end)

def _footref(buff, start, end, targetpos, callback):
    ref_tag = buff.create_tag()
    ref_tag.connect("event", callback, targetpos)
    buff.apply_tag_by_name("ref", start, end)
    buff.apply_tag(ref_tag, start, end)


def create_article_text_buffer(texttagtable=None):
    if texttagtable is None:
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
                    background_gdk=table_bgcolor,
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
                    underline=pango.UNDERLINE_SINGLE),

                tag('ref',
                     underline=pango.UNDERLINE_SINGLE,
#                     weight=pango.WEIGHT_SEMIBOLD,
                    rise=6*pango.SCALE,
                    scale=pango.SCALE_X_SMALL,
                    foreground_gdk=footnote_fgcolor),

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
                    foreground_gdk=int_link_fgcolor),

                tag('url',
                     underline=pango.UNDERLINE_SINGLE,
                     foreground_gdk=ext_link_fgcolor),

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
                    left_margin=10),

                tag('cite',
                    style=pango.STYLE_ITALIC,
                    family='serif',
                    left_margin=10),

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
                    background_gdk=highlight_bgcolor),

                #The definition of a term, in a definition list.
                tag('dd', 
                    family='serif',
                    style=pango.STYLE_ITALIC),

                #Text font, ignore for now
                tag('font'),
                )

        tagtable = gtk.TextTagTable()

        for t in tags:
            if interrupted:
                raise FormatStop
            tagtable.add(t)
    else:
        tagtable = texttagtable

    return gtk.TextBuffer(tagtable)

interrupted = False
import threading

def stop():
    global interrupted
    interrupted = True
    [thread.join() for thread in threading.enumerate() if thread.getName() == 'format']
    interrupted = False
