# coding=latin-1

"""
idxbeast.py - simple content indexer.

This script implements a simple document indexing application.

todo: manage the deletion of old documents after indexing existing doc

Copyright (c) 2013, Francois Jeannotte.
"""

import apsw
import collections
import ctypes
import datetime
import hashlib
import itertools
import logging
import logging.handlers
import multiprocessing as mt
import os
import Queue
import string
import struct
import subprocess
import sys
import time
import traceback

import unidecode
import win32com.client
import yaml

import cui
import varint

def create_tables(conn):

  sql = conn.cursor().execute

  # match
  #
  # id          : the id is the truncated MD5 of the flattened (été -> ete) word.
  # matches_blob: A list of encoded integer groups, one group for each match.
  #               Each group contains the following integers:
  #                - document id
  #                - word count
  #                - average index
  sql('CREATE TABLE IF NOT EXISTS match(id INTEGER PRIMARY KEY, size INTEGER NOT NULL, matches_blob BLOB NOT NULL)')

  # doc
  #
  # The locator should be unique, and should allow unequivocal retrieval of
  # the document. For example:
  #   - file     : the path
  #   - web page : the URL
  #   - email    : the EntryId
  # The (optional, immutable) title is used to display to the user. Since it is
  # immutable, it will not be updated even if it changes in a web page. For
  # example:
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
         locator         TEXT UNIQUE NOT NULL,
         mtime           INTEGER,
         title           TEXT,
         extension       TEXT,
         title_only      INTEGER DEFAULT 0,
         size            INTEGER,
         word_cnt        INTEGER NOT NULL,
         unique_word_cnt INTEGER NOT NULL,
         from_           TEXT,
         to_             TEXT)''')

# Constants
doctype_file  = 1
doctype_email = 2

# Initialize data dir, creating it if necessary
data_dir = os.path.expanduser(ur'~\.idxbeast')
assert not os.path.isfile(data_dir)
if not os.path.isdir(data_dir):
  os.mkdir(data_dir)
db_path = os.path.join(data_dir, 'index.sqlite3')

# Initialize config file, creating it if necessary
cfg_file = os.path.join(data_dir, u'settings.yaml')
assert not os.path.isdir(cfg_file)
if not os.path.isfile(cfg_file):
  with open(cfg_file, 'w') as f:
    default_config_str = '''
    indexer_proc_count  : 4
    indexed_file_types  : 'bat c cpp cs cxx h hpp htm html ini java js log md py rest rst txt xml yaml yml'
    word_hash_cache_size: 100000
    doc_bundle_size     : 2000
    indexed_dirs:
      - C:\dir1
      - C:\dir2
    indexed_email_folders:
      - Inbox
    indexed_urls:
      - https://github.com/jeaf
    '''
    f.write(default_config_str)

# Initialize logging
log = logging.getLogger('idxbeast')
log.setLevel(logging.DEBUG)
log_formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
log_handler   = logging.handlers.RotatingFileHandler(os.path.join(data_dir, 'log.txt'), maxBytes=10*1024**2, backupCount=5)
log_handler.setFormatter(log_formatter)
log.addHandler(log_handler)

# Load configuration
cfg_obj = dict()
if os.path.isfile(cfg_file):
  with open(cfg_file, 'r') as f:
    cfg_obj  = yaml.load(f)
class cfg(object):
  indexer_proc_count    = cfg_obj.get('indexer_proc_count', 4)
  indexed_file_types    = cfg_obj.get('indexed_file_types', 'bat c cpp cs cxx h hpp htm html ini java log md py rst txt xml')
  word_hash_cache_size  = cfg_obj.get('word_hash_cache_size', 10000)
  doc_bundle_size       = cfg_obj.get('doc_bundle_size', 2000)
  indexed_dirs          = cfg_obj.get('indexed_dirs', [])
  indexed_email_folders = cfg_obj.get('indexed_email_folders', [])
  indexed_urls          = cfg_obj.get('indexed_urls', [])

# Create the translation table used with the str.translate method. This will
# replace all uppercase chars with their lowercase equivalent, and numbers
# and "_" are passed-through as is. All other chars are replaced with a
# space.
translate_table = list(256*' ')
for c in itertools.chain(string.lowercase, string.digits):
  translate_table[ord(c)] = c
for c_upper, c_lower in zip(string.uppercase, string.lowercase):
  translate_table[ord(c_upper)] = c_lower
translate_table[ord('_')] = '_'
translate_table = ''.join(translate_table)

# This Struct instance will be used to extract a 60-bit int from a MD5 hash.
word_hash_struct = struct.Struct('<xxxxxxxxQ')
word_hash_cache = dict()
def get_word_hash(word):
  """
  Create a 60 bit hash for a given word.

  >>> get_word_hash('abc')
  180110074134370006L
  """
  if len(word_hash_cache) > cfg.word_hash_cache_size:
    word_hash_cache.clear()
  word_hash = word_hash_cache.get(word, None)
  if word_hash == None:
    word_hash = word_hash_struct.unpack(hashlib.md5(word).digest())[0] & 0x00000000000000000FFFFFFFFFFFFFFF
    word_hash_cache[word] = word_hash
  return word_hash

supported_extensions = set(''.join(['.', ext]) for ext in cfg.indexed_file_types.split())
def is_file_handled(path):
  root, ext = os.path.splitext(path)
  return ext in supported_extensions

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
    self.title_only = not is_file_handled(self.locator)
    self.size       = os.path.getsize(self.locator)
    self.from_      = None
    self.to_        = None
  def __repr__(self):
    return '<File ' + ' ' + self.locator + '>'
  def get_text(self):
    if not self.title_only:
      with open(self.locator, 'r') as f:
        return ''.join((self.locator, ' ', f.read()))
    else:
      return self.locator

def iterfiles(rootdir):
  for dirpath, dirnames, filenames in os.walk(rootdir):
    for name in filenames:
      name = os.path.join(dirpath, name)
      try:
        yield File(name), None
      except Exception, ex:
        yield name, ex

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

class MenuDoc(object):
  def __init__(self, locator, relev, title, title_only):
    self.locator = locator
    self.relev = relev
    self.title = title
    if self.title == None:
      self.title = self.locator
    self.title_only = title_only
    self.disp_str = u'[{}] {}'.format(self.relev, self.title)
  def activate(self):
    if os.path.isfile(self.locator):
      if self.title_only:
        os.startfile(self.locator)
      else:
        subprocess.Popen(['notepad.exe', self.locator])
    else:
      outlook = win32com.client.Dispatch('Outlook.Application')
      mapi = outlook.GetNamespace('MAPI')
      mapi.GetItemFromId(self.locator).Display()

def search(words, limit, offset):
  
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
  return total, cur.execute('''SELECT doc.locator, SUM(search.relev), doc.title, doc.title_only FROM doc
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

