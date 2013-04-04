import itertools
import os.path

import string
import unidecode

import core

# Create the translation table used with the str.translate method. This will
# replace all uppercase chars with their lowercase equivalent, and numbers
# and "_" are passed-through as is. All other chars are replaced with a
# space.
translate_table = list(256*'\0')
for c in itertools.chain(string.lowercase, string.digits):
  translate_table[ord(c)] = c
for c_upper, c_lower in zip(string.uppercase, string.lowercase):
  translate_table[ord(c_upper)] = c_lower
translate_table[ord('_')] = '_'
translate_table = ''.join(translate_table)

def build():
   Create the mapping file
  s = ''
  s += 'char charmap[0x10ffff] = {\n'
  for i in range(0, 0x10000, 32):
    for j in range(32):
      c = unidecode.unidecode(unichr(i+j)).lower()
      if not c: c = ' '
      oc = ord(c[0])
      if oc and (oc >= 48 and oc <= 57) or (oc >= 97 and oc <= 122) or oc == 95:
        c = "'{}'".format(c.translate(translate_table)[0])
      else:
        c = ' 0 '
      s += '{:>3},'.format(c)
    s += '\n'
  s += '};'
  print s

if __name__ == '__main__':
  build()

