import os
import os.path as osp
import sys

def exec_cmd(c):
    print(c)
    os.system(c)

if sys.platform == 'win32': tcc = osp.expanduser(r'~\app\tcc32\tcc.exe')
assert osp.isfile(tcc), 'C compiler not found: {}'.format(tcc)

exec_cmd('{} -c {}'.format(tcc, 'charmap.c'))
exec_cmd('{} -c {}'.format(tcc, 'idxlib.c'))
exec_cmd('{} -shared -o idxlib.dll idxlib.o charmap.o'.format(tcc))


