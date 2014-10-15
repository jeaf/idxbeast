CC          = gcc
CFLAGS      = -O3
CPP         = g++
CPPFLAGS    = -O3 -std=c++11
SQLITEFLAGS = -DSQLITE_THREADSAFE=0 -DSQLITE_TEMP_STORE=3

idxbeast.exe: idxbeast.o sqlite3.o
	$(CPP) $(CPPFLAGS) $(SQLITEFLAGS) -o $@ $+

idxbeast.o: idxbeast.cpp sqlite3.h
	$(CPP) $(CPPFLAGS) $(SQLITEFLAGS) -c $<

sqlite3_shell.exe: sqlite3_shell.c sqlite3.o
	$(CC) $(CFLAGS) $(SQLITEFLAGS) -o $@ $+

sqlite3.o: sqlite3.c sqlite3.h
	$(CC) $(CFLAGS) $(SQLITEFLAGS) -c $<

clean:
	rm -f *.o
	rm -f sqlite3_shell.exe

