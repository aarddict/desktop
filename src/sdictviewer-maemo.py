#!/usr/bin/env python
"""
This file is part of SDict Viewer (http://sdictviewer.sf.net) - 
a dictionary application that allows to use data bases 
in AXMASoft's open dictionary format. 

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2006-2007 Igor Tkach
"""
import sys
sys.path.append('/usr/lib/')

from sdictviewer import ui
import sdictviewer.hildon

osso_c = osso.Context("sdictviewer", ui.version, False)

if __name__ == "__main__":    
    viewer = sdictviewer.hildon.HildonSDictViewer()
    viewer.main()