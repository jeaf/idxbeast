import os.path

def build():
  c = os.path.expanduser(r'~\app\tcc\tcc.exe -shared -o idxlib.dll hash_64a.c idxlib.c')
  print c
  os.system(c)

if __name__ == '__main__':
  build()

