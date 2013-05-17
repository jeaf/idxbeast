# coding=latin-1

"""
idxbeast core services.

This modules provide the core indexing services for idxbeast.

Copyright (c) 2013, François Jeannotte.
"""

import collections
import ctypes
import datetime
import hashlib
import itertools
import logging
import multiprocessing as mp
import os.path
import Queue
import string
import struct
import time
import traceback

import apsw
import unidecode
import win32com.client

import charmap_gen
import varint

# Initialize logger, initially without handler. Handlers are added by users of
# this module. For instance, the idxbeast.py entry point script will setup
# file logging, if enabled. A gui module (does not exist yet) could also setup
# a handler that logs into a window, for example.
log = logging.getLogger('core')
log.setLevel(logging.DEBUG)
log_formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")

def create_tables(conn):
    """
    Create the database tables used for storing the index: match and doc.
    """

    sql = conn.cursor().execute

    # match
    #
    # id          : the truncated MD5 of the flattened (été -> ete) word.
    # size        : the size in bytes of the encoded data stored in the BLOB.
    #               It is possible for the encoded data to be smaller than the
    #               real BLOB size. For example, if the BLOB needs to be
    #               resized, it could be resized to a larger value than needed
    #               to try to avoid resizes in future updates.
    # matches_blob: A list of encoded integer groups, one group for each match.
    #               Each group contains the following integers:
    #                - document id
    #                - word count (the number of times this word appears in the
    #                  document)
    #                - the average index of this word in the document. The
    #                  index is zero based (i.e., the first word has index 0).
    sql('''CREATE TABLE IF NOT EXISTS match(id           INTEGER PRIMARY KEY,
                                            size         INTEGER NOT NULL,
                                            matches_blob BLOB    NOT NULL)''')

    # doc
    #
    # The locator should be unique, and should allow unequivocal retrieval of
    # the document. For example:
    #   - file     : the path
    #   - web page : the URL
    #   - email    : the EntryId
    # The (optional, immutable) title is used to display to the user. Since it
    # is immutable, it will not be updated even if it changes in a web page.
    # For example:
    #   - file     : <not used, will display locator>
    #   - web page : the title of the page
    #   - email    : the subject
    # We use AUTOINCREMENT for the id primary key, because otherwise SQLite may
    # reuse ids from previously deleted rows. We don't want this because updated
    # documents are deleted from the DB, but their id may still be inside the
    # index for a word.
    sql('''CREATE TABLE IF NOT EXISTS doc(
           id              INTEGER PRIMARY KEY AUTOINCREMENT,
           type_           INTEGER NOT NULL,
           locator         TEXT    UNIQUE NOT NULL,
           mtime           INTEGER,
           title           TEXT,
           extension       TEXT,
           size            INTEGER,
           word_cnt        INTEGER NOT NULL,
           unique_word_cnt INTEGER NOT NULL,
           from_           TEXT,
           to_             TEXT)''')

# Constants
doctype_file  = 1
doctype_email = 2

# Get the translation table from the charmap generator script
translate_table = charmap_gen.create_translate_table()

# This Struct instance will be used to extract a 60-bit int from a MD5 hash.
word_hash_struct = struct.Struct('<xxxxxxxxQ')
word_hash_cache = dict()
def get_word_hash(word):
    """
    Create a 60 bit hash for a given word.

    >>> get_word_hash('abc')
    180110074134370006L
    """
    if len(word_hash_cache) > 10000:
        word_hash_cache.clear()
    word_hash = word_hash_cache.get(word, None)
    if word_hash == None:
        word_hash = word_hash_struct.unpack(hashlib.md5(word).digest())[0] & 0x00000000000000000FFFFFFFFFFFFFFF
        word_hash_cache[word] = word_hash
    return word_hash

class Document(object):
    def index(self):
        try:
            words = collections.Counter()
            current_relev_value = 100
            for i,w in enumerate(w for w in unidecode.unidecode(self.get_text()).translate(translate_table).split() if len(w) > 1 and len(w) < 40):
                words[w] += current_relev_value
                if current_relev_value > 0.1:
                    current_relev_value -= 0.1
            self.word_cnt        = i + 1
            self.unique_word_cnt = len(words)
            encoded_id = varint.encode([self.id])
            self.words = dict( (get_word_hash(w), bytearray().join((encoded_id, varint.encode([int(relev)])))) for w,relev in words.iteritems() )
        except Exception, ex:
            log.warning('Exception while processing {}, exception: {}'.format(self, ex))
            self.words = dict()

