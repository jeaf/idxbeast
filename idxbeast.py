from ctypes import *
import os
import os.path as osp
import sqlite3
import sys

conn = sqlite3.connect(osp.expanduser('~\\idxbeast.db'))

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

conn.execute('''CREATE TABLE IF NOT EXISTS match(
                word_id     INTEGER,
                doc_id      INTEGER,
                relev       INTEGER NOT NULL,
                PRIMARY KEY(word_id, doc_id)) WITHOUT ROWID''')

supported_exts = '''bat c cpp cs cxx h hpp htm html ini java js log md py rest
                    rst txt vim xml yaml yml'''
supported_exts = set('.' + e for e in supported_exts.split())

lib = cdll.idxbeast
lib.parse_doc.argtypes = [c_longlong, POINTER(c_uint), c_longlong]
lib.parse_doc.restype  = c_int

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

def index_path(p):
    pass

def insert_file(f):
    pass

def parse(path):
    path = osp.abspath(path)
    if osp.isfile(path): parse_file(path)
    elif osp.isdir(path):
        for dirpath, dirnames, filenames in os.walk(path):
            for name in filenames: parse_file(os.path.join(dirpath, name))
    else: assert False, 'Invalid path: {}'.format(path)

def parse_file(path):
    assert osp.isfile(path)
    path = osp.normpath(path)

    with conn:

        # Insert and index path
        lookup_path(path)
        index_path(path)

        # If content indexing support, insert and index file
        root, ext = os.path.splitext(path)
        if ext in supported_exts:
            with open(path) as f: s = f.read()

if __name__ == '__main__':
    parse(sys.argv[1])

