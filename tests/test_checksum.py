from aarddict import dictionary
from os import path

def test_calcsha1():
    test_file =  path.join(path.dirname(__file__), 'emptyfile.bz2')
    hexdigest = dictionary.calcsha1(test_file, 0)
    assert hexdigest == '64a543afbb5f4bf728636bdcbbe7a2ed0804adc2', hexdigest
    
