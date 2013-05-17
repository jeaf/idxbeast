import bottle

import core

db_path = None

@bottle.route('/idxbeast/images/idxbeast.jpg')
def bottle_idxbeast_images():
    return bottle.static_file('idxbeast.jpg', '.')

@bottle.route('/idxbeast')
def bottle_idxbeast():
    query_str = bottle.request.query.q
    total, cursor = core.search(db_path, query_str, 20, 0)
    return bottle.template('idxbeast', cursor=cursor)

def run(_db_path):
    global db_path
    db_path = _db_path
    bottle.run(host='localhost', port=8080, debug=True, reloader=True)

