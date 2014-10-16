CC          = gcc
SQLITEFLAGS = -DSQLITE_THREADSAFE=0 -DSQLITE_TEMP_STORE=3
CPPFLAGS    = -Wall -Werror $(SQLITEFLAGS)
CFLAGS      =
CXXFLAGS    = -std=c++11

.PHONY: all
all: idxbeast.exe sqlite3shell.exe

idxbeast.exe: charmap.o idxbeast.o sqlite3.o sqlite3wrapper.o
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ $+

sqlite3shell.exe: sqlite3shell.o sqlite3.o
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $+

charmap.o       : charmap.c charmap.h
idxbeast.o      : idxbeast.cpp charmap.h sqlite3wrapper.h
sqlite3.o       : sqlite3.c sqlite3.h
sqlite3shell.o  : sqlite3shell.c sqlite3.h
sqlite3wrapper.o: sqlite3wrapper.cpp sqlite3wrapper.h sqlite3.h

.PHONY: clean
clean:
	rm -f *.o
	rm -f sqlite3shell.exe
	rm -f idxbeast.exe

