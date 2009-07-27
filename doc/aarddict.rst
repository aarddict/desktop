===============
Aard Dictionary
===============

Installation Notes
==================

Windows
-------
On Windows versions earlier than Windows XP SP3 installation of
`Microsoft Visual C++ 2005 Redistributable Package (x86)`_ may be needed.

.. _Microsoft Visual C++ 2005 Redistributable Package (x86): http://www.microsoft.com/downloads/details.aspx?FamilyId=32BC1BEE-A3F9-4C13-9C99-220B62A191EE&displaylang=en


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


Release Notes
=============

0.7.5
-----

- Added command line option to print dictionary metadata.

- Language tabs scroll when dictionaries in many languages are open.

- Display Wikipedia language code in article tab title.

- When article found in multiple dictionaries select tab with article
  from most recently used dictionary.

- Added ability to verify dictionary data integrity:
  :menuselection:`Dictionary --> Verify`.

- Fixed redirects: some redirects previously were resolving
  incorrectly because weak string matching (base characters only) was
  used.

- Added ability to select string matching strength:
  :menuselection:`Dictionary --> Match`.

- Render previously ignored ``dd`` tag often used in Wikipedia
  articles in serif italic font.

- Implemented links to article sections.

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
