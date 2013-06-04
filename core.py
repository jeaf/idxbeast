# coding=latin-1

"""
idxbeast core services.

This modules provide the core indexing services for idxbeast.

Since this module uses multiprocessing, logging requires special care. A
module-level object is created on module import. Internally, this object will
use a Queue and a thread to make sure logs from multiple processes are logged
correctly.

Copyright (c) 2013, François Jeannotte.
"""

import collections
import ctypes
import datetime
import idxlib
import itertools
import logging
import multiprocessing as mp
import operator
import os.path
import Queue
import string
import struct
import threading
import time
import traceback
import urllib2
from   urlparse import urljoin

import apsw
import bs4
import unidecode
import win32com.client

import charmap_gen
import varint

class MultiprocessingLogger(object):
    """
    This class implements support for proper logging with the multiprocessing
    module. All logs are sent to a queue, and a thread is used to empty the
    queue and log the messages.

    Initially, the logger has no handler. Handlers are added by users of this
    module. For instance, the idxbeast.py entry point script will setup file
    logging, if enabled. A gui module (does not exist yet) could also setup a
    handler that logs into a window, for example.
    """

    def __init__(self):
        """
        Initialize the logger with a None queue. The queue will need to be set
        by each process spawned by the multiprocessing module.
        """
        self.log_queue = None

    def log_thread(self):
        """The log listener thread."""
        while True:
            level, msg = self.log_queue.get()
            self.log_obj.log(level, msg)

    def add_handler(self, handler):
        """
        The first call to add_handler will create the queue and the processing
        thread.
        """
        if self.log_queue == None:
            self.log_obj = logging.getLogger('core')
            self.log_obj.setLevel(logging.DEBUG)
            self.log_queue = mp.Queue()
            t = threading.Thread(target=MultiprocessingLogger.log_thread,
                                 args=(self,))
            t.daemon = True
            t.start()
        self.log_obj.addHandler(handler)

    def debug(self, msg):
        """Log a debug message."""
        if self.log_queue != None:
            self.log_queue.put((logging.DEBUG, msg))

    def info(self, msg):
        """Log a warning message."""
        if self.log_queue != None:
            self.log_queue.put((logging.INFO, msg))

    def warning(self, msg):
        """Log a warning message."""
        if self.log_queue != None:
            self.log_queue.put((logging.WARNING, msg))

    def error(self, msg):
        """Log an error message."""
        if self.log_queue != None:
            self.log_queue.put((logging.ERROR, msg))

log = MultiprocessingLogger()

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
doctype_file    = 1
doctype_email   = 2
doctype_webpage = 3

# Get the translation table from the charmap generator script
translate_table = charmap_gen.create_translate_table()

word_hash_cache = dict()
def get_word_hash(word):
    """
    Create a 64 bit hash for a given word.
    """
    if len(word_hash_cache) > 500000:
        word_hash_cache.clear()
    word_hash = word_hash_cache.get(word, None)
    if word_hash == None:
        word_hash = idxlib.fnv(word)
        word_hash_cache[word] = word_hash
    return word_hash

class Document(object):
    def index(self):
        try:
            words, word_cnt      = idxlib.index(self.id, self.get_text())
            self.words           = words
            self.word_cnt        = word_cnt
            self.unique_word_cnt = len(words)
        except Exception, ex:
            log.warning('Exception while processing {}, exception: {}'.
                        format(self, ex))
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
                log.warning('Exception while processing Outlook folder, '
                              'exception: {}'.format(ex))

class Webpage(Document):
    def __init__(self, url, size, soup):
        self.type_      = doctype_webpage
        self.locator    = url
        self.mtime      = 0
        self.title      = soup.title.get_text()
        self.extension  = None
        self.size       = size
        self.from_      = None
        self.to_        = None
        self.soup       = soup
    def __repr__(self):
        return '<Webpage ' + ' ' + self.locator + '>'
    def get_text(self):
        return unicode(self.soup)

def iterwebpages(url, recurselinks):
    """Yield web page documents, recursing through links if necessary."""

    # Read and yield the root page
    try:
        s = urllib2.urlopen(url).read()
        soup = bs4.BeautifulSoup(s)
        yield Webpage(url, len(s), soup), None
    except Exception, ex:
        yield None, ex

    # If we must recurse, loop through links
    if recurselinks > 0:
        for link in set(link.get('href') for link in soup.find_all('a')):
            abs_url = urljoin(url, link)
            for p, err in iterwebpages(abs_url, recurselinks - 1):
                yield p, err

