=====================
Using Aard Dictionary
=====================

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





