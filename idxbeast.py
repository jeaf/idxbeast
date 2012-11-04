# coding=latin-1

"""
idxbeast.py - simple content indexer.

This script implements a simple document indexing application. The application
settings are modified by changing the parameters directly in the cfg class.
todo: support a better way to handle the configuration.

Copyright (c) 2012, Francois Jeannotte.
"""

import binascii
import bz2
import collections
import cPickle
import ctypes
import datetime
import getpass
import hashlib
import itertools
import logging
import logging.handlers
import multiprocessing as mt
import operator
import os
import sqlite3
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

sys.path.append('pysak')
import cio
import datastore
datastore.trace_sql = False # Set this to True to trace SQL statements
import menu
import util

# Initialize data dir, creating it if necessary
data_dir = os.path.expanduser(ur'~\.idxbeast')
assert not os.path.isfile(data_dir)
if not os.path.isdir(data_dir):
  os.mkdir(data_dir)
db_path = os.path.join(data_dir, 'idxbeast.db')

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
log_handler   = logging.handlers.RotatingFileHandler(os.path.join(data_dir, 'log.txt'), maxBytes=1024**2, backupCount=5)
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
  indexed_urls          = []

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
  columns = [('id'       , 'INTEGER PRIMARY KEY AUTOINCREMENT'),
             ('mtime'    , 'INTEGER'                          ),
             ('locator'  , 'TEXT NOT NULL'                    ),
             ('title'    , 'TEXT'                             )]

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
  def index(self, words):
    try:
      for word_hash in (get_word_hash(w) for w in unidecode.unidecode(self.get_text()).translate(translate_table).split()):
        word_entry = words[word_hash]
        word_entry[self.id] = word_entry.get(self.id, 0) + 1
    except Exception, ex:
      print 'Exception while processing {}, exception follows'.format(self)
      traceback.print_exc()

class File(Document):
  def __init__(self, path):
    super(File, self).__init__()
    self.locator = os.path.abspath(path)
    self.title = self.locator
    self.mtime = os.path.getmtime(self.locator)
  def __repr__(self):
    return '<File ' + ' ' + self.locator + '>'
  def get_text(self):
    with open(self.locator, 'r') as f:
      return ''.join((self.locator, ' ', f.read()))

def iterfiles(rootdir):
  assert os.path.isdir(rootdir), rootdir
  for f, error in util.walkdir(rootdir, maxdepth=9999, listdirs=False, file_filter=is_file_handled, file_wrapper=File):
    if error != None:
      log.warning('Cannot process file {}, error: {}'.format(f, error))
    else:
      yield f

class OutlookEmail(Document):
  """
  Represents a email document from Microsoft Outlook. Reference for MailItem
  objects can be found at
  http://msdn.microsoft.com/en-us/library/aa210946(v=office.11).aspx
  """
  def __init__(self, entry_id, mapi, from_, to_, subject, rt):
    super(OutlookEmail, self).__init__()
    self.locator = entry_id
    self.mapi = mapi
    self.from_ = from_
    self.to_ = to_
    self.title = subject
    self.mtime = time.mktime(datetime.datetime(rt.year, rt.month, rt.day, rt.hour, rt.minute, rt.second).timetuple())
    self.update_required = False
    row = DocumentTable.selectone(locator=self.locator)
    if row == None or row.mtime < self.mtime:
      self.update_required = True
      if row != None:
        DocumentTable.delete(id=row.id)
      self.id = DocumentTable.insert(locator=self.locator, title=self.title)
  def __repr__(self):
    return '<Email ' + str(self.title) + '>'
  def get_text(self):
    mail_item = self.mapi.GetItemFromId(self.locator)
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
        table.Columns.Add('Subject')
        table.Columns.Add('ReceivedTime')
        while not table.EndOfTable:
          try:
            row = table.GetNextRow()
            yield OutlookEmail(row['EntryId'],
                               mapi,
                               row['SenderName'],
                               ' '.join((row['To'], row['CC'], row['BCC'])),
                               row['Subject'],
                               row['ReceivedTime'])
          except Exception, ex:
            print 'Exception while processing Outlook item, information follows'
            traceback.print_exc()
      except Exception, ex:
        print 'Exception while processing Outlook folder, information follows'
        traceback.print_exc()

