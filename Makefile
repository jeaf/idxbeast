CC          = gcc
SQLITEFLAGS = -DSQLITE_THREADSAFE=0 -DSQLITE_TEMP_STORE=3
CPPFLAGS    = -Wall $(SQLITEFLAGS)
CFLAGS      =
CXXFLAGS    = -std=gnu++11

.PHONY: all
all: idxbeast.exe sandbox.exe sqlite3shell.exe

idxbeast.exe: charmap.o idxbeast.o idxlib.o sqlite3.o sqlite3wrapper.o util.o
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ $+

sandbox.exe: sandbox.o util.o
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ $+

sqlite3shell.exe: sqlite3shell.o sqlite3.o
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $+

charmap.o       : charmap.cpp charmap.h util.h
idxbeast.o      : idxbeast.cpp idxlib.h util.h
idxlib.o        : idxlib.cpp idxlib.h charmap.h sqlite3wrapper.h util.h
sandbox.o       : sandbox.cpp util.h
sqlite3.o       : sqlite3.c sqlite3.h
sqlite3shell.o  : sqlite3shell.c sqlite3.h
sqlite3wrapper.o: sqlite3wrapper.cpp sqlite3wrapper.h sqlite3.h util.h
util.o          : util.cpp util.h

.PHONY: clean
clean:
	rm -f *.o
	rm -f idxbeast.exe
	rm -f sandbox.exe
	rm -f sqlite3shell.exe

