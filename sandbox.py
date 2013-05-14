# coding=latin-1

import array
import binascii
import bz2
import cPickle
import functools
import heapq
import itertools
import pprint
import random
import time
import timeit

def create_huffman_mapping(huffman_tree, code_dict, prefix = ''):
    """
    Create the huffman mapping from a huffman_tree recursively. This function
    is only used from init_word_encoding.
    """

    if len(huffman_tree) == 2:
        code_dict[huffman_tree[1]] = prefix
    else:
        create_huffman_mapping(huffman_tree[1], code_dict, prefix + '0')
        create_huffman_mapping(huffman_tree[2], code_dict, prefix + '1')

def init_word_encoding():
    """
    This function prepares the character mapping that will be used to encode
    words. The first step is to create the huffman coding tree corresponding to
    standard english letter frequencies. Then, the tree is parsed to create a
    mapping between each basic char (a-z0-9_) and its binary encoding string
    (e.g., '001101001010'). Then, the mapping is extended to cover equivalent
    letters. For example, the letters 'é', 'è', 'ë' will also be mapped to the
    same binary encoding as the letter 'e'.
    """

    # The standard english letter frequencies
    char_freqs = [
        (0.124167, u'e'),   
        (0.096922, u't'),   
        (0.082001, u'a'),   
        (0.076805, u'i'),   
        (0.076405, u'n'),   
        (0.071409, u'o'),   
        (0.070676, u's'),   
        (0.066813, u'r'),   
        (0.044830, u'l'),   
        (0.036370, u'd'),   
        (0.035038, u'h'),   
        (0.034439, u'c'),   
        (0.031714, u'_'),
        (0.028777, u'u'),   
        (0.028177, u'm'),   
        (0.023514, u'f'),   
        (0.020727, u'1'),
        (0.020317, u'p'),   
        (0.018918, u'y'),   
        (0.018118, u'g'),   
        (0.013522, u'w'),   
        (0.012456, u'v'),   
        (0.011480, u'2'),
        (0.011375, u'0'),
        (0.010658, u'b'),   
        (0.008631, u'3'),
        (0.007621, u'6'),
        (0.007365, u'4'),
        (0.006833, u'5'),
        (0.006670, u'8'),
        (0.006136, u'9'),
        (0.006091, u'7'),
        (0.003930, u'k'),   
        (0.002198, u'x'),   
        (0.001998, u'j'),   
        (0.000932, u'q'),   
        (0.000599, u'z')   
    ]

    # Create the Huffman tree
    trees = list(char_freqs)
    heapq.heapify(trees)
    while len(trees) > 1:
        childR, childL = heapq.heappop(trees), heapq.heappop(trees)
        parent = (childL[0] + childR[0], childL, childR)
        heapq.heappush(trees, parent)
    huffman_mapping = dict()
    create_huffman_mapping(trees[0], huffman_mapping)

    # Apply all basic character equivalences
    for c_ext, c_base in zip(chr_ext, chr_base):
        huffman_mapping[c_ext] = huffman_mapping[c_base]

    # Apply special equivalences
    huffman_mapping[u'\u0153'] = huffman_mapping[u'o'] + huffman_mapping[u'e']
    huffman_mapping[u'\xe1'  ] = huffman_mapping[u'a']
    huffman_mapping[u'\xdf'  ] = huffman_mapping[u's'] + huffman_mapping[u's']
    huffman_mapping[u'\xd7'  ] = huffman_mapping[u'x']
    huffman_mapping[u'\xe3'  ] = huffman_mapping[u'a']
    huffman_mapping[u'\xe4'  ] = huffman_mapping[u'a']
    huffman_mapping[u'\xaa'  ] = huffman_mapping[u'a']
    huffman_mapping[u'\xb5'  ] = huffman_mapping[u'u']
    huffman_mapping[u'\xe5'  ] = huffman_mapping[u'a']
    huffman_mapping[u'\xf1'  ] = huffman_mapping[u'n']
    huffman_mapping[u'\xff'  ] = huffman_mapping[u'y']
    huffman_mapping[u'\u0161'] = huffman_mapping[u's']
    huffman_mapping[u'\u017e'] = huffman_mapping[u'z']
    huffman_mapping[u'\xed'  ] = huffman_mapping[u'i']
    huffman_mapping[u'\xf3'  ] = huffman_mapping[u'o']
    huffman_mapping[u'\xf5'  ] = huffman_mapping[u'o']
    huffman_mapping[u'\xf8'  ] = huffman_mapping[u'o']
    huffman_mapping[u'\xfa'  ] = huffman_mapping[u'u']
    huffman_mapping[u'\xf2'  ] = huffman_mapping[u'o']
    huffman_mapping[u'\xe6'  ] = huffman_mapping[u'a'] + huffman_mapping[u'e']
    huffman_mapping[u'\u0192'] = huffman_mapping[u'f']
    
    return huffman_mapping

