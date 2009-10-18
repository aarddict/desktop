===============
Aard Dictionary
===============

Installation Notes
==================

Windows
-------
If starting the application results in error message like this::

  This application has failed to start because the application
  configuration is incorrect. Reinstalling the application may fix this
  problem. 

or

::

  The application has failed to start because its side-by-side
  configuration is incorrect. Please see the application event log for
  more detail. 

most likely `Microsoft Visual C++ 2008 SP1 Redistributable Package (x86)`_
needs to be installed.

On Windows earlier than Windows XP SP3 users may also need to install
`Microsoft Visual C++ 2005 Redistributable Package (x86)`_. 

.. _Microsoft Visual C++ 2005 Redistributable Package (x86): http://www.microsoft.com/downloads/details.aspx?FamilyId=32BC1BEE-A3F9-4C13-9C99-220B62A191EE&displaylang=en

.. _Microsoft Visual C++ 2008 SP1 Redistributable Package (x86): http://www.microsoft.com/downloads/details.aspx?familyid=A5C84275-3B97-4AB7-A40D-3802B2AF5FC2&displaylang=en


User Interface Language
=======================
Currently Aard Dictionary interface is available in English (default) and
Russian. User interface language should be selected automatically
based on system's locale. System settings can be overridden by
starting Aard Dictionary from command line like this::

  $ LANG=ru_RU.UTF-8 aarddict

If specified locale is not available this will result in GTK warning

::

  (process:12326): Gtk-WARNING **: Locale not supported by C library.
	  Using the fallback 'C' locale.

followed by a stack trace and Aard Dictionary will fail to
start. Corresponding locale will need to be installed. For example, in
Ubuntu 9.04 the following command will fix the error::

  $ sudo locale-gen ru


Fonts
=====

Aard Dictionary's JSON article format supports special tag for marking
up phonetic transcription. Font for the article text marked as
phonetic transcription can be assigned through :menuselection:`View
--> Phonetic Font...` menu.  Often phonetic transcription is written
with characters from `International Phonetic Alphabet`_
(IPA). Phonetic transcription in IPA can also be found in many
Wikipedia articles. To have IPA symbols displayed properly you may
want to install one of the excellent IPA fonts available at
http://scripts.sil.org.

You also may need to install additional fonts if you use dictionaries
that use script not available on your system. `WAZU JAPAN's Gallery of
Unicode Fonts`_ is an excellent resource for various unicode fonts.

To install fonts on Maemo simply create ``/home/user/.fonts``
directory and copy font files there. New fonts should now appear in
font selection dialog.

If you don't like or know how to copy font files into
``/home/user/.fonts`` you may install `Doulos SIL Font package`_ with
Maemo Application Manager.

.. _`Doulos SIL Font package`: http://aarddict.org/dists/diablo/user/binary-armel/ttf-sil-doulos_4.104-1maemo_all.deb
.. _International Phonetic Alphabet: http://en.wikipedia.org/wiki/International_Phonetic_Alphabet
.. _`WAZU JAPAN's Gallery of Unicode Fonts`: http://www.wazu.jp/

Building Mac OS X App
=====================

Mac OS X application bundle can be built with py2app_ for Aard
Dictionary 0.8.0 and newer. 

- Install MacPorts_

- Install Python 2.6::

    sudo port install python26 +no_tkinter +ucs4

  Change environment to make this Python version default::

    sudo port install python_select
    sudo python_select python26
 
  Make sure Python 2.6 you just installed runs indeed when you type
  ``python`` (you mae need to open a new terminal for
  ``python_select`` to take effect).
 

- Install PyQT4::

    sudo port install py26-pyqt4
   
  This should bring in py26-sip and qt4-mac as dependencies. Qt4
  compilation takes several hours and requires a lot of disc space
  (around 6-8 Gb).
  
- Install py2app::

    sudo port install py26-py2app

- Install PyICU. This is a bit tricky because MacPorts 1.8.1 includes
  ICU 4.3.1 and PyICU doesn't seem to build with that. It looks like 
  ``py26-pyicu @0.8.1`` port was added when ICU was at 4.2.0 and it
  probably worked then. In any case, PyICU 0.8.1 only claims to work
  with ICU 3.6 and 3.8, so it is best to install and activate older
  ICU port - 3.8.1.

