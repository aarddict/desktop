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

import os.path
import pickle

settings_dir  = ".sdictviewer"
app_state_file = "app_state"

def save_app_state(app_state):
    home_dir = os.path.expanduser('~')
    settings_dir_path = os.path.join(home_dir, settings_dir)
    if not os.path.exists(settings_dir_path):
        try:
            os.mkdir(settings_dir_path)
        except:
            pass        
    settings = os.path.join(home_dir, settings_dir, app_state_file)
    try:
        settings_file = file(settings, "w")
        pickle.dump(app_state, settings_file)
        return
    except IOError:
        pass    
    
def load_app_state():
    home_dir = os.path.expanduser('~')
    settings = os.path.join(home_dir, settings_dir, app_state_file)
    app_state = None
    if os.path.exists(settings):        
        settings_file = file(settings, "r")
        app_state = pickle.load(settings_file)
    return app_state
    
class State:    
    def __init__(self, dict_file = None, phonetic_font = None, word = None, history = [], recent = [], dict_files = [], last_dict_file_location = None):
        self.dict_file = dict_file
        self.phonetic_font = phonetic_font
        self.word = word
        self.history = history
        self.recent = recent
        self.dict_files = dict_files
        self.last_dict_file_location = last_dict_file_location