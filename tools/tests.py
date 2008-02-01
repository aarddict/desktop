#!/usr/bin/env python
import unittest
        
import re
import mediawikiparser
from mediawikiparser import MediaWikiParser
import aarddict

class WikiParserTests(unittest.TestCase):

    def setUp(self):
        self.collator = aarddict.pyuca.Collator("aarddict/allkeys.txt", strength = 1)
        self.wiki_str = """
        <mediawiki>
            <siteinfo>
                <sitename>Wikipedia</sitename>
                <base>http://fr.wikipedia.org/boogy</base>
            </siteinfo>
            <page>
                <title>hi&amp;ho</title>
                <text>''blah''
                    [[Image:thing.png|right|See [[thing article|thing text]]]] cows {{go}} bong
                </text>
                </page>
            <page>
                <title>Page 2</title>
                <text>''blah2''
                    [[Image:what]] [[thing article|thing text]]]] bells go moo
                </text>
            </page>
            </x>
        </mediawiki>\n \n \n
        """
        self.parsed_text_1 = '''<p><i>blah</i>\n<img href="thing.png">See <a href="thing article">thing text</a></img> cows {{go}} bong\n</p>'''
        self.parsed_text_2 = '''<p><i>blah2</i>\n<img href="what">Image:what</img> <a href="thing article">thing text</a>]] bells go moo\n</p>'''
        self.parse_results = []
         
    def test_metadata_parsing(self):
       metadata = {}
       consumer = lambda title, text : (title, text)
       self.parser = MediaWikiParser(self.collator, metadata, self.parse_result_consumer)
       self.parser.parseString(self.wiki_str)
       self.assertEqual(metadata, {'index_language': 'fr', 'article_language': 'fr', 'title': 'Wikipedia'})
       self.assertEqual(len(self.parse_results), 2)
       self.assertEqual(self.parse_results[0], ('hi&ho', self.parsed_text_1))
       self.assertEqual(self.parse_results[1], ('Page 2', self.parsed_text_2))
    
    def parse_result_consumer(self, title, text):
       self.parse_results.append((title, text))
        

class WikiTemplateTests(unittest.TestCase):
        
    def test_parse_template_inclusion_with_named_params(self):
        name, params = mediawikiparser.parseTemplate('{{templatename|parname1=parvalue1|parname2=parvalue2}}')  
        self.assertEqual(name, 'templatename')  
        self.assertEqual(params, {'parname1' : 'parvalue1', 'parname2' : 'parvalue2'})

    def test_parse_template_inclusion_with_numbered_params(self):
        name, params = mediawikiparser.parseTemplate('{{templatename|parvalue1|parvalue2}}')  
        self.assertEqual(name, 'templatename')  
        self.assertEqual(params, {1 : 'parvalue1', 2 : 'parvalue2'})

    def test_parse_template_without_params(self):
        name, params = mediawikiparser.parseTemplate('{{templatename}}')  
        self.assertEqual(name, 'templatename')  
        self.assertEqual(params, {})
  
if __name__ == '__main__':
    unittest.main() 
