# todo: determine a max word length, forcefully splitting if larger
# todo: Python: if doc is larger than a certain max size, split in blocks to
#       send to Cpp, however, Python must make sure to split blocks at word
#       boundary
# todo: read the doc directly into ctypes buffer (read_into)
# todo: from Cpp, create a queue where blocks are accumulated, and a thread (or
#       more) that pick them up and process them, storing results
# todo: from Python, only retrieve results from Cpp when a certain number of
#       words, or a certain quantity of total data, has been accumulated

import codecs
from ctypes import *
import os
import os.path as osp
import sqlite3
import sys

db_file = osp.expanduser('~\\idxbeast.db')
conn = sqlite3.connect(db_file)

conn.execute('''CREATE TABLE IF NOT EXISTS doc(
                id          INTEGER PRIMARY KEY,
                create_time INTEGER NOT NULL,
                update_time INTEGER NOT NULL)''')

conn.execute('''CREATE TABLE IF NOT EXISTS path(
                id          INTEGER PRIMARY KEY,
                name        TEXT NOT NULL,
                parent      INTEGER,
                UNIQUE(name, parent))''')
conn.execute('''INSERT OR IGNORE INTO path(id, name) VALUES(1, 'root')''')

conn.execute('''CREATE TABLE IF NOT EXISTS file(
                id          INTEGER PRIMARY KEY,
                path        INTEGER NOT NULL UNIQUE)''')

conn.execute('''CREATE TABLE IF NOT EXISTS word(
                id          INTEGER PRIMARY KEY,
                word        TEXT UNIQUE)''')

conn.execute('''CREATE TABLE IF NOT EXISTS match(
                word_id     INTEGER,
                doc_id      INTEGER,
                relev       INTEGER NOT NULL,
                PRIMARY KEY(word_id, doc_id)) WITHOUT ROWID''')

supported_exts = '''bat c cpp cs cxx h hpp htm html ini java js log md py rest
                    rst txt vim xml yaml yml'''
supported_exts = set('.' + e for e in supported_exts.split())

lib = cdll.idxbeast
lib.push_block.argtypes = [c_longlong, POINTER(c_ubyte), c_longlong]
lib.push_block.restype  = c_int

def lookup_path(p):
    cur = conn.cursor()
    path_tokens = p.split(os.sep)
    cur_parent = 1 # 1 is the root
    for tok in path_tokens:
        cur.execute('SELECT id FROM path WHERE name=? AND parent=?',
                    (tok, cur_parent))
        for row in cur:
            cur_parent = row[0]
            break
        else: 
            cur.execute('INSERT INTO path(name, parent) VALUES(?, ?)',
                        (tok, cur_parent))
            cur_parent = cur.lastrowid
    return cur_parent

def lookup_file(path_id):
    c = conn.cursor()
    for row in c.execute('SELECT id FROM file WHERE path=?', (path_id,)):
        return row[0]
    c.execute('INSERT INTO file(path) VALUES(?)', (path_id,))
    return c.lastrowid

def index_doc(doc_id, text):
    print('Indexing {}'.format(doc_id))
    encoded_text = text.encode('utf-32') # Not specifying byte order will use
                                         # the native byte order, which means
                                         # the C++ lib can read the code points
                                         # directly as uint32_t.
    arr = (c_ubyte * len(encoded_text))()
    for i,c in enumerate(encoded_text): arr[i] = c
    print('Calling push_block...')
    lib.push_block(doc_id, arr, len(arr))
    print('Done.')

def parse(path):
    path = osp.abspath(path)
    if osp.isfile(path): parse_file(path)
    elif osp.isdir(path):
        for dirpath, dirnames, filenames in os.walk(path):
            for name in filenames: parse_file(os.path.join(dirpath, name))
    else: assert False, 'Invalid path: {}'.format(path)

    # Get results from lib
    #lib.get_results()

def parse_file(path):
    print(path)
    assert osp.isfile(path), 'Path is not a file: {}'.format(path)
    path = osp.normpath(path)

    with conn:

        print('Indexing path')
        path_id = lookup_path(path)
        index_doc(path_id, path)
        s = None
        root, ext = os.path.splitext(path)

        # Decode with system default
        try:
            with open(path) as f: s = f.read()
        except UnicodeDecodeError as ex: pass

        # Decode with UTF-8
        if not s:
            try:
                with codecs.open(path, encoding='utf-8') as f:
                    s = f.read()
            except UnicodeDecodeError as ex2: pass

        # Decode with ascii
        if not s:
            with codecs.open(path, encoding='ascii', errors='replace') as f:
                s = f.read()

        # Index contents
        file_id = lookup_file(path_id)
        index_doc(file_id, s)

if __name__ == '__main__':
    parse(sys.argv[1])

