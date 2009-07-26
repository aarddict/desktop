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
            
            # Copy the files to the collection dir.
            # Also add the copied file to the list of compiled
            # files so it will be included in zipfile.
            all_files = ([f for f in glob.glob('aarddict/*.cfg')] + 
                         [f for f in glob.glob('aarddict/locale/*/*/*.mo')])
            for f in all_files:
                
                dirname = os.path.dirname(f)
                collect_subdir = os.path.join(self.collect_dir, dirname)
                if not os.path.exists(collect_subdir):
                    self.mkpath(collect_subdir)
                
                self.copy_file(f, collect_subdir)
                self.compiled_files.append(f)

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

    install_requires = ['PyICU >= 0.8', 
                        'simplejson'],
    package_data = {
             'aarddict': ['*.cfg', 'locale/*/*/*.mo']
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
    description = 'Aard Dictionary is a multiplatform dictionary '
    'and offline Wikipedia reader.',
    license = "GPL 3",
    keywords = ['aarddict', 'dict', 'dictionary', 'maemo', 'netbook'],
    url = "http://aarddict.org",  
    classifiers=[
                 'Development Status :: 4 - Beta',
                 'Operating System :: OS Independent',
                 'Programming Language :: Python',
                 'License :: OSI Approved :: GNU General Public License (GPL)',
                 'Topic :: Utilities',
                 'Environment :: X11 Applications :: GTK'
    ],
    options = {
        'py2exe' : {
            'skip_archive': True,
            'packages': 'encodings',
            'includes': 'cairo, pango, pangocairo, atk, gobject, gtk, gtk.keysyms',
            'dll_excludes': ['MSVCR80.dll']
            },
        'sdist': {
            'formats': 'zip',
            }
        },
    **py2exe_options    
)

