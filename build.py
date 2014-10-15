import os
import os.path as osp
import shutil

# The compilers to use
c_compiler = 'gcc'
#c_compiler = 'i686-pc-mingw32-g++'
#c_compiler = 'clang++'
cpp_compiler = 'g++'

# The list of files and executables to compile
files_to_compile = 'sqlite3.c'.split()
executables      = 'shell.c'.split()
#options          = '-Wall -Werror -O3'
options          = ''

# Bring the cygwin dependencies
for f in 'cygwin1.dll cyggcc_s-1.dll cygstdc++-6.dll'.split():
    if not osp.isfile(f):
        shutil.copy(r'C:\cygwin\bin\{}'.format(f), r'.\{}'.format(f))

# Compile the files
for f in files_to_compile:
    base, ext = osp.splitext(f)
    if ext == '.c':
        c = '{} {} -c {}'.format(c_compiler, options, f)
    elif ext == '.cpp':
        c = '{} -std=c++11 {} -c {}'.format(cpp_compiler, options, f)
    else: assert False
    print(c)
    os.system(c)

# Produce the executables
for e in executables:
    base, ext = osp.splitext(e)
    if ext == '.c':
        c = '{} {} -o {}.exe {}'.format(c_compiler, options, base, e)
    else: assert False
    print(c)
    os.system(c)

