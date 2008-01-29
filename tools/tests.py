#!/usr/bin/env python
import unittest
        
import re
import mediawikiparser

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
