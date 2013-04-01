#include "fnv.h"

#define DLLEXP __attribute__((dllexport))

DLLEXP int fnv(char* s, unsigned* oHashLow, unsigned* oHashHigh)
{
  Fnv64_t h = fnv_64a_str(s, FNV1A_64_INIT);
  printf("hash of %s: %x %x\n", s, h.w32[0], h.w32[1]);
  *oHashLow  = h.w32[0];
  *oHashHigh = h.w32[1];
  return 0;
}

