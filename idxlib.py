#coding: latin-1

import binascii
from   ctypes import *
import os

try:
    lib = cdll.idxlib
    lib.fnv.argtypes = [c_char_p, POINTER(c_uint), POINTER(c_uint)]
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
        low  = c_uint()
        high = c_uint()
        res  = lib.fnv(s, byref(low), byref(high))
        return (high.value << 32) | low.value
    else:
        h = 14695981039346656037L # 64 bit offset basis
        for c in s:
            h ^= ord(c)
            h *= 1099511628211L # 64 bit FNV prime
            h &= 0xFFFFFFFFFFFFFFFF
        return h

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

    #lib.test()

if __name__ == '__main__':
    main()

