<div align="center">
    <img src="https://s3.amazonaws.com/jeaf/idxbeast/idxbeast_small.jpg"/>
</div>

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

* **Another Python SQLite Wrapper** (<http://code.google.com/p/apsw/>)

  Even though Python natively supports most SQLite features, some of the newer
  APIs are not supported, such as BLOB I/O (which is used by idxbeast).  APSW
  gives access to the entire SQLite API.

* **Unidecode** (<https://pypi.python.org/pypi/Unidecode>)

  Unidecode converts unicode text to ASCII in a manner similar to what a human
  with a U.S. keyboard would do. This is used by idxbeast for "flattening"
  input texts, which allows for words with accents, for exemple, to map to the
  same word without them (e.g., élève maps to eleve).

* **pywin32** (<http://sourceforge.net/projects/pywin32>)

  A very useful module for Windows-specific Python scripts. idxbeast uses it
  for COM communication with the Microsoft Outlook application. It is also
  used for implementing the console user interface.

* **Beautiful Soup** (<http://www.crummy.com/software/BeautifulSoup/>)

  Used to process HTML documents.

### Optional

The following dependencies are required to build the optional idxlib.dll
optimization C library.

* **TCC** (<http://bellard.org/tcc/>)

  TCC means "Tiny C Compiler". This is the only tested compiler for the
  optional idxlib.dll C library.

Compilation
-----------

To compile idxlib.dll, run build.py.

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
4. stats

Testing
-------

doctest is used for testing simple and low-level functions. The `test.py`
script is used to run all tests.

Todo
----

Many features are incomplete, or not even started. This section lists such
features that are either actively being worked on, or may be worked on in the
future.

### Web application

idxbeast provides a rudimentary web application (server.py) built on the Bottle
web framework.  Some effort could be invested in making this web application
more polished and feature-rich.

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
joined with an implicit AND operator. This means that for a document to match,
all words specified in the search string must be present in the document.

It would be interesting to provide an extended search syntax, allowing for more
flexibility in the way indexed documents are searched. For example,

* Provide a OR operator that can be mixed freely with the AND operator. This
  would also require the introduction of parenthesis in the search string to
  properly define precedence.
* Provide a "minus" operator that would allow excluding words.
* Allow for time constraints (e.g., modified after April 15th) to be provided
  in the search string.
* etc.

Acknowledgements
----------------

* idxbeast uses the Bottle Web Framework (<http://bottlepy.org>) to implement a
  basic web server. The bottle.py file is included in the idxbeast source
  distribution.

* idxbeast uses the Fowler-Noll-Vo (FNV) hash:
  <http://www.isthe.com/chongo/tech/comp/fnv/>.

* The idxbeast image was adapted from
  <http://commons.wikimedia.org/wiki/File:Chaos_Monster_and_Sun_God.png>.

* The test data files were taken from Project Gutenberg
  (<http://www.gutenberg.org>)

