#!/usr/bin/env python
"""
This file is part of SDict Viewer (http://sdictviewer.sf.net) - dictionary that uses 
data bases in AXMASoft's open dictionary format. SDict Viewer is distributed under terms 
and conditions of GNU General Public License Version 2. See http://www.gnu.org/licenses/gpl.html
for license details.
Copyright (C) 2006-2007 Igor Tkach
"""
import pysdic
import sdict
if __name__ == "__main__":    
    viewer = pysdic.SDictViewer()
    viewer.main()