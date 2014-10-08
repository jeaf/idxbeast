import os
c = 'i686-pc-mingw32-g++ -Wall -Werror -O3 -std=c++11 -shared -static -o idxbeast.dll idxbeast.cpp'
print(c)
os.system(c)

