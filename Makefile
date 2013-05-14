TCC = $(USERPROFILE)\app\tcc\tcc.exe

idxlib.dll: idxlib.o charmap.o hash_64a.o
	$(TCC) -shared -o idxlib.dll idxlib.o charmap.o hash_64a.o

idxlib.o: idxlib.c fnv.h
	$(TCC) -c idxlib.c

charmap.o: charmap.c
	$(TCC) -c charmap.c

charmap.c: charmap_gen.py
	python.exe charmap_gen.py charmap.c

hash_64a.o: hash_64a.c fnv.h
	$(TCC) -c hash_64a.c
