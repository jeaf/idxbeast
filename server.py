import bottle

#class SessionTable(datastore.SqliteTable):
#  """
#  Store sessions (for server mode).
#  """
#  columns = [('id'  , 'INTEGER PRIMARY KEY'),
#             ('sid' , 'TEXT NOT NULL'      ),
#             ('user', 'TEXT'               )]
#
#class UserTable(datastore.SqliteTable):
#  """
#  Store users for server mode.
#  """
#  columns = [('id'      , 'INTEGER PRIMARY KEY'),
#             ('name'    , 'TEXT NOT NULL'      ),
#             ('pwd_hash', 'TEXT NOT NULL'      )]

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

if __name__ == '__main__':
  main()

