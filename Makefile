CC          = gcc
SQLITEFLAGS = -DSQLITE_THREADSAFE=0 -DSQLITE_TEMP_STORE=3
CPPFLAGS    = -Wall $(SQLITEFLAGS)
CFLAGS      =
CXXFLAGS    = -std=gnu++11

.PHONY: all
all: idxb.exe sandbox.exe sqlite3shell.exe test.exe

idxb.exe: charmap.o core.o cui.o db.o sqlite3.o util.o
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ $+

sandbox.exe: sandbox.o util.o
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ $+

sqlite3shell.exe: sqlite3shell.o sqlite3.o
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $+

test.exe: test.o
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ $+

charmap.o      : charmap.cpp charmap.h
core.o         : core.cpp core.h charmap.h db.h util.h
cui.o          : cui.cpp core.h util.h
db.o           : db.cpp db.h sqlite3.h util.h
sandbox.o      : sandbox.cpp util.h
sqlite3.o      : sqlite3.c sqlite3.h
sqlite3shell.o : sqlite3shell.c sqlite3.h
test.o         : test.cpp core.h
util.o         : util.cpp util.h

.PHONY: clean
clean:
	rm -f *.o
	rm -f idxb.exe
	rm -f sandbox.exe
	rm -f sqlite3shell.exe
	rm -f test.exe

