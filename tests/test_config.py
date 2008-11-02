#coding: utf-8
from aarddict import ui

def test_config_read_list():
    config = ui.Config()
    
    from StringIO import StringIO
    config.readfp(StringIO("""
[testlist]
5 = a 
3 = q
1 = z
10 = b
09 = c
100 = p
    """))          
    result = config.getlist('testlist')
    assert result == ['z', 'q', 'a', 'c', 'b', 'p']
    
def test_config_read_list_when_no_section():
    config = ui.Config()
    result = config.getlist('nosuchsection')
    assert result == []

def test_config_read_list_when_no_values():
    config = ui.Config()
    section = 'testlist'
    config.add_section(section)        
    result = config.getlist(section)
    assert result == []

def test_config_write_list_new_section():
    config = ui.Config()    
    from StringIO import StringIO
    config.setlist('testlist', ['a', 'b', 'c'])
    result = StringIO()
    config.write(result)        
    expected = """
[testlist]
1 = b
0 = a
2 = c    
"""    
    assert result.getvalue().strip() == expected.strip()    
    
def test_config_write_list_section_exists():
    config = ui.Config()
    
    from StringIO import StringIO
    config.readfp(StringIO("""
[testlist]
100 = p
    """))    
    config.setlist('testlist', ['a', 'b', 'c'])
    result = StringIO()
    config.write(result)        
    expected = """
[testlist]
1 = b
0 = a
2 = c    
"""    
    assert result.getvalue().strip() == expected.strip()    