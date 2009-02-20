========================
Release Notes (aarddict)
========================

0.7.2
=====

- Much faster word navigation (`issue #4`_)

- Fixed memory leak (`issue #4`_)

- Visual feedback when link clicked

.. _issue #4: http://bitbucket.org/itkach/aarddict/issue/4

0.7.1
=====

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
=====

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
