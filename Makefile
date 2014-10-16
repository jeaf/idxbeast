CC          = gcc
CFLAGS      = -O3
CPP         = g++
CPPFLAGS    = -O3 -std=c++11
SQLITEFLAGS = -DSQLITE_THREADSAFE=0 -DSQLITE_TEMP_STORE=3

.PHONY: all
all: idxbeast.exe sqlite3shell.exe

charmap.o: charmap.c charmap.h
	$(CPP) $(CPPFLAGS) $(SQLITEFLAGS) -c $<

idxbeast.exe: charmap.o idxbeast.o sqlite3.o sqlite3wrapper.o
	$(CPP) $(CPPFLAGS) $(SQLITEFLAGS) -o $@ $+

idxbeast.o: idxbeast.cpp sqlite3.h sqlite3wrapper.h
	$(CPP) $(CPPFLAGS) $(SQLITEFLAGS) -c $<

sqlite3.o: sqlite3.c sqlite3.h
	$(CC) $(CFLAGS) $(SQLITEFLAGS) -c $<

sqlite3shell.exe: sqlite3shell.o sqlite3.o
	$(CC) $(CFLAGS) $(SQLITEFLAGS) -o $@ $+

sqlite3shell.o: sqlite3shell.c sqlite3.h
	$(CC) $(CFLAGS) $(SQLITEFLAGS) -c $<

sqlite3wrapper.o: sqlite3wrapper.cpp sqlite3wrapper.h sqlite3.h
	$(CPP) $(CPPFLAGS) $(SQLITEFLAGS) -c $<

.PHONY: clean
clean:
	rm -f *.o
	rm -f sqlite3shell.exe
	rm -f idxbeast.exe

