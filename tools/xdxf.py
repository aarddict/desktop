import sys
from lxml import etree

class XDXFParser():
    
    def __init__(self, header, handle_article):
        self.header = header
        self.handle_article = handle_article

    def _text(self, element, tags, offset=0):
        txt = ''
        start = offset
        if element.text: 
            txt += element.text
        for c in element:            
            txt += self._text(c, tags, offset + len(txt)) 
        end = start + len(txt)
        tags.append([element.tag, start, end, dict(element.attrib)])
        if element.tail:
            txt += element.tail
        return txt
        
    def parse(self, f):
        for event, element in etree.iterparse(f):
            if element.tag == 'description':
                self.header[element.tag] = element.text.encode('utf-8')
                element.clear()
                
            if element.tag == 'full_name':
                self.header['title'] = element.text.encode('utf-8')
                element.clear()
    
            if element.tag == 'xdxf':    
                self.header['article_language'] = element.get('lang_to').encode('utf-8')
                self.header['index_language'] = element.get('lang_from').encode('utf-8')
                self.header['format'] = element.get('format').encode('utf-8')
                element.clear()
    
            if element.tag == 'ar':
                tags = []
                txt = self._text(element, tags)
                try:
                    title = element.find('k').text.encode('utf-8')            
                    self.handle_article(title, txt.encode('utf-8'), tags)
                except:
                    sys.stderr.write('\nSkipping bad article\n')
                finally:
                    element.clear()                        
