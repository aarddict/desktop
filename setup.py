from setuptools import setup, find_packages
import sys, os

# files to install
inst_icons_26   = [ '../icons/hicolor/26x26/hildon/aarddict.png' ]
inst_icons_40   = [ '../icons/hicolor/40x40/hildon/aarddict.png' ]
inst_icons_64   = [ '../icons/hicolor/scalable/hildon/aarddict.png' ]
inst_desktop    = [ '../desktop/aarddict.desktop']

setup(
    name = "aarddict",
    version = '0.7.0',
    packages = find_packages(),
    entry_points = {
        'console_scripts': ['aardcompile = aardtools.compiler:main'],                   
        'gui_scripts': ['aarddict = aarddict:main']
    },

    install_requires = ['PyICU >= 0.8.1', 
                        'mwlib == 0.8.4.dev', 
                        'lxml >= 2.0', 
                        'simplejson'],

    package_data = {
        '': ['*.txt'],
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
    author_email = "itkach@gmail.com",
    description =  '''Aarddict is a dictionary application providing offline 
    access to dictionaries, Wikipedia and other reference materials.''',
    license = "GPL 3",
    keywords = ['aarddict', 'dict', 'dictionary', 'maemo'],
    url = "http://code.google.com/p/aarddict",  
    classifiers=[
                 'Development Status :: 3 - Alpha',
                 'Operating System :: OS Independent',
                 'Programming Language :: Python',
                 'License :: OSI Approved :: GNU General Public License (GPL)',
                 'Topic :: Utilities',
                 'Environment :: X11 Applications :: GTK'
    ]    
)