- Copy :file:`aarddict.py` recipe (and :file:`__init__.py`) for py2app
  from ``macosx`` to installed py2app package directory::

    cp macosx/py2app/recipes/*.py /opt/local/Library/Frameworks/Python.framework/Versions/2.6/lib/python2.6/site-packages/py2app/recipes/ 
  
  This recipe is same as for `numpy` and other libraries that have
  package data and won't work if put in zip archive. 

- Finally, run py2app_::

    python setup.py py2app

- Remove unused debug binaries::
  
    find dist/ -name "*_debug*" -print0 | xargs -0 rm
  
  A number of unused Qt frameworks gets included in final app (QtDesigner,
  QtSql etc.) but they can't be removed since they are linked in
  :file:`_qt.so`.

.. _py2app: http://svn.pythonmac.org/py2app/py2app/trunk/doc/index.html
.. _MacPorts: http://www.macports.org/

Release Notes
=============

0.7.6
-----

- Include license, documentation, icons and desktop files in source
  distribution generated by ``setup.py``.

- Added ability to open online Wikipedia article in a browser
  (:menuselection:`Navigate --> Online Article`) and to copy article
  URL (:menuselection:`Dictionary --> Copy --> Article URL`).

- Open all volumes of the same dictionary when one volume is open
  if other volumes are in the same directory.

- Fixed auto selecting article from most recently used dictionary (this
  didn't always work with multi volume dictionaries since volume id
  was used instead of dictionary id).

- Remove :kbd:`Control-f` key binding for history forward and
  :kbd:`Control-b` for history back in Hildon UI, use
  :kbd:`Shift-Back` and :kbd:`Back` instead. 

- Windows version now uses Python 2.6.

- Windows installer updated: by default Aard Dictionary now goes into
  `Aard Dictionary` group, shortcuts to web site, forum, and
  uninstaller are created.

0.7.5
-----

- Added command line option to print dictionary metadata.

- Language tabs scroll when dictionaries in many languages are open.

- Display Wikipedia language code in article tab title.

- When article found in multiple dictionaries select tab with article
  from most recently used dictionary (`issue #1`_).

- Added ability to verify dictionary data integrity:
  :menuselection:`Dictionary --> Verify`.

- Fixed redirects: some redirects previously were resolving
  incorrectly because weak string matching (base characters only) was
  used.

- Added ability to select string matching strength:
  :menuselection:`Dictionary --> Match`.

- Render previously ignored ``dd`` tag often used in Wikipedia
  articles in serif italic font.

- Implemented links to article sections (`issue #6`_).

- Highlight current item in word lookup history dropdown list.

- Better lookup history navigation: previously if link followed was
  already in history that history item whould be activated resulting
  in confusing result of subsequent `Back` or `Forward` actions.

- Link sensitivity tweaks to reduce unintended clicks when finger
  scrolling articles on tablet.

- Fixed handling of articles with multiple tables in same position
  (resulted in application crash on Windows).

- Properly limit matched word list for multivolume dictionaries.

- Python 2.5 .deb is now installable on Ubuntu 8.04 LTS.   


.. _issue #6: http://bitbucket.org/itkach/aarddict/issue/6
.. _issue #1: http://bitbucket.org/itkach/aarddict/issue/1

0.7.4
-----

- Customizable table rows background

- Added Russian translation

0.7.3
-----

- Customizable link colors (`issue #2`_)

- Updated default link colors (`issue #2`_)

- +/- keys on N800/N810 change article text size (`issue #3`_)

- Article finger scrolling and link sensitivity tweaks

.. _issue #2: http://bitbucket.org/itkach/aarddict/issue/2
.. _issue #3: http://bitbucket.org/itkach/aarddict/issue/3

0.7.2
-----

- Much faster word navigation (`issue #4`_)

- Fixed memory leak (`issue #4`_)

- Visual feedback when link clicked

.. _issue #4: http://bitbucket.org/itkach/aarddict/issue/4

0.7.1
-----

- Better redirects.

- Better dictionary information display in info dialog and window
  title.

- Added `Lookup Box` action - move focus to word input field and
  select it's content (bound to :kbd:`Ctrl+L`).

- Place cursor at the beginning of article text buffer - helps make
  `Maemo bug 2469`_ less annoying (scrolling to cursor on every text
  view size change).

- Fixed glitch in articles tabs display (event box for articles tab
  labels wasn't invisible, looked bad on Maemo and Windows).

.. _Maemo bug 2469: https://bugs.maemo.org/show_bug.cgi?id=2469

0.7.0
-----

Initial release. Changes compared to `SDict Viewer`_:

- New binary dictionary format

- New article format

- Use `PyICU`_/`ICU`_ for Unicode collation

- Updated UI

.. _PyICU: http://pyicu.osafoundation.org
.. _ICU: http://www.icu-project.org
.. _SDict Viewer: http://sdictviewer.sourceforge.net

Major user visible differences:

- Lenient search (case-insensitive, ignores secondary differences like
  accented characters)

- Faster startup, faster word lookup

- Better link representation in articles, footnote navigation inside
  article

- Better word lookup history navigation

- Updated UI
