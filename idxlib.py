#coding: latin-1

import binascii
from   ctypes import *
import hashlib
import os
import struct
import time

try:
    lib = cdll.idxlib
    lib.fnv.argtypes = [c_char_p]
    lib.fnv.restype = c_ulonglong
except:
    lib = None

def fnv(s):
    """
    Compute the FNV hash of a string (64 bit integer). The test data used in
    the first three doctest examples was taken from:
    http://tools.ietf.org/html/draft-eastlake-fnv-05#page-15
    The last doctest example (the one with a result of 0L) comes from the
    zero hash challenges (#8) on the FNV home page:
    http://www.isthe.com/chongo/tech/comp/fnv/index.html#zero-hash
    
    >>> fnv('')
    14695981039346656037L
    >>> fnv('a')
    12638187200555641996L
    >>> fnv('foobar')
    9625390261332436968L
    >>> fnv('\xd5\x6b\xb9\x53\x42\x87\x08\x36')
    0L
    """
    if lib:
        return lib.fnv(s)
    else:
        h = 14695981039346656037L # 64 bit offset basis
        for c in s:
            h ^= ord(c)
            h *= 1099511628211L # 64 bit FNV prime
            h &= 0xFFFFFFFFFFFFFFFF
        return h

def perf_test():
    global lib
    lib = None
    start_time = time.clock()
    for i in range(100000):
        fnv('shdfklaiugrliagwrligbaw98ry9a8w7uf9a8w')
    elapsed_time = time.clock() - start_time
    print 'Python fnv exec time: {} seconds'.format(elapsed_time)

    lib = cdll.idxlib
    start_time = time.clock()
    for i in range(100000):
        fnv('shdfklaiugrliagwrligbaw98ry9a8w7uf9a8w')
    elapsed_time = time.clock() - start_time
    print 'c fnv exec time     : {} seconds'.format(elapsed_time)

    word_hash_struct = struct.Struct('<xxxxxxxxQ')
    start_time = time.clock()
    for i in range(100000):
        word_hash_struct.unpack(hashlib.md5('shdfklaiugrliagwrligbaw98ry9a8w7uf9a8w').digest())[0] & 0x00000000000000000FFFFFFFFFFFFFFF
    elapsed_time = time.clock() - start_time
    print 'Python MD5 exec time: {} seconds'.format(elapsed_time)

def main():

    os.system('make')

    lib = cdll.idxlib
    lib.fnv.argtypes = [c_char_p, POINTER(c_uint), POINTER(c_uint)]

    #low  = c_uint()
    #high = c_uint()
    #res  = lib.fnv("abc", byref(low), byref(high))
    #print '{0:x} {1:x}'.format(low.value, high.value)
    #res  = lib.fnv("chongo was here", byref(low), byref(high))
    #print '{0:x} {1:x}'.format(low.value, high.value)

    #s = u"test��"
    #e = s.encode('utf-32')
    #lib.index(e, len(e) / 4);
    #s = u""
    #e = s.encode('utf-32')
    #lib.index(e, len(e) / 4);
    #s = u"abc ceci test� abc"
    #e = s.encode('utf-32')
    #lib.index(e, len(e) / 4);

    with open('testdata_donjuan.txt', 'r') as f:
        s = f.read()
    e = s.encode('utf-32')
    lib.index(e, len(e) / 4);

    #lib.test()

if __name__ == '__main__':
    main()

