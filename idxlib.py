#coding: latin-1

from   ctypes import *
import hashlib
import os
import struct
import time

import unidecode

import charmap_gen
import core
import varint

translate_table = charmap_gen.create_translate_table()

def fnv_(s):
    """
    Compute the 64 bit FNV hash of a string. The hash is interpreted as a
    signed integer because SQLite uses signed integers for the ROWID (the hash
    will be used as the ROWID).

    >>> fnv_('')
    -3750763034362895579L
    >>> fnv_('a')
    -5808556873153909620L
    >>> fnv_('aa')
    620444549055354551L
    >>> fnv_('abcd')
    -281581062704388899L
    >>> fnv_('foobar')
    -8821353812377114648L
    >>> long(fnv_('\xd5\x6b\xb9\x53\x42\x87\x08\x36'))
    0L
    >>> fnv_('delta') == lib.fnv('delta')
    True
    >>> fnv_('289uy4r98#delta') == lib.fnv('289uy4r98#delta')
    True
    """
    h = 14695981039346656037L # 64 bit offset basis
    for c in s:
        h ^= ord(c)
        h *= 1099511628211L # 64 bit FNV prime
        h &= 0xFFFFFFFFFFFFFFFF
    return c_longlong(h).value # Return as a signed long long so it can be used
                               # as a SQLite ROWID.

def index_(docid, text):
    """
    Index a document, i.e., find all unique words, their frequencies, etc.
    """
    words = dict()
    i = -1 # For empty files, word_cnt will be -1 + 1, thus 0
    for i,w in enumerate(w for w in unidecode.unidecode(text).translate(translate_table).split() if len(w) > 1 and len(w) < 40):
        word_counters = words.setdefault(w, [0,0])
        word_counters[0] += 1
        word_counters[1] += i
    words = dict((core.get_word_hash(w), varint.encode(
                 [docid, cnts[0], int(cnts[1]/cnts[0])]))
                 for w,cnts in words.iteritems())
    return words, i + 1

def lib_index_(docid, text):
    """
    Call library's implementation of index function.
    """

    # Call the library index function with the text encoded in UTF-32. The
    # C library uses the unicode code point to index the charmap directly.
    encoded_text = text.encode('utf-32')
    total_word_cnt = lib.index(docid, encoded_text, len(encoded_text) / 4);

    # Init the iterator, and create the required ctypes variables
    lib.index_iterator_init()
    word_hash = c_longlong()
    word_cnt  = c_uint()
    avg_idx   = c_uint()

    # Loop on the iterator to retrieve all the results
    words = dict()
    while lib.index_iterator_next(byref(word_hash),
                                  byref(word_cnt),
                                  byref(avg_idx)):
        words[word_hash.value] = varint.encode((docid,
                                                word_cnt.value,
                                                avg_idx.value))
    return words, total_word_cnt

try:
    # Load the C library
    lib = cdll.idxlib
    lib.fnv.argtypes    = [c_char_p]
    lib.fnv.restype     = c_longlong
    lib.index.argytypes = [c_uint, POINTER(c_uint), c_uint]
    lib.index.restype   = c_int

    # Set the public functions to point to the library
    fnv   = lib.fnv
    index = lib_index_
except Exception, ex:
    # Could not load the library, use Python implementation
    print 'Could not load library:', ex
    fnv   = fnv_
    index = index_

def perf_test():
    start_time = time.clock()
    for i in range(100000):
        fnv_('shdfklaiugrliagwrligbaw98ry9a8w7uf9a8w')
    elapsed_time = time.clock() - start_time
    print 'Python fnv exec time: {} seconds'.format(elapsed_time)

    start_time = time.clock()
    for i in range(100000):
        lib.fnv('shdfklaiugrliagwrligbaw98ry9a8w7uf9a8w')
    elapsed_time = time.clock() - start_time
    print 'c fnv exec time     : {} seconds'.format(elapsed_time)

    word_hash_struct = struct.Struct('<xxxxxxxxQ')
    start_time = time.clock()
    for i in range(100000):
        word_hash_struct.unpack(hashlib.md5('shdfklaiugrliagwrligbaw98ry9a8w7uf9a8w').digest())[0] & 0x00000000000000000FFFFFFFFFFFFFFF
    elapsed_time = time.clock() - start_time
    print 'Python MD5 exec time: {} seconds'.format(elapsed_time)


def main():

    #print index(8, 'ceci est un test')
    #return
    #perf_test()
    return

if __name__ == '__main__':
    main()