#word_encoding_map = init_word_encoding()

word_encoding_cache = dict()
def encode_word(word):
    bin_obj = word_encoding_cache.get(word)
    if bin_obj != None:
        return bin_obj
    bin_str = ''.join(word_encoding_map.get(letter, '') for letter in word)
    pad_count = 8 - ((len(bin_str) + 3) % 8)
    if pad_count == 8:
        pad_count = 0
    assert pad_count >= 0 and pad_count < 8
    bin_str = '{:03b}{}{}'.format(pad_count, bin_str, '0'*(pad_count))
    #to_debug_bin_str = bin_str
    bin_array = ''
    while len(bin_str) > 0:
        bin_array += chr(int(bin_str[0:8], 2))
        bin_str = bin_str[8:]
    #print binascii.hexlify(bin_array)
    #print word
    #print 'raw: ', ''.join('{:08b}'.format(ord(c)) for c in word)
    #print 'enc: ', to_debug_bin_str
    #print '      |       |       |       |       |       |       |       |'
    word_encoding_cache[word] = sqlite3.Binary(bin_array)
    return sqlite3.Binary(bin_array)

def compute_freqs(paths):
    freqs = collections.Counter()
    total_word_length = 0
    word_count = 0
    for path in paths:
        for f, err in util.walkdir(path, maxdepth=9999, listdirs=False, file_filter=is_file_handled):
            for word in (w for w in util.isplit(chr_map[c] for c in iter_file_txt(f))):
                total_word_length += len(word)
                word_count += 1
                #for c in word:
                #  freqs[c] += 1
                #freqs['X'] += 1
    pprint(sorted(freqs.items(), key=operator.itemgetter(1), reverse=True))
    print float(total_word_length) / word_count

def print_intarray_buf(name, b):
    print
    print name
    print 'size:', len(b)
    #print binascii.hexlify(b)

def encode_simple_ints(d, concat, spec_list):
    #for k,v in d.iteritems():
    #  if v > 255:
    #    v = 255
    #  new_int = (k<<8) | v
    #  print 'new_int:',new_int
    #  print new_int & 0xf
    #  print new_int >> 8
    if spec_list:
        return [k<<8 | v for k,v in d.iteritems()]
    if concat:
        return array.array('L', [k<<8 | v for k,v in d.iteritems()]).tostring()
    else:
        return array.array('L', list(itertools.chain.from_iterable(d.iteritems()))).tostring()

def encode_obj(obj, pickle, comp, is_list=False, concat=True, spec_list=False):
    print
    print 'pickle:', pickle, ', comp:', comp, ', is_list:', is_list, ', concat:', concat, ', spec_list', spec_list
    t = time.clock()
    if spec_list:
        obj = encode_simple_ints(obj, concat, spec_list)
    if pickle:
        b = cPickle.dumps(obj, protocol=2)
    else:
        b = encode_simple_ints(obj, concat, spec_list)
    if comp:
        b = bz2.compress(b)
    t = time.clock() - t
    print 'time:', t
    print 'len :', len(b)
    #print pprint.pprint(obj)
    #print binascii.hexlify(b)
    return b

def test_perf_encoding(matches, merges, is_array=False):
    t = time.clock()
    if is_array:
        b = bz2.compress(matches)
        matches = bz2.decompress(b)
    else:
        b = bz2.compress(cPickle.dumps(matches, protocol=2))
        matches = cPickle.loads(bz2.decompress(b))
    if is_array:
        matches = array.array('L', matches)
        matches.extend(merges)
    if isinstance(matches, dict):
        matches.update(merges)
    elif isinstance(matches, list):
        matches.extend(merges)
    t = time.clock() - t
    print 'time:', t
    print 'len :', len(b)

