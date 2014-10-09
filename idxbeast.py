import codecs
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
lib.parse_doc.argtypes = [c_longlong, POINTER(c_ubyte), c_longlong]
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

def lookup_file(path_id):
    c = conn.cursor()
    for row in c.execute('SELECT id FROM file WHERE path=?', (path_id,)):
        return row[0]
    c.execute('INSERT INTO file(path) VALUES(?)', (path_id,))
    return c.lastrowid

def index_doc(doc_id, text):
    encoded_text = text.encode('utf-32')
    arr = (c_ubyte * len(encoded_text))()
    for i,c in enumerate(encoded_text): arr[i] = c
    lib.parse_doc(doc_id, arr, len(arr))

def parse(path):
    path = osp.abspath(path)
    if osp.isfile(path): parse_file(path)
    elif osp.isdir(path):
        for dirpath, dirnames, filenames in os.walk(path):
            for name in filenames: parse_file(os.path.join(dirpath, name))
    else: assert False, 'Invalid path: {}'.format(path)

def parse_file(path):
    assert osp.isfile(path), 'Path is not a file: {}'.format(path)
    path = osp.normpath(path)

    with conn:

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

