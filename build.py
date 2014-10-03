import os
c = 'i686-pc-mingw32-g++ -shared -static -o idxbeast.dll idxbeast.cpp'
print(c)
os.system(c)