def search(conn, words):

  # Extract the matches for all words
  matches = []
  for word_hash in (get_word_hash(w) for w in unidecode.unidecode(words).translate(translate_table).split()):
    row = MatchTable.selectone(conn, id=word_hash)
    if row != None:
      matches.append(cPickle.loads(bz2.decompress(row.matches)))
    else:
      matches.append(dict())

  # Loop on intersected keys and sum their relevences
  results = dict()
  intersect_docs = reduce(set.intersection, (set(d.keys()) for d in matches))
  for doc in intersect_docs:
    results[doc] = sum(d[doc] for d in matches)
  matches = sorted(results.iteritems(), key=operator.itemgetter(1), reverse=True)

  # Resolve the documents
  docs = []
  print 'Resolving documents...'
  for match,relev in matches:
    rows = DocumentTable.select(conn, id=match)
    for row in rows:
      new_doc = MenuDoc(relev, locator=row.locator, title=row.title)
      new_doc.id = match
      docs.append(new_doc)
  return docs

class MenuDoc(object):
  def __init__(self, relev=None, locator=None, title=None):
    self.relev   = relev
    self.locator = locator
    self.title   = title
    if self.title == None:
      self.title = self.locator
    self.disp_str = u'[{}] {}'.format(relev, self.title)
  def activate(self):
    if os.path.isfile(self.locator):
      subprocess.Popen(['notepad.exe', self.locator])
    else:
      outlook = win32com.client.Dispatch('Outlook.Application')
      mapi = outlook.GetNamespace('MAPI')
      mapi.GetItemFromId(self.locator).Display()

class IndexerSharedData(ctypes.Structure):
  _fields_ = [('status'        , ctypes.c_char*40 ),
              ('doc_done_count', ctypes.c_int     ),
              ('current_doc'   , ctypes.c_char*380),
              ('pid'           , ctypes.c_int     ),
              ('bundle_size'   , ctypes.c_int     )]

class DispatcherSharedData(ctypes.Structure):
  _fields_ = [('status'          , ctypes.c_char*40),
              ('total_listed'    , ctypes.c_int    ),
              ('current_doc'     , ctypes.c_char*380)]

# Create shared mem used when indexing. The size of the indexer array
# will determine the number of indexer worker processes
dispatcher_shared_data    = mt.Value(DispatcherSharedData)
indexer_shared_data_array = mt.Array(IndexerSharedData, cfg.indexer_proc_count)
dispatcher_shared_data.status = 'Idle'
for dat in indexer_shared_data_array:
  dat.status = 'Idle'

def dispatcher_proc_flush(indexer_shared_data_array, worker_procs, bundle, db_lock):
  if len(bundle) == 0:
    return
  for i in itertools.cycle(range(len(worker_procs))):
    if worker_procs[i] and worker_procs[i].is_alive():
      time.sleep(0.1)
    else:
      worker_procs[i] = mt.Process(target=indexer_proc, args=(i, indexer_shared_data_array, bundle, db_lock))
      worker_procs[i].start()
      del bundle[:]
      return

