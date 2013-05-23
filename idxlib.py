#coding: latin-1

from   ctypes import *
import hashlib
import os
import struct
import time

def fnv_python(s):
    """
    Compute the 64 bit FNV hash of a string. The hash is interpreted as a
    signed integer because SQLite uses signed integers for the ROWID (the hash
    will be used as the ROWID).

    >>> fnv_python('')
    -3750763034362895579L
    >>> fnv_python('a')
    -5808556873153909620L
    >>> fnv_python('aa')
    620444549055354551L
    >>> fnv_python('abcd')
    -281581062704388899L
    >>> fnv_python('foobar')
    -8821353812377114648L
    >>> long(fnv_python('\xd5\x6b\xb9\x53\x42\x87\x08\x36'))
    0L
    >>> fnv_python('delta') == lib.fnv('delta')
    True
    >>> fnv_python('289uy4r98#delta') == lib.fnv('289uy4r98#delta')
    True
    """
    h = 14695981039346656037L # 64 bit offset basis
    for c in s:
        h ^= ord(c)
        h *= 1099511628211L # 64 bit FNV prime
        h &= 0xFFFFFFFFFFFFFFFF
    return c_longlong(h).value # Return as a signed long long so it can be used
                               # as a SQLite ROWID.

try:
    # Load the C library
    lib = cdll.idxlib
    lib.fnv.argtypes = [c_char_p]
    lib.fnv.restype = c_longlong

    # Set the public fnv function to point to lib.fnv
    fnv = lib.fnv
except:
    # Could not load the library, use Python implementation
    fnv = fnv_python

def perf_test():
    start_time = time.clock()
    for i in range(100000):
        fnv_python('shdfklaiugrliagwrligbaw98ry9a8w7uf9a8w')
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

    perf_test()
    return

    os.system('make')

    lib = cdll.idxlib
    lib.fnv.argtypes = [c_char_p, POINTER(c_uint), POINTER(c_uint)]

    #s = u"testéà"
    #e = s.encode('utf-32')
    #lib.index(e, len(e) / 4);
    #s = u""
    #e = s.encode('utf-32')
    #lib.index(e, len(e) / 4);
    #s = u"abc ceci testé abc"
    #e = s.encode('utf-32')
    #lib.index(e, len(e) / 4);

    with open('testdata_donjuan.txt', 'r') as f:
        s = f.read()
    e = s.encode('utf-32')
    lib.index(e, len(e) / 4);

if __name__ == '__main__':
    main()