class File(Document):
    def __init__(self, path):
        self.type_      = doctype_file
        self.locator    = os.path.abspath(path)
        self.mtime      = os.path.getmtime(self.locator)
        self.title      = None
        root, ext       = os.path.splitext(self.locator)
        self.extension  = ext[1:] if ext.startswith('.') else ext
        self.size       = os.path.getsize(self.locator)
        self.from_      = None
        self.to_        = None
    def __repr__(self):
        return '<File ' + ' ' + self.locator + '>'
    def get_text(self):
        with open(self.locator, 'r') as f:
            return ''.join((self.locator, ' ', f.read()))

def iterfiles(rootdir, exts):
    supported_extensions = set(''.join(['.', ext]) for ext in exts.split())
    for dirpath, dirnames, filenames in os.walk(rootdir):
        for name in filenames:
            path = os.path.join(dirpath, name)
            root, ext = os.path.splitext(path)
            if ext in supported_extensions:
                try:
                    yield File(path), None
                except Exception, ex:
                    yield path, ex

class OutlookEmail(Document):
    """
    Represents a email document from Microsoft Outlook. Reference for MailItem
    objects can be found at
    http://msdn.microsoft.com/en-us/library/aa210946(v=office.11).aspx
    """
    def __init__(self, entry_id, mapi, from_, to_, size, subject, rt):
        self.type_   = doctype_email
        self.locator = entry_id
        self.mtime   = time.mktime(datetime.datetime(rt.year, rt.month, rt.day, rt.hour, rt.minute, rt.second).timetuple())
        self.title   = subject
        self.size    = int(size)
        self.from_   = from_
        self.to_     = to_
        #self.mapi    = mapi
    def __repr__(self):
        return '<Email ' + str(self.title) + '>'
    def get_text(self):
        outlook = win32com.client.Dispatch('Outlook.Application')
        mapi = outlook.GetNamespace('MAPI')
        mail_item = mapi.GetItemFromId(self.locator)
        f = ''
        if self.from_:
            f = self.from_
        t = ''
        if self.to_:
            t = self.to_
        return ''.join((f, ' ', t, ' ', self.title, ' ', unicode(mail_item.Body)))

def iteremails(folder_filter):
    outlook = win32com.client.Dispatch('Outlook.Application')
    mapi = outlook.GetNamespace('MAPI')
    for f in mapi.Folders:
        for folder in f.Folders:
            if not str(folder) in folder_filter:
                continue
            try:
                table = folder.GetTable()
                table.Columns.RemoveAll()
                table.Columns.Add('EntryId')
                table.Columns.Add('SenderName')
                table.Columns.Add('To')
                table.Columns.Add('CC')
                table.Columns.Add('BCC')
                table.Columns.Add('Size')
                table.Columns.Add('Subject')
                table.Columns.Add('ReceivedTime')
                while not table.EndOfTable:
                    try:
                        row = table.GetNextRow()
                        oe = OutlookEmail(row['EntryId'],
                                          mapi,
                                          row['SenderName'],
                                          ' '.join((row['To'], row['CC'], row['BCC'])),
                                          row['Size'],
                                          row['Subject'],
                                          row['ReceivedTime'])
                        yield oe, None
                    except Exception, ex:
                        yield None, ex
            except Exception, ex:
                log.warning('Exception while processing Outlook folder, exception: {}'.format(ex))

def search(db_path, words, limit, offset):
    
    # Connect to the DB and create the necessary temporary memory tables
    conn = apsw.Connection(db_path)
    cur = conn.cursor()
    cur.execute("ATTACH ':memory:' AS search_db")
    cur.execute('CREATE TABLE search_db.search(id INTEGER PRIMARY KEY, word_hash INTEGER NOT NULL, doc_id INTEGER NOT NULL, relev INTEGER NOT NULL)')

    # Get all the matches blobs from the DB and expand them into the temporary search table
    search_tuples = []
    query_word_hashes = [(get_word_hash(w),) for w in unidecode.unidecode(words).translate(translate_table).split()]
    for size,word_hash in cur.executemany('SELECT size,id FROM match WHERE id=?', query_word_hashes):
        with conn.blobopen('main', 'match', 'matches_blob', word_hash, False) as blob:
            buf = bytearray(size)
            blob.readinto(buf, 0, size)
            int_list = varint.decode(buf)
            assert len(int_list) % 2 == 0, 'int_list should contain n groups of doc_id,relev'
            for i in range(0, len(int_list), 2):
                search_tuples.append((word_hash, int_list[i], int_list[i+1]))
    with conn:  
        cur.executemany('INSERT INTO search(word_hash, doc_id, relev) VALUES (?,?,?)', search_tuples)

    # Figure out the total number of results
    for total, in cur.execute('''SELECT COUNT(1) FROM (SELECT 1 FROM doc
                                                       INNER JOIN search ON main.doc.id = search.doc_id
                                                       GROUP BY main.doc.id HAVING COUNT(1) = ?)''', (len(query_word_hashes),)):
        break
    else:
        total = 0

    # Return search results
    return total, cur.execute('''SELECT doc.locator, SUM(search.relev), doc.title FROM doc
                                 INNER JOIN search ON main.doc.id = search.doc_id
                                 GROUP BY main.doc.id HAVING COUNT(1) = ?
                                 ORDER BY SUM(search.relev) DESC
                                 LIMIT ? OFFSET ?''', (len(query_word_hashes), limit, offset))