# Create shared mem used when indexing. The size of the indexer array
# will determine the number of indexer worker processes
dispatcher_shared_data    = mt.Value(DispatcherSharedData)
indexer_shared_data_array = mt.Array(IndexerSharedData, cfg.indexer_proc_count)
dispatcher_shared_data.status = 'Idle'
for dat in indexer_shared_data_array:
  dat.status = ''

def dispatcher_proc(dispatcher_shared_data, indexer_shared_data_array):

  # Create the document queue and worker processes
  index_q = mt.Queue()
  db_q    = mt.Queue()
  worker_procs = [mt.Process(target=indexer_proc, args=(i, indexer_shared_data_array, index_q, db_q)) for i in range(len(indexer_shared_data_array))]
  for p in worker_procs: p.start()
  dbwriter_p = mt.Process(target=dbwriter_proc, args=(db_q, dispatcher_shared_data))
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
  chained_iterfiles  = itertools.chain.from_iterable(iterfiles(unicode(rootdir)) for rootdir   in cfg.indexed_dirs         )
  chained_iteremails = itertools.chain.from_iterable(iteremails(em_folder)       for em_folder in cfg.indexed_email_folders)
  chained_webpages   = itertools.chain.from_iterable(iterwebpages(webpage)       for webpage   in cfg.indexed_urls         )
  for doc, error in itertools.chain(chained_iterfiles, chained_iteremails, chained_webpages):

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

