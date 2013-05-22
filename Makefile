TCC = $(USERPROFILE)\app\tcc\tcc.exe

idxlib.dll: idxlib.o charmap.o
	$(TCC) -shared -o idxlib.dll idxlib.o charmap.o

idxlib.o: idxlib.c
	$(TCC) -c idxlib.c

charmap.o: charmap.c
	$(TCC) -c charmap.c

charmap.c: charmap_gen.py
	python.exe charmap_gen.py charmap.c