def dispatcher_proc(dispatcher_shared_data, indexer_shared_data_array, selected_roots_id, db_lock):

  # Connect to DB
  conn = datastore.SqliteTable.connect(db_path, DocumentTable, MatchTable)

  # Create the worker processes slots
  worker_procs = [None for s in indexer_shared_data_array]

  # List all documents
  # todo: possible optimization: don't create documents one by one in the DB,
  #       but create them in one shot with a executemany call. It is simpler
  #       to do it one by one because the generation of the ID is handled by
  #       the DB.
  dispatcher_shared_data.status = 'Listing documents'
  all_updated_docs   = []
  doc_ids_to_delete  = []
  chained_iterfiles  = itertools.chain.from_iterable(iterfiles(rootdir)    for rootdir   in cfg.indexed_dirs         )
  chained_iteremails = itertools.chain.from_iterable(iteremails(em_folder) for em_folder in cfg.indexed_email_folders)
  chained_webpages   = itertools.chain.from_iterable(iterwebpages(webpage) for webpage   in cfg.indexed_urls         )
  for doc in itertools.chain(chained_iterfiles, chained_iteremails, chained_webpages):
    try:
      dispatcher_shared_data.total_listed += 1
      dispatcher_shared_data.current_doc = doc.title
      row = DocumentTable.selectone(conn, locator=doc.locator)
      if row == None or row.mtime < doc.mtime:
        if row != None:
          doc_ids_to_delete.append((row.id,))
        doc.id = DocumentTable.insert(conn, locator=doc.locator)
        all_updated_docs.append(doc)
      else:
        # todo: count the skipped documents in the dispatcher shared memory
        pass
    except Exception, ex:
      log.error('Dispatcher: error while processing doc {}, error: {}'.format(doc, ex))

  # Update or create documents in the DB
  dispatcher_shared_data.status = 'Deleting outdated documents'
  if len(doc_ids_to_delete) > 0:
    DocumentTable.deletemany(conn, ['id'], doc_ids_to_delete)

  # At this point we can close the DB connection
  conn.close()

  # Dispatch bundles to indexer processes
  dispatcher_shared_data.status = 'Dispatching bundles'
  for bundle in (all_updated_docs[i:i+cfg.doc_bundle_size] for i in range(0, len(all_updated_docs), cfg.doc_bundle_size)):
    dispatcher_proc_flush(indexer_shared_data_array, worker_procs, bundle, db_lock)

  # Wait on indexer processes
  dispatcher_shared_data.status = 'Waiting on indexer processes'
  [p.join() for p in worker_procs if p]
  dispatcher_shared_data.status = 'Idle'

def indexer_proc(i, shared_data_array, bundle, db_lock):

  # Index documents
  assert len(bundle) > 0
  shared_data_array[i].status         = 'Indexing'
  shared_data_array[i].doc_done_count = 0
  shared_data_array[i].current_doc    = ''
  shared_data_array[i].pid            = os.getpid()
  shared_data_array[i].bundle_size    = len(bundle)
  words = collections.defaultdict(dict)
  updated_docs = []
  for doc in bundle:
    shared_data_array[i].current_doc = doc.title
    updated_docs.append(doc)
    doc.index(words)
    shared_data_array[i].doc_done_count += 1
  shared_data_array[i].current_doc = ''

  # Connect to database
  shared_data_array[i].status         = 'Waiting on DB lock (connection)'
  with db_lock:
    conn = datastore.SqliteTable.connect(db_path, DocumentTable, MatchTable)

  # Flush words
  shared_data_array[i].status = 'Waiting on DB lock (match update)'
  with db_lock:
    shared_data_array[i].status = 'Writing matches'
    tuples_upd = []
    tuples_new = []
    for word_hash,matches in words.iteritems():
      row = MatchTable.selectone(conn, id=word_hash)
      if row != None:
        matches.update(cPickle.loads(bz2.decompress(row.matches)))
        tuples_upd.append((sqlite3.Binary(bz2.compress(cPickle.dumps(matches))), word_hash))
      else:
        tuples_new.append((word_hash, sqlite3.Binary(bz2.compress(cPickle.dumps(matches)))))
    MatchTable.insertmany(conn, ['id', 'matches'], tuples_new)
    MatchTable.updatemany(conn, ['matches'], ['id'], tuples_upd)

  # Flush updated docs
  tuples = ((doc.mtime,doc.id) for doc in updated_docs)
  shared_data_array[i].status = 'Waiting on DB lock (doc. updates)'
  with db_lock:
    shared_data_array[i].status = 'Writing document updates'
    DocumentTable.updatemany(conn, val_cols=('mtime',), key_cols=('id',), tuples=tuples)

  conn.close()

  shared_data_array[i].status = 'Idle'

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
    authenticated_session = SessionTable.selectone(server_conn, sid=sid)
    if authenticated_session:
      print authenticated_session
      return bottle.template('idxbeast.tpl', page='search')
    else:
      user_name = bottle.request.query.user
      user_auth = bottle.request.query.auth
      if user_name and user_auth:
        user_col = UserTable.selectone(server_conn, name=user_name)
        if user_col:
          concat = '{}{}'.format(user_col.pwd_hash, sid)
          computed_user_auth = hashlib.sha1(concat).hexdigest()
          if user_auth == computed_user_auth:
            SessionTable.insert(server_conn, sid=sid, user=user_name)
            return bottle.template('idxbeast.tpl', page='search')
          else:
            print 'Failed login'
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
    docs_list = list()
    if len(docs) > 25:
      docs = docs[:25]
    for doc in docs:
      docs_list.append({'id': doc.id, 'title': doc.disp_str})
    return {'res': docs_list}

