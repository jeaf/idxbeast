idxbeast - full text indexer
============================

idxbeast is a simple content indexer written (mostly) in Python. It parses
local text files and index their contents into a SQLite database. The database
can later be searched either from the command line or from a web server.

Dependencies
------------

Before running idxbeast, make sure you have all the required dependencies
installed on your system.

### Required

* **Another Python SQLite Wrapper** ([http://code.google.com/p/apsw/](http://code.google.com/p/apsw/))

  Even though Python natively supports most SQLite features, some of the newer
  APIs are not supported, such as BLOB I/O (which is used by idxbeast).  APSW
  gives access to the entire SQLite API.

* **Unidecode** ([https://pypi.python.org/pypi/Unidecode](https://pypi.python.org/pypi/Unidecode))

  Unidecode converts unicode text to ASCII in a manner similar to what a human
  with a U.S. keyboard would do. This is used by idxbeast for "flattening"
  input texts, which allows for words such as "mangé" and "mange" to map to the
  same word.

* **pywin32** ([http://sourceforge.net/projects/pywin32](http://sourceforge.net/projects/pywin32))

  A very useful module for Windows-specific Python scripts. idxbeast uses it
  for COM communication with the Microsoft Outlook application.

* **PyYAML** ([http://pyyaml.org/wiki/PyYAML](http://pyyaml.org/wiki/PyYAML))

  The idxbeast configuration file is written in the YAML syntax.

### Optional

The following dependencies are required to build the idxlib.dll optimization
C library. That library is optional, and as of this writing it is not completed
nor functional.

* **TCC** ([http://bellard.org/tcc/](http://bellard.org/tcc/))

  TCC means "Tiny C Compiler". This is the only tested compiler for the
  optional idxlib.dll C library.

* **make for Windows** ([http://unxutils.sourceforge.net/](http://unxutils.sourceforge.net/))

  A Makefile is provided for building the idxlib.dll library. The make utility
  can be found in the GNU utilities for Win32 package.

Compilation
-----------

No compilation is required for basic idxbeast usage. However, an experimental
idxlib.dll library can be compiled to provide faster text indexing
capabilities. As of this writing, the library is incomplete and non-functional.

To compile idxlib.dll, simply run the make utility from inside a command prompt
located into the idxbeast directory. idxbeast will automatically use the
optimized library for indexing once it has been built.

Configuration
-------------

A YAML file is used to define idxbeast configuration parameters. That file is
located under ~\.idxbeast\settings.yaml.

Usage
-----

### Indexing

todo

Acknowledgements
----------------

* idxbeast uses the SQLite C amalgamation files for the idxlib optimized C
  library. The two required files (sqlite3.c and sqlite3.h) are included in
  the idxbeast source distribution.

* idxbeast uses the Bottle Web Framework (http://bottlepy.org) to implement a
  basic web server. The bottle.py file is included in the idxbeast source
  distribution.

* The Fowler-Noll-Vo hash (FNV) C implementation used by idxbeast comes almost
  as is from the reference implementation on the FNV homepage:
  http://www.isthe.com/chongo/tech/comp/fnv/. All needed files are included in
  the idxbeast source distribution.

* The idxbeast image was adapted from
  http://commons.wikimedia.org/wiki/File:Chaos_Monster_and_Sun_God.png.

