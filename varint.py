# coding=latin-1

"""
Variable Length Integer Encoding

This module implements the base 128 variable length integer encoding defined
here: https://developers.google.com/protocol-buffers/docs/encoding. This
encoding allow for smaller integers to be encoded in fewer bytes, while
still supporting arbitrary large integers (that will be encoded using more
bytes).

Copyright (c) 2013, François Jeannotte.
"""

def encode(int_list):
    """
    Encode an iterable of integers using an encoding similar to Google Protocol
    Buffer 'varint'.

    >>> from binascii import hexlify as h
    >>> h(encode([]))
    ''
    >>> h(encode([0]))
    '00'
    >>> h(encode([3]))
    '03'
    >>> h(encode([300]))
    'ac02'
    >>> h(encode([300, 300, 300, 3, 0]))
    'ac02ac02ac020300'

    The following examples give an idea of the size differences between
    pickling and varint encoding (both with and without compression) for a
    short sequence of integers.

    >>> import bz2
    >>> import cPickle
    >>> lst = [987,567,19823649185,12345134,3,4,5,99,1,0,123123,2,3,234987987352,3245,23,2,42,5,5,54353,34,35,345,53,452]
    >>> lst.extend([4,1,2,3,123123,123,399999,12,333333333,3,23,1,23,12,345,6,567,8,8,9,76,3,45,234,234,345,45,6765,78])
    >>> lst.extend([987,234234,234,4654,67,75,87,8,9,9,78790,345,345,243,2342,123,342,433,453,4564,56,567,56,75,67])
    >>> len(encode(lst))
    131
    >>> len(bz2.compress(encode(lst)))
    194
    >>> len(cPickle.dumps(lst, protocol=2))
    219
    >>> len(bz2.compress(cPickle.dumps(lst, protocol=2)))
    259
    """
    b = bytearray()
    for i in int_list:
        assert i >= 0
        if i == 0:
            b.append(0)
        else:
            while i > 0:
                b.append(i & 0x7f | 0x80)
                i >>= 7
            b[-1] &= 0x7f
    return b

def decode(buf):  
    """
    Decode provided binary buffer into list of integers, using the varint
    encoding.

    >>> decode(encode([3]))
    [3]
    >>> decode(encode([300]))
    [300]
    >>> decode(encode([300,4]))
    [300, 4]
    >>> decode(encode([300, 99239934294392243432234, 1]))
    [300, 99239934294392243432234L, 1]
    """
    int_list = []
    num      = 0
    i        = 0
    for b in buf:
        num |= (b & 0x7f) << i*7
        if b & 0x80: # Continuation bit is set
            i += 1
        else:
            int_list.append(num)
            num = 0
            i   = 0
    return int_list

