#include "fnv.h"

int main()
{
  char* t = "abc";
  Fnv64_t h = fnv_64a_str(t, FNV1A_64_INIT);
  printf("hash of %s: %x %x", t, h.w32[0], h.w32[1]);
  return 0;
}

