import apsw
from   contextlib import closing
import doctest
import fnmatch
import importlib
import logging
import os
import os.path as op
import shutil
import tempfile
import time

import core

script_dir = op.dirname(op.abspath(__file__))

def assert_eq(expected, actual):
    assert expected == actual, 'expected: {}, actual: {}'.format(expected, actual)

def assert_fail(msg):
    assert False, msg

class TempDir(object):
  """
  Allow the creation of an automatically deleted temporary dir using the
  context management protocol.
  """
  def __init__(self):
    self.tempd = tempfile.mkdtemp()
  def __enter__(self):
    return self
  def __exit__(self, exc_type, exc_value, traceback):
    shutil.rmtree(self.tempd)
  def __str__(self):
    return self.tempd

def doctest_all():
    """
    Search for python scripts in same directory, and run doctest examples
    contained within.
    """
    for f in os.listdir(script_dir):
        if op.isfile(f):
            name,ext = op.splitext(f)
            if name != 'bottle' and ext == '.py': # we exclude the third party
                                                  # bottle.py module because it
                                                  # has failed examples
                doctest.testmod(importlib.import_module(name))

def test_search(expected_nb_results, conn, query):
    """
    Executes a search on the given connection, and check the result against
    expected data.
    """
    nb_results, cur = core.search(conn, query, expected_nb_results, 0)
    assert_eq(expected_nb_results, nb_results)
    for id, loc, relev, title in cur:
        break
    else:
        assert_fail('At least one result should be available')

def testdata():
    """
    Index all the test data files, and validate the results by running a couple
    of search queries.
    """
    with TempDir() as td:
        tempd        = unicode(td)
        db_path      = op.join(tempd, 'test.db')
        testdata_dir = op.join(tempd, 'testdata')
        os.mkdir(testdata_dir)
        for f in os.listdir(script_dir):
            if fnmatch.fnmatch(f, 'testdata_*.*'):
                shutil.copyfile(op.join(script_dir, f),
                                op.join(testdata_dir, f))

        # Run indexing, and time its execution
        start_time = time.clock()
        dstat, istat_array  = core.start_indexing(db_path, [testdata_dir],
                                                  1, 'txt')
        while dstat.status != 'Idle':
            time.sleep(0.01)
        elapsed_time = time.clock() - start_time
        print 'Indexing completed in {} seconds'.format(elapsed_time)

        with closing(apsw.Connection(db_path)) as conn:
            test_search(1, conn, 'quebec montreal')
            test_search(2, conn, 'pauvre')

if __name__ == '__main__':

    # Add a console handler for loggers
    log_handler = logging.StreamHandler()
    log_handler.setFormatter(logging.Formatter('%(asctime)s [%(name)s] '
                                               '%(levelname)s: %(message)s'))
    core.log.add_handler(log_handler)

    # Run all doctest examples
    print 'Running doctest for all modules...'
    doctest_all()
    print 'Done.'

    # Index the test data files, and validate the results
    print 'Indexing and querying test data files...'
    testdata()
    print 'Done.'

