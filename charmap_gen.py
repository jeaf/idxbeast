# coding=latin-1

"""
Character mapping code generator.

This script generates the C character mapping file used to translate unicode
characters into a reduced set of ASCII characters used for text indexing. It
creates a C array of strings (char*) that will be indexed by the unicode
integer code point. Any unsupported unicode character will map to the empty
string.

The third party unidecode package (https://pypi.python.org/pypi/Unidecode)
package is first used to reduce the unicode character to ASCII. After that,
the string.translate function is used to apply lowercasing, and remove
unindexed characters such as &, $, etc.

Here are a few examples of unicode characters and their ASCII equivalents used
for indexing (note that some unicode characters map to more than one ASCII
character):
  - é: e
  - ç: c
  - A: a
  - °: deg
  - ]: <empty string>
  - ,: <empty string>

Copyright (c) 2013, François Jeannotte.
"""

import itertools
import os.path
import string
import sys

import unidecode

def create_translate_table():
    """
    Create the translation table used with the str.translate method. This will
    replace all uppercase chars with their lowercase equivalent, and numbers
    and "_" are passed-through as is. All other chars are replaced with a
    space.
    """

    # Create the table, initially containing only spaces
    translate_table = list(256*' ')

    # All lowercase letters, digits, and the underscore character go through
    # unmodified (they map to themselves)
    for c in itertools.chain(string.lowercase, string.digits):
        translate_table[ord(c)] = c
    translate_table[ord('_')] = '_'

    # All uppercase letters map to their lowercase counterpart
    for c_upper, c_lower in zip(string.uppercase, string.lowercase):
        translate_table[ord(c_upper)] = c_lower

    # Return the table in the proper format for using with string.translate
    return ''.join(translate_table)

def generate_charmap_code(translate_table):
    """Generate the C code that implements the character map."""

    s = 'char* charmap[0x10000] = {\n'
    for i in range(0, 0x10000, 32):
        for j in range(32):
            c = unidecode.unidecode(unichr(i+j))
            s += '"{}",'.format(c.translate(translate_table).replace(' ', ''))
        s += '\n'
    s += '};'
    return s

def main():
    """Main program entry point."""

    # Check input arguments
    if len(sys.argv) != 2:
        print 'Input arguments error, no output file provided.'
        print
        print 'Usage: charmap_gen.py <outfile>'
        sys.exit(1)

    # Generate the charmap code
    translate_table = create_translate_table()
    charmap_code    = generate_charmap_code(translate_table)

    # Write the code to the output file
    with open(sys.argv[1], 'w') as f:
        f.write(charmap_code)

if __name__ == '__main__':
    main()