def test_intarray_encoding():
    # Create matches
    matches_dict = dict()
    for i in range(1000):
        matches_dict[random.randint(0, 2000000)] = random.randint(0, 100)
    matches_list = list(itertools.chain.from_iterable(matches_dict.iteritems()))

    # Create merges
    tomerge_dict = dict()
    for i in range(1000):
        tomerge_dict[random.randint(3000000, 3500000)] = random.randint(0, 100)
    tomerge_list = list(itertools.chain.from_iterable(tomerge_dict.iteritems()))
    print 

    #pprint.pprint(matches_dict)
    #pprint.pprint(matches_list)
    #pprint.pprint(tomerge_dict)
    #pprint.pprint(tomerge_list)
    #print 'matches dict size:', len(matches_dict)
    #print 'matches list size:', len(matches_list)
    #print 'merges  dict size:', len(tomerge_dict)
    #print 'merges  list size:', len(tomerge_list)

    print 'dict'
    test_perf_encoding(matches_dict, tomerge_dict)
    print
    print 'list'
    test_perf_encoding(matches_list, tomerge_list)
    print
    print 'array'
    matches = array.array('L', matches_list)
    merges = array.array('L', tomerge_list)
    test_perf_encoding(matches, merges, True)
    return

    #encode_obj(matches                                                  , pickle=True  , comp=False)
    #encode_obj(list(itertools.chain.from_iterable(matches.iteritems())) , pickle=True  , comp=False  , is_list=True)
    #encode_obj(matches                                                  , pickle=False , comp=False)
    #encode_obj(matches                                                  , pickle=False , comp=False, concat=False)
    #encode_obj(matches                                                  , pickle=True  , comp=False, concat=True, spec_list=True)
    #encode_obj(matches                                                  , pickle=True  , comp=True)
    #encode_obj(list(itertools.chain.from_iterable(matches.iteritems())) , pickle=True  , comp=True   , is_list=True)
    #encode_obj(matches                                                  , pickle=False , comp=True)
    #encode_obj(matches                                                  , pickle=False , comp=True, concat=False)
    #encode_obj(matches                                                  , pickle=True  , comp=True, concat=True, spec_list=True)

def test_perf_comp():
    for proto in (0,1,2):
        w1 = 'messagedelta'
        w2 = 'etats'
        w3 = 'if'
        w4 = 'omega'
        w5 = 'for'
        print
        print 'proto:', proto
        m1 = dict()
        m1[w1] = {123:2, 234234423:899, 2:3, 4:5, 6:7, 8:9, 9:8, 77:56, 654:34, 345345345:2, 3345345345345:2, 456456456456:6}
        m1[w2] = {99123:299, 234234423:9}
        m1[w3] = {123123:33, 1231231233:32243, 3424325435:65, 56756758874:5}
        m1[w4] = {1:2, 3:4, 5:6, 7:8}
        m1[w5] = {234234:4, 234432:1, 9879789789:3, 0:1}
        b = cPickle.dumps(m1, protocol=proto)
        print 'raw :', len(b)
        b_zlib = zlib.compress(b)
        print 'zlib:', len(b_zlib)
        b_bz2 = bz2.compress(b)
        print 'bz2 :', len(b_bz2)
        print repr(b_bz2)

def test_md5():
    pass
    #h = hashlib.md5(u'dededaldlaélongmessage').digest()
    #s = struct.Struct('<xxxxxxxxQ')
    #large_id = s.unpack(h)[0] & 0x00000000000000000FFFFFFFFFFFFFFF
    #print repr(large_id)
    #conn.execute("INSERT INTO tbl_MatchTable ('id', 'word', 'doc_id', 'relev') VALUES (?,?,?,?)", (large_id, sqlite3.Binary(''), 1, 3)) 
    #row = MatchTable.select(conn, id=large_id)[0]
    #conn.rollback()
    #print row
    #print repr(row.id)

if __name__ == '__main__':
    test_intarray_encoding()
