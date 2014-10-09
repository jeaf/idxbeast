#define DLLEXP extern "C" __attribute__((dllexport))

#include "charmap.c"

#include <cstdint>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

using namespace std;

#define REQUIRE(cond, msg) if (!(cond)) {\
    ostringstream oss; \
    oss << msg << " @ " << __FUNCTION__ << "(" << __LINE__ << ")"; \
    throw runtime_error(oss.str());}

DLLEXP int parse_doc(int64_t docid, const uint8_t* text, int64_t len)
{
    REQUIRE(docid   > 0, "docid must be larger than 0"      )
    REQUIRE(text       , "text cannot be NULL"              )
    REQUIRE(len     > 0, "text length must be larger than 0")

    unordered_map<string, int64_t> words;

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
        words[cur_word]++;

        // Advance until non-blank char
        while (len && !*charmap[*utf32])
        {
            --len;
            ++utf32;
        }
    }

    // Debug output
    for (auto it = words.begin(); it != words.end(); ++it)
    {
        cout << it->first << ", " << it->second << endl;
    }

    return 0;
}

