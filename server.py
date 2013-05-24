import apsw
import bottle

import core

db_path = None

@bottle.route('/idxbeast/images/idxbeast_small.jpg')
def bottle_idxbeast_images():
    return bottle.static_file('idxbeast_small.jpg', '.')

@bottle.route('/idxbeast')
def bottle_idxbeast():
    doc_id = bottle.request.query.d
    if doc_id:
        with apsw.Connection(db_path) as conn:
            for loc, in conn.cursor().execute('SELECT locator FROM doc WHERE id=?', (doc_id,)):
                bottle.response.content_type = 'text/plain; charset=UTF8'
                with open(unicode(loc), 'r') as f:
                    return f.read()
            return 'Document not found'
    else:
        query_str = bottle.request.query.q
        total, cursor = core.search(apsw.Connection(db_path), query_str, 20, 0)
        return bottle.template('idxbeast', cursor=cursor)

def run(_db_path):
    global db_path
    db_path = _db_path
    bottle.run(host='localhost', port=8080, debug=True, reloader=True)

