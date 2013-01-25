# coding=latin-1

"""
idxbeast.py - simple content indexer.

This script implements a simple document indexing application.

todo: use varint for blob encoding for matches for a given word
todo: use Blob IO to append data to blobs (now possible because of using of
      varint), double size when needed to grow blob
todo: use multiple index DBs based on the first bits of MD5 instead of
      randomly dispatching matches to multiples DBs.
todo: improve ResultSet paging, using LIMIT and OFFSET

Copyright (c) 2012, Francois Jeannotte.
"""

import binascii
import bz2
import collections
import cPickle
import ctypes
import datetime
import getpass
import glob
import hashlib
import itertools
import logging
import logging.handlers
import multiprocessing as mt
import operator
import os
import random
import string
import struct
import subprocess
import sys
import time
import traceback

import bottle
import unidecode
import win32com.client
import yaml

sys.path.append(os.path.join(os.path.dirname(__file__), 'pysak'))
import cio
import datastore
datastore.trace_sql = False # Set this to True to trace SQL statements
import menu
import util

# Constants
doctype_file = 1
doctype_email = 2 

# Initialize data dir, creating it if necessary
data_dir = os.path.expanduser(ur'~\.idxbeast')
assert not os.path.isfile(data_dir)
if not os.path.isdir(data_dir):
  os.mkdir(data_dir)
db_path_doc = os.path.join(data_dir, 'doc.db')