matches_cache = dict()
orderby_map   = {'relev': 1, 'freq': 2, 'avgidx': 3}
orderdir_map  = {'desc': True, 'asc': False}

def search(db_conn, words, limit, offset, orderby='relev', orderdir='desc'):
    """
    Executes a search. orderby can be:
        - relev
        - freq
        - avgidx
    orderdir can be:
        - asc
        - desc
    """

    cur = db_conn.cursor()

    # Decode the matches that correspond to the query
    doc_id_sets = []
    match_dicts = []
    for wh in (get_word_hash(w) for w in
               unidecode.unidecode(words).translate(translate_table).split()):
        if wh not in matches_cache:
            doc_id_set = frozenset()
            matches = dict()
            for size, in cur.execute('SELECT size FROM match WHERE id=?',
                                     (wh,)):
                with db_conn.blobopen('main', 'match', 'matches_blob',
                                      wh, False) as blob:
                    buf = bytearray(size)
                    blob.readinto(buf, 0, size)
                    int_list = varint.decode(buf)
                    assert len(int_list) % 3 == 0
                    doc_id_set = []
                    matches = collections.Counter()
                    for i in range(0, len(int_list), 3):
                        doc_id_set.append(int_list[i])
                        matches[int_list[i]] = complex(int_list[i+1],
                                                       int_list[i+2])
                    doc_id_set = frozenset(doc_id_set)
            matches_cache[wh] = doc_id_set, matches
        else:
            doc_id_set, matches = matches_cache[wh]
        doc_id_sets.append(doc_id_set)
        match_dicts.append(matches)

    # Compute the intersection between matches set, and insert into search
    match_ids = reduce(frozenset.intersection, doc_id_sets)
    tots = ((docid, sum(m[docid] for m in match_dicts)) for docid in match_ids)
    search_tuples = [(did, t.real * 10.0 / (t.imag + 1), t.real, t.imag)
                     for did,t in tots]

    # Return search results
    search_tuples.sort(key=operator.itemgetter(orderby_map[orderby]),
                       reverse=orderdir_map[orderdir])
    result_docids = search_tuples[offset: offset + limit]
    c = cur.executemany('''SELECT ?,?,?,id,type_,locator,title
                           FROM doc WHERE id=?''',
                        ((relev,freq,avgidx,docid) for docid,relev,freq,avgidx
                                                    in result_docids))
    return len(match_ids), c

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


def dispatcher_proc(db_path, dispatcher_shared_data, indexer_shared_data_array,
                    srcs, exts, recurselinks, log_q):

    # Setup the logger for this process
    log.log_queue = log_q

    # Create the document queue and worker processes
    index_q = mp.Queue()
    db_q    = mp.Queue()
    worker_procs = [mp.Process(target=indexer_proc, args=(i, indexer_shared_data_array, index_q, db_q, log_q)) for i in range(len(indexer_shared_data_array))]
    for p in worker_procs: p.start()
    dbwriter_p = mp.Process(target=dbwriter_proc, args=(db_path, db_q, dispatcher_shared_data, log_q))
    dbwriter_p.start()

    # Read the entire document DB in memory
    dispatcher_shared_data.status = 'Load initial document list'
    initial_docs = dict()
    next_doc_id = 0
    for id,locator,mtime in apsw.Connection(db_path).cursor().execute('SELECT id,locator,mtime FROM doc'):
        initial_docs[locator] = id,mtime
        next_doc_id = max(next_doc_id, id)
    next_doc_id += 1

    # Split the sources into dirs and web pages
    srcs_dir     = [src for src in srcs if os.path.isdir(src)]
    srcs_webpage = [src for src in srcs if not os.path.isdir(src)]

    # List all documents
    chained_iterfiles  = itertools.chain.from_iterable(
                         iterfiles(unicode(rootdir), exts)
                         for rootdir in srcs_dir)
    chained_webpages   = itertools.chain.from_iterable(
                         iterwebpages(webpage, recurselinks)
                         for webpage in srcs_webpage)
    for doc, error in itertools.chain(chained_iterfiles, chained_webpages):

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
            log.error('Dispatcher: error while processing doc {}, error: {}'.
                        format(doc, traceback.format_exc()))

    # Wait on worker processes
    dispatcher_shared_data.status = 'Waiting on indexer processes'
    for i in range(len(worker_procs)): index_q.put(None)
    for p in worker_procs: p.join()
    dispatcher_shared_data.status = 'Waiting on db writer process'
    db_q.put(None)
    dbwriter_p.join()
    dispatcher_shared_data.status = 'Idle'

