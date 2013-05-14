import datetime
import idxbeast
import time

def assert_eq(expected, actual):
    assert expected == actual, 'expected: {}, actual: {}'.format(expected, actual)

start_time = time.clock()

for i in range(10):
    results = idxbeast.search('shared_ptr de boost alpha')
    assert_eq(2, len(results))

    results = idxbeast.search('for')
    assert_eq(11892, len(results))

    results = idxbeast.search('lambda american')
    assert_eq(2, len(results))

elapsed_time = time.clock() - start_time
print 'All tests passed in {}.'.format(datetime.timedelta(seconds=elapsed_time))

