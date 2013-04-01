import os.path

c = os.path.expanduser(r'~\app\tcc\tcc.exe hash_64a.c -run test_fnv.c')
print c
os.system(c)
