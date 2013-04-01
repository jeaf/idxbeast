#include "charmap.c"
#include "fnv.h"

#define DLLEXP __attribute__((dllexport))

extern char charmap[0x10ffff];

DLLEXP int fnv(char* s, unsigned* oHashLow, unsigned* oHashHigh)
{
  Fnv64_t h = fnv_64a_str(s, FNV1A_64_INIT);
  printf("hash of %s: %x %x\n", s, h.w32[0], h.w32[1]);
  *oHashLow  = h.w32[0];
  *oHashHigh = h.w32[1];
  return 0;
}

DLLEXP int index(unsigned* utf32, unsigned len)
{
  for (unsigned i = 0; i < len; ++i)
  {
    printf("%d,", utf32[i]);
    printf("%c,", charmap[utf32[i]]);
  }
  printf("\n");
  return 0;
}