class IndexerSharedData(ctypes.Structure):
    _fields_ = [('status'        , ctypes.c_char*40 ), # e.g., idle, locked, writing
                ('doc_done_count', ctypes.c_int     ),
                ('current_doc'   , ctypes.c_char*380)]

class DispatcherSharedData(ctypes.Structure):
    _fields_ = [('status'          , ctypes.c_char*40 ),
                ('listed_count'    , ctypes.c_int     ),
                ('uptodate_count'  , ctypes.c_int     ),
                ('outdated_count'  , ctypes.c_int     ),
                ('new_count'       , ctypes.c_int     ),
                ('error_count'     , ctypes.c_int     ),
                ('current_doc'     , ctypes.c_char*380),
                ('db_status'       , ctypes.c_char*40 )]


def dispatcher_proc(db_path, dispatcher_shared_data, indexer_shared_data_array, srcs, exts):

    # Create the document queue and worker processes
    index_q = mp.Queue()
    db_q    = mp.Queue()
    worker_procs = [mp.Process(target=indexer_proc, args=(i, indexer_shared_data_array, index_q, db_q)) for i in range(len(indexer_shared_data_array))]
    for p in worker_procs: p.start()
    dbwriter_p = mp.Process(target=dbwriter_proc, args=(db_path, db_q, dispatcher_shared_data))
    dbwriter_p.start()

    # Read the entire document DB in memory
    dispatcher_shared_data.status = 'Load initial document list'
    initial_docs = dict()
    next_doc_id = 0
    for id,locator,mtime in apsw.Connection(db_path).cursor().execute('SELECT id,locator,mtime FROM doc'):
        initial_docs[locator] = id,mtime
        next_doc_id = max(next_doc_id, id)
    next_doc_id += 1

    # List all documents
    chained_iterfiles  = itertools.chain.from_iterable(iterfiles(unicode(rootdir), exts) for rootdir in srcs)
    #chained_iteremails = itertools.chain.from_iterable(iteremails(em_folder)       for em_folder in srcs_email)
    #chained_webpages   = itertools.chain.from_iterable(iterwebpages(webpage)       for webpage   in srcs_webpage)
    #for doc, error in itertools.chain(chained_iterfiles, chained_iteremails, chained_webpages):
    for doc, error in chained_iterfiles:

        dispatcher_shared_data.status = 'Listing documents'
        try:
            dispatcher_shared_data.listed_count += 1

            if error != None:
                log.warning('Cannot process file {}, error: {}'.format(f, error))
                dispatcher_shared_data.error_count += 1
                continue

            dispatcher_shared_data.current_doc = doc.title if doc.title else doc.locator
            init_doc = initial_docs.get(doc.locator)
            if init_doc == None or init_doc[1] < doc.mtime:
                if init_doc != None:
                    dispatcher_shared_data.outdated_count += 1
                    doc.old_id = init_doc[0]
                else:
                    dispatcher_shared_data.new_count += 1
                doc.id = next_doc_id
                next_doc_id += 1
                index_q.put(doc)
            else:
                dispatcher_shared_data.uptodate_count += 1

        except Exception, ex:
            log.error('Dispatcher: error while processing doc {}, error: {}'.format(doc, traceback.format_exc()))

    # Wait on worker processes
    dispatcher_shared_data.status = 'Waiting on indexer processes'
    for i in range(len(worker_procs)): index_q.put(None)
    for p in worker_procs: p.join()
    dispatcher_shared_data.status = 'Waiting on db writer process'
    db_q.put(None)
    dbwriter_p.join()
    dispatcher_shared_data.status = 'Idle'

