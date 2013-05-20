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
  input texts, which allows for words with accents, for exemple, to map to the
  same word.

* **pywin32** ([http://sourceforge.net/projects/pywin32](http://sourceforge.net/projects/pywin32))

  A very useful module for Windows-specific Python scripts. idxbeast uses it
  for COM communication with the Microsoft Outlook application. It is also
  used for implementing the console user interface.

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

Usage
-----

idxbeast is called from the command line in the following manner:

    idxbeast.py <command name> [command arguments]

Detailed usage for each command can be obtained by calling:

    idxbeast.py <command name> -h

The following commands are supported:

1. index
2. search
3. server

Testing
-------

doctest is used for testing simple and low-level functions. The `test.py`
script is used to run all tests. `idxlib_test.py` is used to test the optimized
C library.

Todo
----

Many features are incomplete, or not even started. This section lists such
features that are either actively being worked on, or may be worked on in the
future.

### Web application

idxbeast provides a rudimentary web application (server.py) built on the Bottle
web framework.  Some effort could be invested in making this web application
more polished and feature rich.

### Optimized C library

Work on an experimental optimized C library called idxlib has been started. As
is currently designed, idxbeast.py would call idxlib for each file to index.
Before calling idxlib, idxbeast would read the whole file as unicode, and
convert it to UTF-32. For each file, idxlib expects an array of unicode code
points: 32 bit integers between 0 and 0xFFFF inclusive (assuming a Python
narrow build).  idxlib will index each file, and store the accumulated results.
When some criteria is met (e.g., number of files indexed larger than x), idxlib
will flush the indexed documents to the SQLite database.

### Web pages indexing

Web pages indexing is not supported yet. This could be most useful for intranet
or such networks that aren't indexed by Google.

### Microsoft Outlook contents indexing

idxbeast provides support for indexing the contents of emails from the
Microsoft Outlook application. COM is used to communicate with Outlook, and
retrieve the text of emails.  However, there seems to be a resource leak in the
way idxbeast queries the Outlook API, and after a few hundreds emails, COM
fails to read any more emails with a "out of resource" exception. The Outlook
application is then unresponsive, and must be restarted.

Since I don't use Outlook anymore, debugging of this problem has been put on
hold.

### Extended search syntax

As of this writing, it is only possible to search for one or more words, all
joined with the implicit AND operator. This means that for a document to match, all
words specified in the search string must be present in the document.

It would be interesting to provide an extended search syntax, allowing for more
flexibility in the way indexed documents are searched. For example,

* Provide a OR operator that can be mixed freely with the AND operator. This
  would also require the introduction of parenthesis in the search string to
  properly define precedence.
* Provide a "minus" operator that would allow exluding words.
* Allow for time constraints (e.g., modified after April 15th) to be provided
  in the search string.
* etc.

### Testing

For now testing is somewhat disorganised, and lacking in many respects. The
following are elements that should be improved in the future:

* Provide a test.py main entry point for running all tests, or a subset of the
  tests.
* Include in the source distribution some relatively small test documents that
  can be indexed and for which expected results can be defined.
* Choose a well known package containing many text files (e.g., a specific
  version of the Boost source distribution) that can be used to gather
  performance data.


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

* The test data files were taken from Project Gutenberg
  ([www.gutenberg.org](www.gutenberg.org)).