@bottle.route('/idxbeast/api/activate')
def bottle_idxbeast_api_activate():
  doc_id = bottle.request.query.doc_id
  if doc_id:
    row = DocumentTable.selectone(server_conn, id=int(doc_id))
    if row:
      d = MenuDoc(locator=row.locator)
      d.activate()
      return {}
    else:
      return {}

def run_server(conn):
  global server_conn
  server_conn = conn
  bottle.run(host='localhost', port=8080, debug=True, reloader=True)

def conform_str(s, width):
  if len(s) == width:
    return s
  if len(s) < width:
    return s + ' '*(width - len(s))
  return s[0:width]

def main():

  # Init DB
  print 'DB: {}'.format(db_path)
  conn = datastore.SqliteTable.connect(db_path, DocumentTable, MatchTable, SessionTable, UserTable)
  with conn:
    print 'Creating locator index...',
    conn.execute("CREATE INDEX IF NOT EXISTS locator_idx ON tbl_DocumentTable ('locator')")
    print 'Done.'

  # Check if config
  if len(sys.argv) > 1 and sys.argv[1] == 'config':
    print 'Configuration file is located at {}, opening default editor...'.format(cfg_file)
    subprocess.call('notepad.exe ' + cfg_file)
    return

  # Check if server
  if len(sys.argv) > 1 and sys.argv[1] == 'server':
    run_server(conn)
    return

  # Check if add user (for web server)
  if len(sys.argv) > 1 and sys.argv[1] == 'user':
    user_name = sys.argv[2]
    if UserTable.exists(conn, name=user_name):
      print 'User {} already exists'.format(user_name)
    else:
      print 'Creating user {}'.format(user_name)
      pwd = getpass.getpass()
      UserTable.insert(conn, name=user_name, pwd_hash=hashlib.sha1(pwd).hexdigest())
    return
    
  # Check if search
  if len(sys.argv) == 3 and sys.argv[1] == 'search':
    print 'Executing search...'

    docs = search(conn, sys.argv[2])
    if docs:
      if len(docs) > 25:
        print
        print '*** Warning: only showing the 25 most relevant results ***'
        print
        docs = docs[:25]
      syncMenu = menu.Menu()
      for doc in docs:
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
    dispatcher_shared_data.status = 'Starting'
    for dat in indexer_shared_data_array:
      dat.status = 'Idle'

    # Launch dispatcher process
    db_lock = mt.Lock()
    disp = mt.Process(target=dispatcher_proc, args=(dispatcher_shared_data, indexer_shared_data_array, None, db_lock))
    disp.start()

    # Wait for indexing to complete, update status
    curpos = cio.getcurpos()
    c_width = cio.get_console_size()[0] - 10
    while dispatcher_shared_data.status != 'Idle':
      time.sleep(0.05)
      cio.setcurpos(curpos.x, curpos.y)
      print
      print '-'*c_width
      print 'Dispatcher'
      print '-'*c_width
      print conform_str('status          : {}'.format(dispatcher_shared_data.status)      , c_width)
      print conform_str('documents listed: {}'.format(dispatcher_shared_data.total_listed), c_width)
      print conform_str('current document: {}'.format(dispatcher_shared_data.current_doc) , c_width)
      print
      print '-'*c_width
      print 'Indexer processes'
      print '-'*c_width
      for i in range(len(indexer_shared_data_array)):
        dat = indexer_shared_data_array[i]
        done_percentage = 0
        if dat.bundle_size > 0:
          done_percentage = 100*dat.doc_done_count / dat.bundle_size
        print '#{} [PID {}]'.format(i, dat.pid)
        print conform_str('   status:           {}'.format(dat.status)                                                     , c_width)
        print conform_str('   progress:         {:>3} / {:>3} ({:>2}%)'.format(dat.doc_done_count, dat.bundle_size, done_percentage), c_width)
        print conform_str('   current document: {}'.format(dat.current_doc, c_width)                                       , c_width)
    elapsed_time = time.clock() - start_time
    print
    print 'Indexing completed in {}.'.format(datetime.timedelta(seconds=elapsed_time))
    return

  # Unknown command, print usage
  print 'Usage: idxbeast.py index|search [search string]'

if __name__ == '__main__':
  main()

