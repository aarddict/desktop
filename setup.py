from setuptools import setup, find_packages
import sys, os
try:
    import py2exe
except:
    print 'py2exe is not installed'
    py2exe_options = {}
else:
    import os
    import glob
    from py2exe.build_exe import py2exe as build_exe
    
    class Collector(build_exe):
        def copy_extensions(self, extensions):
            build_exe.copy_extensions(self, extensions)
            
            # Create subdir where the
            # Python files are collected.
            full = os.path.join(self.collect_dir, 'aarddict')
            if not os.path.exists(full):
                self.mkpath(full)
                
            # Copy the files to the collection dir.
            # Also add the copied file to the list of compiled
            # files so it will be included in zipfile.
            for f in glob.glob('aarddict/*.cfg'):
                name = os.path.basename(f)
                self.copy_file(f, os.path.join(full, name))
                self.compiled_files.append(os.path.join('aarddict', name))
    py2exe_options = {
        'cmdclass': {'py2exe': Collector}        
        }

# files to install
inst_icons_26   = [ 'icons/hicolor/26x26/hildon/aarddict.png' ]
inst_icons_40   = [ 'icons/hicolor/40x40/hildon/aarddict.png' ]
inst_icons_64   = [ 'icons/hicolor/scalable/hildon/aarddict.png' ]
inst_desktop    = [ 'desktop/aarddict.desktop']

import aarddict

setup(
    name = aarddict.__name__,
    version = aarddict.__version__,
    packages = find_packages(),
    windows=[{
        'script': 'run',
        'icon_resources': [(0, 'windows/aarddict.ico')],
        }
    ], 
       
    entry_points = {
        'gui_scripts': ['aarddict = aarddict:main']
    },

    install_requires = ['PyICU >= 0.8.1', 
                        'simplejson'],
    package_data = {
             'aarddict': ['*.cfg']
    },
    data_files   =     
    [
       (os.path.join(sys.prefix,'share/icons/hicolor/26x26/apps'), inst_icons_26),
       (os.path.join(sys.prefix,'share/icons/hicolor/40x40/apps'), inst_icons_40),
       (os.path.join(sys.prefix,'share/pixmaps'), inst_icons_64),
       (os.path.join(sys.prefix,'share/icons/hicolor/64x64/apps'), inst_icons_64),
       (os.path.join(sys.prefix,'share/applications'), inst_desktop)
    ],      
    author = "Igor Tkach",
    author_email = "itkach@aarddict.org",
    description =  '''Aard Dictionary is a dictionary application providing offline 
    access to dictionaries, Wikipedia and other reference materials.''',
    license = "GPL 3",
    keywords = ['aarddict', 'dict', 'dictionary', 'maemo', 'netbook'],
    url = "http://aarddict.org",  
    classifiers=[
                 'Development Status :: 3 - Alpha',
                 'Operating System :: OS Independent',
                 'Programming Language :: Python',
                 'License :: OSI Approved :: GNU General Public License (GPL)',
                 'Topic :: Utilities',
                 'Environment :: X11 Applications :: GTK'
    ],
    options = {
        'py2exe' : {
            'packages': 'encodings',
            'includes': 'cairo, pango, pangocairo, atk, gobject',
            },
        'sdist': {
            'formats': 'zip',
            }
        },
    **py2exe_options    
)

