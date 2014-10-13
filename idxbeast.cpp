#define DLLEXP extern "C" __attribute__((dllexport))

#include "charmap.c"

#include <array>
#include <cstdint>
#include <iostream>
#include <queue>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

using namespace std;

// This macro implements a sort of assert that will also be enabled in release
#define REQUIRE(cond, msg) if (!(cond)) {\
    ostringstream oss; \
    oss << msg << " @ " << __FUNCTION__ << "(" << __LINE__ << ")"; \
    throw runtime_error(oss.str());}

// Various typedefs to make things clearer
typedef int64_t docid_t;

// The counts that describe how a specific word matches a document
struct WordCounts
{
    // How many times does the word appear in the doc?
    int64_t count;  

    // The sum of the "positions" of a word in a doc. e.g., for the following
    // text: "gamma abc def ghi abc", abc would have a totpos of 5, since if
    // appears at position 1 and at position 4. This value will be used to
    // compute the average pos, which is used for computing the relevance of
    // matches.
    int64_t totpos;
};

// The main index, stores the docid and counts for each word
unordered_map<string, unordered_map<docid_t, WordCounts>> words;

// The state of indexing for a specific document
struct IndexingState
{
    string cur_word;
};
unordered_map<docid_t, IndexingState> idx_state;

// The blocks queue
queue<pair<docid_t, array<uint32_t, 64>>> block_queue;

// Parses a single doc (todo: will be changed to sending blocks of raw text
// into a queue, and a thread that processes the queue of blocks)
DLLEXP int parse_doc(docid_t docid, const uint8_t* text, int64_t len)
{
    REQUIRE(docid   > 0, "docid must be larger than 0"      )
    REQUIRE(text       , "text cannot be NULL"              )
    REQUIRE(len     > 0, "text length must be larger than 0")

    const uint32_t* utf32 = reinterpret_cast<const uint32_t*>(text);
    len = len / 4;

    // Advance until non-blank char
    while (len && !*charmap[*utf32])
    {
        --len;
        ++utf32;
    }

    while (len)
    {
        string cur_word;

        // Process current word
        while (len && *charmap[*utf32])
        {
            cur_word += charmap[*utf32];
            --len;
            ++utf32;
            REQUIRE(!len || *utf32 < sizeof(charmap), "Invalid charmap index");
        }

        // Store current word
        if (cur_word.size() > 1)
        {
            words[cur_word][docid].count++;
        }

        // Advance until non-blank char
        while (len && !*charmap[*utf32])
        {
            --len;
            ++utf32;
        }
    }

    return 1;
}

DLLEXP int get_results()
{
    // Debug output
    for (auto it = words.begin(); it != words.end(); ++it)
    {
        int64_t sum = 0;
        for (auto it2 = it->second.begin(); it2 != it->second.end(); ++it2)
        {
            sum += it2->second.count;
        }
        cout << it->first << ": " << sum << endl;
    }

    return 1;
}