# Initialize config file, creating it if necessary
cfg_file = os.path.join(data_dir, u'settings.yaml')
assert not os.path.isdir(cfg_file)
if not os.path.isfile(cfg_file):
  with open(cfg_file, 'w') as f:
    default_config_str = '''
    indexer_db_count    : 4
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
  indexer_db_count      = cfg_obj.get('indexer_db_count', 4)
  indexer_proc_count    = cfg_obj.get('indexer_proc_count', 4)
  indexed_file_types    = cfg_obj.get('indexed_file_types', 'bat c cpp cs cxx h hpp htm html ini java log md py rst txt xml')
  word_hash_cache_size  = cfg_obj.get('word_hash_cache_size', 10000)
  doc_bundle_size       = cfg_obj.get('doc_bundle_size', 2000)
  indexed_dirs          = cfg_obj.get('indexed_dirs', [])
  indexed_email_folders = cfg_obj.get('indexed_email_folders', [])
  indexed_urls          = cfg_obj.get('indexed_urls', [])

def str_fill(s, length):
  """
  Truncates a string to the given length, using an ellipsis (...) in the
  middle if necessary.

  >>> str_fill('abcdefghijklmnopqrstuvwxyz', 15)
  'abcdef...uvwxyz'
  >>> str_fill('abcdef', 15)
  'abcdef         '
  """
  assert length > 0
  s = str(s)
  if len(s) == length:
    return s
  if len(s) > length:
    if length < 9:
      s = s[-length:]
    else:
      q,r = divmod(length-3, 2)
      s = s[0:q] + '...' + s[-(q+r):]
  if len(s) < length:
    s = s + ' '*(length - len(s))
  assert len(s) == length, 'len(s): {}, length:{}'.format(len(s), length)
  return s

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

class DocumentTable(datastore.SqliteTable):
  """
  The locator should be unique, and should allow unequivocal retrieval of
  the document. For example:
    - file     : the path
    - web page : the URL
    - email    : the EntryId
  The (optional, immutable) title is used to display to the user. Since it is
  immutable, it will not be updated even if it changes in a web page. For
  example:
    - file     : <not used, will display locator>
    - web page : the title of the page
    - email    : the subject
  We use AUTOINCREMENT for the id primary key, because otherwise SQLite may
  reuse ids from previously deleted rows. We don't want this because updated
  documents are deleted from the DB, but their id may still be inside the
  index for a word.
  """
  columns = [('id'             , 'INTEGER PRIMARY KEY AUTOINCREMENT'),
             ('type_'          , 'INTEGER NOT NULL'                 ),
             ('locator'        , 'TEXT UNIQUE NOT NULL'             ),
             ('mtime'          , 'INTEGER'                          ),
             ('title'          , 'TEXT'                             ),
             ('size'           , 'INTEGER'                          ),
             ('word_cnt'       , 'INTEGER NOT NULL'                 ),
             ('unique_word_cnt', 'INTEGER NOT NULL'                 ),
             ('from_'          , 'TEXT'                             ),
             ('to_'            , 'TEXT'                             )]

class MatchTable(datastore.SqliteTable):
  """
  id     : the id is the truncated MD5 of the flattened (été -> ete) word.
  matches: a pickled/bz2 dict laid out as follows:
             - doc_id1: relev
             - doc_id2: relev
  """
  columns = [('id'     , 'INTEGER PRIMARY KEY'),
             ('matches', 'BLOB NOT NULL'      )]

class SessionTable(datastore.SqliteTable):
  """
  Store sessions (for server mode).
  """
  columns = [('id'  , 'INTEGER PRIMARY KEY'),
             ('sid' , 'TEXT NOT NULL'      ),
             ('user', 'TEXT'               )]

class UserTable(datastore.SqliteTable):
  """
  Store users for server mode.
  """
  columns = [('id'      , 'INTEGER PRIMARY KEY'),
             ('name'    , 'TEXT NOT NULL'      ),
             ('pwd_hash', 'TEXT NOT NULL'      )]

supported_extensions = set(''.join(['.', ext]) for ext in cfg.indexed_file_types.split())
def is_file_handled(path):
  root, ext = os.path.splitext(path)
  return ext in supported_extensions

class Document(object):
  def index(self):
    try:
      words = collections.defaultdict(list)
      for i,w in enumerate(w for w in unidecode.unidecode(self.get_text()).translate(translate_table).split() if len(w) > 1):
        words[w].append(i)
      return [(get_word_hash(w), len(lst), sum(lst)/len(lst)) for w,lst in words.iteritems()]
    except Exception, ex:
      log.warning('Exception while processing {}, exception: {}'.format(self, ex))
      return 0, dict()

class File(Document):
  def __init__(self, path):
    self.type_   = doctype_file
    self.locator = os.path.abspath(path)
    self.mtime   = os.path.getmtime(self.locator)
    self.title   = self.locator
    self.size    = os.path.getsize(self.locator)
    self.from_   = None
    self.to_     = None
  def __repr__(self):
    return '<File ' + ' ' + self.locator + '>'
  def get_text(self):
    with open(self.locator, 'r') as f:
      return ''.join((self.locator, ' ', f.read()))

def iterfiles(rootdir):
  assert os.path.isdir(rootdir), rootdir
  for f, error in util.walkdir(rootdir, maxdepth=9999, listdirs=False, file_filter=is_file_handled, file_wrapper=File):
    yield f, error

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
  def __init__(self, locator, relev, title=None):
    self.locator = locator
    self.relev = relev
    self.title = title
    if self.title == None:
      self.title = self.locator
    self.disp_str = u'[{}] {}'.format(self.relev, self.title)
  def activate(self):
    if os.path.isfile(self.locator):
      subprocess.Popen(['notepad.exe', self.locator])
    else:
      outlook = win32com.client.Dispatch('Outlook.Application')
      mapi = outlook.GetNamespace('MAPI')
      mapi.GetItemFromId(self.locator).Display()

class ResultSet(object):
  def __init__(self, matches):
    conn = datastore.SqliteTable.connect(db_path_doc, DocumentTable)
    self.relevs = dict(matches)
    tuples = [(i,) for i,relev in matches]
    self.count = sum(1 for x in DocumentTable.selectmany(conn, '1', ['id'], tuples))
    self.cur = DocumentTable.selectmany(conn, 'id,locator,title', ['id'], tuples)
  def __len__(self):
    return self.count
  def set_page_size(self, size):
    self.page_size = size
    self.page_count, r = divmod(self.count, self.page_size)
    if r != 0:
      self.page_count += 1
  def get_page(self, idx):
    i = idx*self.page_size
    return list(MenuDoc(loc,self.relevs[id],title) for (id,loc,title) in itertools.islice(self.cur, self.page_size))
  
def search(words):
  
  # Extract the matches for all words
  matches = []
  conns_idx = [datastore.SqliteTable.connect(p, MatchTable) for p in glob.glob(os.path.join(data_dir, 'idx-*.db'))]
  for word_hash in (get_word_hash(w) for w in unidecode.unidecode(words).translate(translate_table).split()):
    cur_dict = dict()
    for conn_idx in conns_idx:
      for row_matches, in MatchTable.select(conn_idx, 'matches', id=word_hash):
        for doc,cnt,avg_idx in cPickle.loads(bz2.decompress(row_matches)):
          cur_dict[doc] = cnt
    matches.append(cur_dict)

  # Loop on intersected keys and sum their relevences
  results = dict()
  intersect_docs = reduce(set.intersection, (set(d.keys()) for d in matches))
  for doc in intersect_docs:
    results[doc] = sum(d[doc] for d in matches)
  matches = sorted(results.iteritems(), key=operator.itemgetter(1), reverse=True)

  # Construct and return the ResultSet
  return ResultSet(matches)

class IndexerSharedData(ctypes.Structure):
  _fields_ = [('db_id'         , ctypes.c_char*10 ), # e.g., doc, idx-01, idx-02
              ('db_status'     , ctypes.c_char*10 ), # e.g., idle, locked, writing
              ('doc_done_count', ctypes.c_int     ),
              ('current_doc'   , ctypes.c_char*380),
              ('pid'           , ctypes.c_int     ),
              ('bundle_size'   , ctypes.c_int     )]

class DispatcherSharedData(ctypes.Structure):
  _fields_ = [('status'          , ctypes.c_char*40),
              ('listed_count'    , ctypes.c_int    ),
              ('uptodate_count'  , ctypes.c_int    ),
              ('outdated_count'  , ctypes.c_int    ),
              ('new_count'       , ctypes.c_int    ),
              ('error_count'     , ctypes.c_int    ),
              ('current_doc'     , ctypes.c_char*380)]

# Create shared mem used when indexing. The size of the indexer array
# will determine the number of indexer worker processes
dispatcher_shared_data    = mt.Value(DispatcherSharedData)
indexer_shared_data_array = mt.Array(IndexerSharedData, cfg.indexer_proc_count)
dispatcher_shared_data.status = 'Idle'
for dat in indexer_shared_data_array:
  dat.db_id = ''
  dat.db_status = ''

def dispatcher_proc_flush(indexer_shared_data_array, worker_procs, bundle, db_lock_doc, db_lock_idx, db_id):
  if len(bundle) == 0:
    return
  for i in itertools.cycle(range(len(worker_procs))):
    if worker_procs[i] and worker_procs[i].is_alive():
      time.sleep(0.01)
    else:
      worker_procs[i] = mt.Process(target=indexer_proc, args=(i, indexer_shared_data_array, bundle, db_lock_doc, db_lock_idx, db_id))
      worker_procs[i].start()
      del bundle[:]
      return

def dispatcher_proc(dispatcher_shared_data, indexer_shared_data_array):

  # Create the worker processes slots
  worker_procs = [None for s in indexer_shared_data_array]

  # Read the entire document DB in memory
  dispatcher_shared_data.status = 'Load initial document list'
  initial_docs = dict()
  conn = datastore.SqliteTable.connect(db_path_doc, DocumentTable)
  next_doc_id = 0
  for id,locator,mtime in DocumentTable.select(conn, 'id,locator,mtime'):
    initial_docs[locator] = id,mtime
    next_doc_id = max(next_doc_id, id)
  next_doc_id += 1

  # Create DB locks
  db_lock_doc = mt.Lock()
  db_locks_idx = [mt.Lock() for i in range(cfg.indexer_db_count)]
  current_idx_db_id = random.randint(0, cfg.indexer_db_count-1)

  # List all documents
  updated_docs   = []
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

      dispatcher_shared_data.current_doc = doc.title
      init_doc = initial_docs.get(doc.locator)
      if init_doc == None or init_doc[1] < doc.mtime:
        if init_doc != None:
          dispatcher_shared_data.outdated_count += 1
          doc.old_id = init_doc[0]
        else:
          dispatcher_shared_data.new_count += 1
        doc.id = next_doc_id
        next_doc_id += 1
        updated_docs.append(doc)
      else:
        dispatcher_shared_data.uptodate_count += 1

      # If we reached the bundle size, dispatch
      if len(updated_docs) >= cfg.doc_bundle_size:
        dispatcher_shared_data.status = 'Waiting for free indexer slot'
        dispatcher_proc_flush(indexer_shared_data_array, worker_procs, updated_docs, db_lock_doc, db_locks_idx[current_idx_db_id], current_idx_db_id)
        current_idx_db_id = (current_idx_db_id + 1) % cfg.indexer_db_count
        updated_docs = []
        
    except Exception, ex:
      log.error('Dispatcher: error while processing doc {}, error: {}'.format(doc, traceback.format_exc()))

  # Final flush
  if len(updated_docs) >= 0:
    dispatcher_shared_data.status = 'Waiting for free indexer slot'
    dispatcher_proc_flush(indexer_shared_data_array, worker_procs, updated_docs, db_lock_doc, db_locks_idx[current_idx_db_id], current_idx_db_id)
    current_idx_db_id = (current_idx_db_id + 1) % cfg.indexer_db_count
    updated_docs = []

  # At this point we can close the DB connection
  conn.close()

  # Wait on indexer processes
  dispatcher_shared_data.status = 'Waiting on indexer processes'
  [p.join() for p in worker_procs if p]
  dispatcher_shared_data.status = 'Idle'

def indexer_proc(i, shared_data_array, bundle, db_lock_doc, db_lock_idx, db_id):

  # Index documents
  assert len(bundle) > 0
  shared_data_array[i].db_id          = ''
  shared_data_array[i].db_status      = ''
  shared_data_array[i].doc_done_count = 0
  shared_data_array[i].current_doc    = ''
  shared_data_array[i].pid            = os.getpid()
  shared_data_array[i].bundle_size    = len(bundle)
  words = collections.defaultdict(list)
  docs_new          = []
  doc_ids_to_delete = []
  for doc in bundle:
    shared_data_array[i].current_doc = doc.title
    docs_new.append(doc)
    if hasattr(doc, 'old_id'):
      doc_ids_to_delete.append((doc.old_id,))
    doc.word_cnt = 0
    doc.unique_word_cnt = 0
    for w,cnt,avg_idx in doc.index():
      words[w].append((doc.id,cnt,avg_idx))
      doc.word_cnt += cnt
      doc.unique_word_cnt += 1
    shared_data_array[i].doc_done_count += 1

  # Flush words
  db_id_str = 'idx-{:02d}'.format(db_id)
  db_path_idx = os.path.join(data_dir, db_id_str + '.db')
  shared_data_array[i].db_id = db_id_str
  shared_data_array[i].db_status = 'locked'
  with db_lock_idx:
    conn = datastore.SqliteTable.connect(db_path_idx, MatchTable)
    shared_data_array[i].db_status = 'writing'
    tuples_upd = []
    tuples_new = []
    for word_hash,matches in words.iteritems():
      for row_matches, in MatchTable.select(conn, 'matches', id=word_hash):
        matches.extend(cPickle.loads(bz2.decompress(row_matches)))
        tuples_upd.append((buffer(bz2.compress(cPickle.dumps(matches))), word_hash))
        break
      else:
        tuples_new.append((word_hash, buffer(bz2.compress(cPickle.dumps(matches)))))
    MatchTable.insertmany(conn, ['id', 'matches'], tuples_new)
    MatchTable.updatemany(conn, ['matches'], ['id'], tuples_upd)
    conn.close()

  # Flush updated docs
  shared_data_array[i].db_id = 'doc'
  tuples = ((doc.id, doc.type_, doc.locator, doc.mtime, doc.title, doc.size, doc.word_cnt, doc.unique_word_cnt, doc.from_, doc.to_) for doc in docs_new)
  shared_data_array[i].db_status = 'locked'
  with db_lock_doc:
    conn = datastore.SqliteTable.connect(db_path_doc, DocumentTable)
    shared_data_array[i].db_status = 'writing'

    # Delete outdated documents
    if len(doc_ids_to_delete) > 0:
      DocumentTable.deletemany(conn, ['id'], doc_ids_to_delete)

    # Insert new/updated documents
    DocumentTable.insertmany(conn, cols=['id', 'type_', 'locator', 'mtime', 'title', 'size', 'word_cnt', 'unique_word_cnt', 'from_', 'to_'], tuples=tuples)

    conn.close()

  shared_data_array[i].db_id     = ''
  shared_data_array[i].db_status = ''
  shared_data_array[i].doc_done_count = 0
  shared_data_array[i].current_doc    = ''
  shared_data_array[i].pid            = 0
  shared_data_array[i].bundle_size    = 0

server_conn = None

@bottle.route('/jquery.js')
def bottle_idxbeast_jquery():
  return bottle.static_file('jquery.js', '.')

@bottle.route('/jquery.cookie.js')
def bottle_idxbeast_jquery():
  return bottle.static_file('jquery.cookie.js', '.')

@bottle.route('/jquery.encoding.digests.sha1.js')
def bottle_idxbeast_jquery():
  return bottle.static_file('jquery.encoding.digests.sha1.js', '.')

@bottle.route('/idxbeast')
def bottle_idxbeast():
  sid = bottle.request.get_cookie('sid')
  print 'sid:', sid
  if sid:
    for user, in SessionTable.select(server_conn, 'user', sid=sid):
      print 'User {} authenticated'.format(user)
      return bottle.template('idxbeast.tpl', page='search')
    else:
      user_name = bottle.request.query.user
      user_auth = bottle.request.query.auth
      if user_name and user_auth:
        for pwd_hash, in UserTable.select(server_conn, 'pwd_hash', name=user_name):
          concat = '{}{}'.format(pwd_hash, sid)
          computed_user_auth = hashlib.sha1(concat).hexdigest()
          if user_auth == computed_user_auth:
            SessionTable.insert(server_conn, sid=sid, user=user_name)
            return bottle.template('idxbeast.tpl', page='search')
          else:
            print 'Failed login'
          break
        else:
          print 'Invalid user'
      return bottle.template('idxbeast.tpl', page='login')
  else:
    print 'setting cookie'
    bottle.response.set_cookie('sid', binascii.hexlify(os.urandom(16)), path='/')
    return bottle.template('idxbeast.tpl', page='login')

@bottle.route('/idxbeast/logout')
def bottle_idxbeast_logout():
  bottle.response.delete_cookie('sid', path='/')
  return 'You have been logged out.'
  
@bottle.route('/idxbeast/api/search')
def bottle_idxbeast_api_search():
  query_str = bottle.request.query.q
  if query_str:
    docs = search(server_conn, query_str)
    docs.set_page_size(25)
    docs_list = list()
    for doc in docs.get_page(0):
      docs_list.append({'id': doc.id, 'title': doc.disp_str})
    return {'res': docs_list}

@bottle.route('/idxbeast/api/activate')
def bottle_idxbeast_api_activate():
  doc_id = bottle.request.query.doc_id
  if doc_id:
    for locator, in DocumentTable.select(server_conn, 'locator', id=int(doc_id)):
      d = MenuDoc(locator=locator)
      d.activate()
      break
    return {}

def run_server(conn):
  global server_conn
  server_conn = conn
  bottle.run(host='localhost', port=8080, debug=True, reloader=True)

def main():

  # Check if config
  if len(sys.argv) > 1 and sys.argv[1] == 'config':
    print 'Configuration file is located at {}, opening default editor...'.format(cfg_file)
    subprocess.call('notepad.exe ' + cfg_file)
    return

  # Check if server
  #if len(sys.argv) > 1 and sys.argv[1] == 'server':
  #  run_server(conn)
  #  return

  # Check if add user (for web server)
  #if len(sys.argv) > 1 and sys.argv[1] == 'user':
  #  user_name = sys.argv[2]
  #  if UserTable.exists(conn, name=user_name):
  #    print 'User {} already exists'.format(user_name)
  #  else:
  #    print 'Creating user {}'.format(user_name)
  #    pwd = getpass.getpass()
  #    UserTable.insert(conn, name=user_name, pwd_hash=hashlib.sha1(pwd).hexdigest())
  #  return
    
  # Check if search
  if len(sys.argv) == 3 and sys.argv[1] == 'search':
    print 'Executing search...'
    start_time = time.clock()
    docs = search(sys.argv[2])
    docs.set_page_size(20)
    docs_page = docs.get_page(0)
    elapsed_time = time.clock() - start_time
    print '\n{} documents found in {}, showing page 0 ({}-{})\n'.format(len(docs), datetime.timedelta(seconds=elapsed_time), 0, len(docs_page)-1)
    if docs:
      syncMenu = menu.Menu()
      for doc in docs_page:
        syncMenu.addItem(menu.Item(doc.disp_str, toggle=True, actions=' *', obj=doc))
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
    curpos = cio.getcurpos()
    c_width = cio.get_console_size()[0] - 10
    while dsd.status != 'Idle':
      time.sleep(0.05)
      cio.setcurpos(curpos.x, curpos.y)
      print
      print '-'*c_width
      print 'status  : {}'.format(str_fill(dsd.status, c_width-18))
      print str_fill('counts  : listed: {:<7}, up-to-date: {:<7}, outdated: {:<7}, new: {:<7}'.format(
      dsd.listed_count, dsd.uptodate_count, dsd.outdated_count, dsd.new_count), c_width-18)
      print 'document: {}'.format(str_fill(dsd.current_doc, c_width-18))
      print
      print '-'*c_width
      header = '{:^5} | {:^18} | {:^55} | {:^6} | {:^8}'.format('PID', 'Progress', 'Document', 'DB', 'DB Status')
      print header
      print '-'*c_width
      for i in range(len(indexer_shared_data_array)):
        dat = indexer_shared_data_array[i]
        done_percentage = 0
        if dat.bundle_size > 0:
          done_percentage = 100*dat.doc_done_count / dat.bundle_size
        print '{:>5} | {:>4} / {:>4} ({:>3}%) | {:>55} | {:^6} | '.format(
        dat.pid, dat.doc_done_count, dat.bundle_size, done_percentage, str_fill(dat.current_doc, 55), dat.db_id),
        if dat.db_status == 'writing':
          col = 'FOREGROUND_GREEN'
        elif dat.db_status == 'locked':
          col = 'FOREGROUND_RED'
        else:
          col = None
        cio.write_color(str_fill(dat.db_status, 10), col, endline=True)
      print '-'*c_width

    elapsed_time = time.clock() - start_time
    print
    print 'Indexing completed in {}.'.format(datetime.timedelta(seconds=elapsed_time))
    return

  # Unknown command, print usage
  print 'Usage: idxbeast.py index|search [search string]'

if __name__ == '__main__':
  main()

