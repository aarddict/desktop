import os
import sys

from setuptools import setup, find_packages

import aarddict

try:
    import py2exe
except:
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
            all_files = ([f for f in glob.glob('aarddict/*.tmpl')] +
                         [f for f in glob.glob('aarddict/*.js')] +
                         [f for f in glob.glob('aarddict/*.png')] +
                         [f for f in glob.glob('aarddict/*.css')] +
                         [f for f in glob.glob('aarddict/locale/*/*/*.mo')] +
                         [f for f in glob.glob('aarddict/locale/*.qm')] +
                         [f for f in glob.glob('aarddict/icons/*/*/*/*.png')]
                         )
            for f in all_files:

                dirname = os.path.dirname(f)
                collect_subdir = os.path.join(self.collect_dir, dirname)
                if not os.path.exists(collect_subdir):
                    self.mkpath(collect_subdir)

                self.copy_file(f, collect_subdir)
                self.compiled_files.append(f)

    py2exe_options = {'cmdclass': {'py2exe': Collector}}


def get_setup_args():
    setup_args = setup_common()
    common_options = options_common()
    setup_arg_func = globals().get('setup_'+sys.platform, setup_other) 
    options_func = globals().get('options_'+sys.platform, options_other) 
    setup_args.update(setup_arg_func())
    common_options.update(options_func())
    setup_args['options'] = common_options
    return setup_args
    

def setup_common():
    return dict(version=aarddict.__version__,
                packages=find_packages(),
                install_requires=['PyICU >= 0.8', 'simplejson'],
                package_data={'aarddict': ['locale/*/*/*.mo',
                                           'locale/*.qm',
                                           'aar.css.tmpl',
                                           '*.js',
                                           '*.css',
                                           '*.png',
                                           'icons/*/*/*/*.png']},
                author="Igor Tkach",
                author_email="itkach@aarddict.org",
                description='Aard Dictionary is a multiplatform dictionary '
                              'and offline Wikipedia reader.',
                license="GPL 3",
                keywords=['aarddict', 'dict', 'dictionary', 'maemo', 'netbook'],
                url="http://aarddict.org",
                classifiers=['Development Status :: 4 - Beta',
                             'Operating System :: OS Independent',
                             'Programming Language :: Python',
                             'License :: OSI Approved :: GNU General Public License (GPL)',
                             'Topic :: Utilities',
                             'Environment :: X11 Applications :: GTK'
                             ]
                )

def options_common():
    return {'sdist': {'formats': 'zip'}}

def setup_win32():
    return dict(name=aarddict.__appname__,
                windows=[{'script': 'run',
                          'icon_resources': [(0, 'windows/aarddict.ico')],}],
                **py2exe_options)

def options_win32():
    return dict(py2exe={'skip_archive': True,
                        'packages': 'encodings',
                        'excludes': ['aarddict.ui', 'aarddict.hildonui', 'aarddict.dictinfo',
                                     'multiprocessing', 'xml', 'email'],
                        'includes': ['PyQt4', 'sip', 'PyQt4.QtNetwork'],
                        'dll_excludes': ['MSVCR80.dll', 'MSVCP90.dll']
                        })

def setup_darwin():
    return dict(name=aarddict.__appname__,
                app=["run.py"])

def options_darwin():
    return dict(py2app={'argv_emulation': True,
                        'optimize': 2,
                        'iconfile': 'macosx/aarddict.icns',
                        'excludes': ['aarddict.ui', 'aarddict.hildonui', 'aarddict.dictinfo', 'aarddict.articleformat',
                                     'multiprocessing', 'xml', 'email', 
                                     ],
                        'includes': ['PyQt4', 'PyQt4._qt', 'sip', 'PyQt4.QtNetwork'],
                        })

def setup_other():
    inst_icons_64 = ['aarddict/icons/hicolor/64x64/apps/aarddict.png' ]
    inst_desktop = ['desktop/aarddict.desktop']
    return dict(name=aarddict.__name__,
                entry_points={'gui_scripts': ['aarddict = aarddict:main']},
                data_files=[(os.path.join(sys.prefix,'share/icons/hicolor/64x64/apps'), inst_icons_64),
                            (os.path.join(sys.prefix,'share/applications'), inst_desktop)])

def options_other():
    return {}


setup(**get_setup_args())
