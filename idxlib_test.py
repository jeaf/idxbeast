#coding: latin-1

from ctypes import *

import build
build.build()

lib = cdll.idxlib
lib.fnv.argtypes = [c_char_p, POINTER(c_uint), POINTER(c_uint)]

low  = c_uint()
high = c_uint()
res  = lib.fnv("abc", byref(low), byref(high))
print '{0:x} {1:x}'.format(low.value, high.value)
res  = lib.fnv("chongo was here", byref(low), byref(high))
print '{0:x} {1:x}'.format(low.value, high.value)

s = "testéà"
e = s.encode('utf-32')
lib.index(e, len(s) + 1);
s = ""
e = s.encode('utf-32')
lib.index(e, len(s) + 1);

