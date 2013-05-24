#define DLLEXP __attribute__((dllexport))
#define hash_bits     18
#define bucket_count  (1 << hash_bits)
#define hash_mask     (bucket_count - 1)
#define FNV1A_64_INIT 14695981039346656037ULL
#define FNV_64_PRIME  1099511628211ULL
#define TWO_63        9223372036854775808LL

typedef unsigned long long uint64;

extern char* charmap[0x10000];

typedef struct
{
    unsigned valid;
    uint64   id;
    unsigned cnt;
    unsigned tot_idx;
} bucket;

typedef struct
{
    bucket buckets[bucket_count];
    unsigned size;
} htable;

htable ht;

void ht_init(htable* table)
{
    memset(table->buckets, 0, bucket_count * sizeof(bucket));
    table->size = 0;
}

bucket* ht_lookup(htable* table, uint64 key)
{
    unsigned hash_index = key & hash_mask;
    unsigned offset     = 0;

    while (offset < bucket_count)
    {
        bucket* b = &table->buckets[(hash_index + offset++) % bucket_count];

        // Slot is free, assign and return it
        if (!b->valid)
        {
            b->valid = 1;
            b->id = key;
            table->size++;
            return b;
        }

        // Slot is the right one, return it
        if (b->id == key)
        {
            return b;
        }
    }

    // The hashtable is full!
    return 0;
}

// Algorithm and constants taken from
// http://www.isthe.com/chongo/tech/comp/fnv/
uint64 fnv_internal(char* s, uint64 hash)
{
    while (*s)
    {
        hash ^= (unsigned char)*s++;
        hash *= FNV_64_PRIME;
    }
    return hash;
}

DLLEXP uint64 fnv(char* s)
{
    //return fnv_internal(s, FNV1A_64_INIT) - TWO_63;
    return fnv_internal(s, FNV1A_64_INIT);
}

DLLEXP unsigned index(unsigned docid, unsigned* utf32, unsigned len)
{
    //printf("idxlib: indexing string of length %u\n", len);

    ht_init(&ht);

    // Advance until non-blank char
    while (len && !*charmap[*utf32])
    {
        --len;
        ++utf32;
    }

    unsigned cur_idx = 0;

    while (len)
    {
        // Process current word
        uint64 key = FNV1A_64_INIT;
        while (len && *charmap[*utf32])
        {
            //printf("Adding %s to current word\n", charmap[*utf32]);
            key = fnv_internal(charmap[*utf32], key);
            --len;
            ++utf32;
        }

        // Store info about current word
        //printf("key: %llx\n", key);
        bucket* b = ht_lookup(&ht, key);
        if (!b)
        {
            // Hashtable is full, maximum number of unique words reached
            break;
        }
        b->cnt     += 1;
        b->tot_idx += cur_idx;
        cur_idx    += 1;

        // Advance until non-blank char
        while (len && !*charmap[*utf32])
        {
            --len;
            ++utf32;
        }
    }

    return cur_idx;
}

unsigned current_bucket = 0;
DLLEXP int index_iterator_init()
{
    current_bucket = 0;
    return 1;
}

DLLEXP int index_iterator_next(uint64* oHash, unsigned* oCnt, unsigned* oAvgIdx)
{
    while (!ht.buckets[current_bucket].valid && current_bucket < bucket_count)
    {
        ++current_bucket;
    }

    if (current_bucket >= bucket_count)
    {
        // We reached the end of the hashtable, return 0
        return 0;
    }

    *oHash   = ht.buckets[current_bucket].id;
    *oCnt    = ht.buckets[current_bucket].cnt;
    *oAvgIdx = ht.buckets[current_bucket].tot_idx / *oCnt;
    ++current_bucket;
    return 1;
}

DLLEXP int test()
{
    //Fnv64_t h = fnv_64a_str("abc", FNV1A_64_INIT);
    //printf("hash of %s: %x %x\n", "abc", h.w32[0], h.w32[1]);
    //Fnv64_t h_a = fnv_64a_str("a", FNV1A_64_INIT);
    //printf("hash of %s: %x %x\n", "a  ", h_a.w32[0], h_a.w32[1]);
    //h = fnv_64a_str("bc", h_a);
    //printf("hash of %s: %x %x\n", "bc, with a init ", h.w32[0], h.w32[1]);
}
