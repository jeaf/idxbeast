import datetime
import doctest
import importlib
import os
import os.path
import time

#def assert_eq(expected, actual):
#    assert expected == actual, 'expected: {}, actual: {}'.format(expected, actual)
#
#def complete_test():
#    start_time = time.clock()
#
#    for i in range(10):
#        results = idxbeast.search('shared_ptr de boost alpha')
#        assert_eq(2, len(results))
#
#        results = idxbeast.search('for')
#        assert_eq(11892, len(results))
#
#        results = idxbeast.search('lambda american')
#        assert_eq(2, len(results))
#
#    elapsed_time = time.clock() - start_time
#    print 'All tests passed in {}.'.format(datetime.timedelta(seconds=elapsed_time))

if __name__ == '__main__':
    print 'Running doctest for all modules...'
    for f in os.listdir(os.path.dirname(os.path.abspath(__file__))):
        if os.path.isfile(f):
            name,ext = os.path.splitext(f)
            if name != 'bottle' and ext == '.py': # we exclude the third party
                                                  # bottle.py module because it
                                                  # has failed examples
                doctest.testmod(importlib.import_module(name))
    print 'Done.'