def dbwriter_proc(db_q, dispatcher_shared_data):

  # Connec to the DB
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
      tuples = [(doc.id, doc.type_, doc.locator, doc.mtime, doc.title, doc.extension, doc.title_only, doc.size, doc.word_cnt, doc.unique_word_cnt, doc.from_, doc.to_) for doc in docs]
      dispatcher_shared_data.db_status = 'insert docs ({})'.format(len(tuples))
      conn.cursor().executemany("INSERT INTO doc ('id','type_','locator','mtime','title','extension','title_only','size','word_cnt','unique_word_cnt','from_','to_') VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", tuples)

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

def main():

  # Create tables
  with apsw.Connection(db_path) as conn:
    create_tables(conn)

  # Check if search
  if len(sys.argv) == 3 and sys.argv[1] == 'search':
    print 'Executing search...'
    start_time = time.clock()
    total, cur = search(sys.argv[2], 20, 0)
    elapsed_time = time.clock() - start_time
    print '\n{} documents found in {}\n'.format(total, datetime.timedelta(seconds=elapsed_time))
    syncMenu = cui.Menu()
    for locator, relev, title, title_only in cur:
      disp_str = '[{}] {}'.format(relev, title if title else locator)
      syncMenu.addItem(cui.Item(disp_str, toggle=True, actions=' *', obj=MenuDoc(locator, relev, title, title_only)))
    if syncMenu.items:
      res = syncMenu.show(sort=True)
      if not res:
        return # This means the user pressed ESC in the menu, abort processing
      selected_docs = []
      print
      for item in syncMenu.items:
        if item.actions[0] == '*':
          selected_docs.append(item.obj)
      for selected_doc in selected_docs:
        selected_doc.activate()
    else:
      print 'No results found.'
    return

  # Run indexing
  if len(sys.argv) == 2 and sys.argv[1] == 'index':
    print 'Indexing...'
    start_time = time.clock()

    # Initialize shared mem structures
    # worker process
    dsd = dispatcher_shared_data
    dsd.status = 'Starting'

    # Launch dispatcher process
    disp = mt.Process(target=dispatcher_proc, args=(dsd, indexer_shared_data_array))
    disp.start()

    # Wait for indexing to complete, update status
    curpos = cui.getcurpos()
    c_width = cui.get_console_size()[0] - 10
    while dsd.status != 'Idle':
      time.sleep(0.05)
      cui.setcurpos(curpos.x, curpos.y)
      print
      print '-'*c_width
      print 'status   : {}'.format(cui.str_fill(dsd.status, c_width-18))
      print cui.str_fill('counts   : listed: {:<7}, up-to-date: {:<7}, outdated: {:<7}, new: {:<7}'.format(
      dsd.listed_count, dsd.uptodate_count, dsd.outdated_count, dsd.new_count), c_width-18)
      print 'document : {}'.format(cui.str_fill(dsd.current_doc, c_width-18))
      print 'DB status: {}'.format(cui.str_fill(dsd.db_status, 40))
      print
      print '-'*c_width
      header = ' {:^12} | {:^75} | {:^25}'.format('Progress', 'Document', 'Status')
      print header
      print '-'*c_width
      for i in range(len(indexer_shared_data_array)):
        dat = indexer_shared_data_array[i]
        done_percentage = 0
        print ' {:>12} | {:>75} | '.format(
        dat.doc_done_count, cui.str_fill(dat.current_doc, 75)),
        if dat.status == 'writing':
          col = 'FOREGROUND_GREEN'
        elif dat.status == 'locked':
          col = 'FOREGROUND_RED'
        else:
          col = None
        cui.write_color(cui.str_fill(dat.status, 25), col, endline=True)
      print '-'*c_width

    elapsed_time = time.clock() - start_time
    print
    print 'Indexing completed in {}.'.format(datetime.timedelta(seconds=elapsed_time))
    return

  # Unknown command, print usage
  print 'Usage: idxbeast.py index|search [search string]'

if __name__ == '__main__':
  main()

