#!/usr/bin/env python
import pysdic
import sdict
if __name__ == "__main__":    
    viewer = pysdic.SDictViewer()
    dict_file = pysdic.read_last_dict()
    if dict_file:
        viewer.open_dict(dict_file)    
    viewer.main()