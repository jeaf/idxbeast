#coding: latin-1

from ctypes import *
import os

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

