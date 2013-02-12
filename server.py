import bottle

import core

@bottle.route('/idxbeast/images/idxbeast.jpg')
def bottle_idxbeast_images():
  return bottle.static_file('idxbeast.jpg', '.')

@bottle.route('/idxbeast')
def bottle_idxbeast():
  query_str = bottle.request.query.q
  total, cursor = core.search(query_str, 20, 0)
  return bottle.template('idxbeast', cursor=cursor)

def run_server():
  bottle.run(host='localhost', port=8080, debug=True, reloader=True)

def main():
  run_server()

if __name__ == '__main__':
  main()