def dbwriter_proc(db_path, db_q, dispatcher_shared_data):

    # Connect to the DB
    conn = apsw.Connection(db_path)

    # Loop on the Queue until the None sentry is received
    finished = False
    while not finished:

        # Extract the documents available from the queue
        dispatcher_shared_data.db_status = 'emptying queue'
        docs              = []
        doc_ids_to_delete = []
        try:
            while True and len(docs) < 10000:
                doc = db_q.get(True, 0.25)
                if doc:
                    docs.append(doc)
                    if hasattr(doc, 'old_id'):
                        doc_ids_to_delete.append((doc.old_id,))
                else:
                    finished = True
                    break
        except Queue.Empty:
            pass

        # Merge the matches from all the documents
        words = collections.defaultdict(bytearray)
        for doc in docs:
            for wh, buf in doc.words.iteritems():
                words[wh].extend(buf)

        # Figure out which word_hash are present in the DB, and which are not
        dispatcher_shared_data.db_status = 'select ({})'.format(len(words))
        wh_in_db = dict(conn.cursor().executemany('SELECT id, size FROM match WHERE id=?', ((wh,) for wh in words.iterkeys())))
        wh_new   = set(words.keys()).difference(wh_in_db.keys())

        # Create the new tuples for new words
        dispatcher_shared_data.db_status = 'new ({})'.format(len(wh_new))
        tuples_new = []
        for wh in wh_new:
            enc_matches = words[wh]
            tuples_new.append((wh, len(enc_matches), enc_matches))

        # Fire up a transaction
        with conn:

            # Process existing words
            dispatcher_shared_data.db_status = 'blob I/O ({})'.format(len(wh_in_db))
            tuples_upd  = []
            tuples_size = []
            blob = None
            for word_hash, old_size in wh_in_db.iteritems():
                enc_matches = words[word_hash]
                if blob:
                    blob.reopen(word_hash)
                else:
                    blob = conn.blobopen('main', 'match', 'matches_blob', word_hash, True)
                new_size  = old_size + len(enc_matches)
                if new_size <= blob.length():
                    blob.seek(old_size)
                    blob.write(enc_matches)
                    tuples_size.append((new_size, word_hash))
                else:
                    buf = bytearray(2 * new_size)
                    blob.readinto(buf, 0, old_size)
                    memoryview(buf)[old_size: new_size] = enc_matches
                    tuples_upd.append((new_size, buf, word_hash))
            if blob:
                blob.close()

            # Insert and update rows in the DB
            dispatcher_shared_data.db_status = 'insert matches ({})'.format(len(tuples_new))
            conn.cursor().executemany("INSERT INTO match ('id', 'size', 'matches_blob') VALUES (?,?,?)", tuples_new)
            dispatcher_shared_data.db_status = 'update matches ({})'.format(len(tuples_upd))
            conn.cursor().executemany('UPDATE match SET size=?, matches_blob=? WHERE id=?', tuples_upd)
            dispatcher_shared_data.db_status = 'update sizes ({})'.format(len(tuples_size))
            conn.cursor().executemany('UPDATE match SET size=? WHERE id=?', tuples_size)

            # Delete outdated documents
            if len(doc_ids_to_delete) > 0:
                dispatcher_shared_data.db_status = 'delete docs ({})'.format(len(doc_ids_to_delete))
                conn.cursor().executemany('DELETE FROM doc WHERE id=?', doc_ids_to_delete)

            # Insert new/updated documents
            tuples = [(doc.id, doc.type_, doc.locator, doc.mtime, doc.title, doc.extension, doc.size, doc.word_cnt, doc.unique_word_cnt, doc.from_, doc.to_) for doc in docs]
            dispatcher_shared_data.db_status = 'insert docs ({})'.format(len(tuples))
            conn.cursor().executemany("INSERT INTO doc ('id','type_','locator','mtime','title','extension','size','word_cnt','unique_word_cnt','from_','to_') VALUES (?,?,?,?,?,?,?,?,?,?,?)", tuples)

            # Right before going out of the current scope, set the status to commit.
            # When the scope ends, the COMMIT will take place because of the context
            # manager.
            dispatcher_shared_data.db_status = 'committing {} documents'.format(len(docs))

    dispatcher_shared_data.db_status = ''
    dispatcher_shared_data.doc_done_count = 0
    dispatcher_shared_data.current_doc    = ''

def indexer_proc(i, shared_data_array, index_q, db_q):

    # Index documents
    shared_data_array[i].status      = ''
    shared_data_array[i].doc_done_count = 0
    shared_data_array[i].current_doc    = ''
    for doc in iter(index_q.get, None):
        shared_data_array[i].current_doc = doc.title if doc.title else doc.locator
        doc.index()
        shared_data_array[i].doc_done_count += 1
        db_q.put(doc)

def start_indexing(db_path, srcs, nbprocs, exts):

    # Create tables
    with apsw.Connection(db_path) as conn:
        create_tables(conn)

    # Initialize shared mem structures
    dstat = mp.Value(DispatcherSharedData)
    dstat.status = 'Starting'
    istat_array = mp.Array(IndexerSharedData, nbprocs)
    for dat in istat_array:
        dat.status = ''

    # Launch dispatcher process
    disp = mp.Process(target=dispatcher_proc, args=(db_path, dstat, istat_array, srcs, exts))
    disp.start()
    return dstat, istat_array

