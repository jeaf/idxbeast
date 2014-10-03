import ctypes
import os
import os.path as osp
import sys

supported_exts = '''bat c cpp cs cxx h hpp htm html ini java js log md py rest
                    rst txt vim xml yaml yml'''
supported_exts = set('.' + e for e in supported_exts.split())

lib = ctypes.cdll.idxbeast

def parse(rootdir):
    assert osp.isdir(rootdir)
    for dirpath, dirnames, filenames in os.walk(rootdir):
        for name in filenames:
            path = os.path.join(dirpath, name)
            root, ext = os.path.splitext(path)
            if ext in supported_exts:
                with open(path) as f: s = f.read()
                print(path)

if __name__ == '__main__':
    print(lib.test())
    #parse(sys.argv[1])

