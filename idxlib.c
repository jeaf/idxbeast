#include "fnv.h"

#define DLLEXP __attribute__((dllexport))
#define bucket_count 16384

extern char* charmap[0x10000];

typedef struct
{
  uint64_t id;
  unsigned cnt;
  unsigned avg_idx;
  struct bucket* next_buck;
} bucket;

typedef struct
{
  bucket bucks[bucket_count];
} ht;

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
  printf("idxlib: indexing string of length %u\n", len);

  // Advance until non-blank char
  while (len && !*charmap[*utf32])
  {
    --len;
    ++utf32;
  }

  while (len)
  {
    // Process current word
    Fnv64_t h = FNV1A_64_INIT;
    while (len && *charmap[*utf32])
    {
      printf("Adding %s to current word\n", charmap[*utf32]);
      h = fnv_64a_str(charmap[*utf32], h);
      --len;
      ++utf32;
    }

    // Store info about current word
    printf("hash of current word: %x %x\n", h.w32[0], h.w32[1]);

    // Advance until non-blank char
    while (len && !*charmap[*utf32])
    {
      --len;
      ++utf32;
    }
  }

  return 0;
}

DLLEXP int test()
{
  Fnv64_t h = fnv_64a_str("abc", FNV1A_64_INIT);
  printf("hash of %s: %x %x\n", "abc", h.w32[0], h.w32[1]);
  Fnv64_t h_a = fnv_64a_str("a", FNV1A_64_INIT);
  printf("hash of %s: %x %x\n", "a  ", h_a.w32[0], h_a.w32[1]);
  h = fnv_64a_str("bc", h_a);
  printf("hash of %s: %x %x\n", "bc, with a init ", h.w32[0], h.w32[1]);
}