def dbwriter_proc(db_path, db_q, dispatcher_shared_data, log_q):

    # Setup the logger for this process
    log.log_queue = log_q

    # Connect to the DB and setup connection for better performance
    conn = apsw.Connection(db_path)
    cur  = conn.cursor()
    cur.execute('PRAGMA journal_mode=off')
    cur.execute('PRAGMA synchronous=off')

    # Loop on the Queue until the None sentry is received
    finished = False
    while not finished:

        # Extract the documents available from the queue
        dispatcher_shared_data.db_status = 'emptying queue'
        docs              = []
        doc_ids_to_delete = []
        try:
            while True and len(docs) < 10000:
                doc = db_q.get(True, 0.5)
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
        dispatcher_shared_data.db_status = 'merge words ({} docs)'.format(len(docs))
        words = collections.defaultdict(bytearray)
        for doc in docs:
            for wh, buf in doc.words.iteritems():
                words[wh].extend(buf)

        # Figure out which word_hash are present in the DB, and which are not
        dispatcher_shared_data.db_status = 'select ({})'.format(len(words))
        wh_in_db = dict((i,size) for (i,size) in cur.execute('SELECT id,size FROM match') if i in words)
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
            cur.executemany("INSERT INTO match ('id', 'size', 'matches_blob') VALUES (?,?,?)", tuples_new)
            dispatcher_shared_data.db_status = 'update matches ({})'.format(len(tuples_upd))
            cur.executemany('UPDATE match SET size=?, matches_blob=? WHERE id=?', tuples_upd)
            dispatcher_shared_data.db_status = 'update sizes ({})'.format(len(tuples_size))
            cur.executemany('UPDATE match SET size=? WHERE id=?', tuples_size)

            # Delete outdated documents
            if len(doc_ids_to_delete) > 0:
                dispatcher_shared_data.db_status = 'delete docs ({})'.format(len(doc_ids_to_delete))
                cur.executemany('DELETE FROM doc WHERE id=?', doc_ids_to_delete)

            # Insert new/updated documents
            tuples = [(doc.id, doc.type_, doc.locator, doc.mtime, doc.title, doc.extension, doc.size, doc.word_cnt, doc.unique_word_cnt, doc.from_, doc.to_) for doc in docs]
            dispatcher_shared_data.db_status = 'insert docs ({})'.format(len(tuples))
            cur.executemany("INSERT INTO doc ('id','type_','locator','mtime','title','extension','size','word_cnt','unique_word_cnt','from_','to_') VALUES (?,?,?,?,?,?,?,?,?,?,?)", tuples)

            # Right before going out of the current scope, set the status to commit.
            # When the scope ends, the COMMIT will take place because of the context
            # manager.
            dispatcher_shared_data.db_status = 'committing {} documents'.format(len(docs))

    dispatcher_shared_data.db_status = ''
    dispatcher_shared_data.doc_done_count = 0
    dispatcher_shared_data.current_doc    = ''

def indexer_proc(i, shared_data_array, index_q, db_q, log_q):

    # Setup the logger for this process
    log.log_queue = log_q

    # Index documents
    shared_data_array[i].status      = ''
    shared_data_array[i].doc_done_count = 0
    shared_data_array[i].current_doc    = ''
    for doc in iter(index_q.get, None):
        shared_data_array[i].current_doc = doc.title if doc.title else doc.locator
        doc.index()
        shared_data_array[i].doc_done_count += 1
        db_q.put(doc)

def start_indexing(db_path, srcs, nbprocs, exts, recurselinks):

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
    disp = mp.Process(target=dispatcher_proc, args=(db_path, dstat,
                                                    istat_array, srcs, exts,
                                                    recurselinks,
                                                    log.log_queue))
    disp.start()
    return dstat, istat_array

