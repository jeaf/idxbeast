import datetime
import idxbeast
import time

def assert_eq(expected, actual):
  assert expected == actual, 'expected: {}, actual: {}'.format(expected, actual)

start_time = time.clock()

for i in range(10):
  results = idxbeast.search('shared_ptr i e a de boost alpha')
  assert_eq(len(results), 1)

  results = idxbeast.search('for')
  assert_eq(len(results), 11892)

  results = idxbeast.search('lambda american')
  assert_eq(len(results), 2)

elapsed_time = time.clock() - start_time
print 'All tests passed in {}.'.format(datetime.timedelta(seconds=elapsed_time))

