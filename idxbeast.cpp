#include "charmap.c"

#include <chrono>
#include <cstdint>
#include <iostream>
#include <mutex>
#include <queue>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

using namespace std;

// This macro implements a sort of assert that will also be enabled in release
#define REQUIRE(cond, msg) if (!(cond)) {\
    ostringstream oss; \
    oss << msg << " @ " << __FUNCTION__ << "(" << __LINE__ << ")"; \
    throw runtime_error(oss.str());}

// Various typedefs to make things clearer
typedef int64_t docid_t;
typedef uint8_t byte;

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

// A block
struct Block
{
    Block() {}
    Block(docid_t did, const byte* byte_ptr, int64_t len) : docid(did)
    {
        REQUIRE(docid > 0, "docid must be larger than 0: " << docid)
        REQUIRE(byte_ptr , "byte_ptr cannot be NULL")
        REQUIRE(len > 0  , "len must be > 0: " << len)
        REQUIRE(len % 4 == 0, "len must be a multiple of 4: " << len);

        //auto uint_ptr = reinterpret_cast<const uint32_t*>(byte_ptr);
        //data.assign(uint_ptr, uint_ptr + len / 4);
    }
    docid_t docid;
    vector<uint32_t> data;
};

// The blocks queue
queue<Block> block_queue;
thread block_queue_thread;
mutex queue_mutex;

// This function will run in a thread that constantly process blocks that are
// being pushed on the queue
int process_queue()
{
    // Try to get a block from the queue
    Block blk;
    {
        lock_guard<mutex> lock(queue_mutex);
        if (!block_queue.empty())
        {
            blk = block_queue.front();
            block_queue.pop();
        }
    }

    // If the queue was empty, sleep a little
    if (blk.docid == 0)
    {
        //cout << "Queue empty, sleep one second" << endl;
        this_thread::sleep_for(chrono::seconds(1));
    }

    // Get the data from the blk
    const uint32_t* utf32 = blk.data.data();
    auto len = blk.data.size();
    auto docid = blk.docid;

    // Advance until non-blank char
    while (len && !*charmap[*utf32])
    {
        --len;
        ++utf32;
    }

    while (len)
    {
        // Process current word
        while (len && *charmap[*utf32])
        {
            idx_state[docid].cur_word += charmap[*utf32];
            --len;
            ++utf32;
            REQUIRE(!len || *utf32 < sizeof(charmap), "Invalid charmap index");
        }

        // Store current word
        if (idx_state[docid].cur_word.size() > 1)
        {
            words[idx_state[docid].cur_word][docid].count++;
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

// Push a block in the queue
int push_block(docid_t docid, const byte* data, int64_t len)
{
    {
        //lock_guard<mutex> lock(queue_mutex);
        //cout << "Pushing block" << endl;
        block_queue.emplace(docid, data, len);
    }
    //if (!block_queue_thread.joinable())
    //{
    //    block_queue_thread = thread(process_queue);
    //}
    return 1;
}

int get_results()
{
    // Debug output
    for (auto it = words.begin(); it != words.end(); ++it)
    {
        int64_t sum = 0;
        for (auto it2 = it->second.begin(); it2 != it->second.end(); ++it2)
        {
            sum += it2->second.count;
        }
        //cout << it->first << ": " << sum << endl;
    }

    return 1;
}

int main(int argc, char* argv[])
{
    cout << "idxbeast" << endl;
    return 0;
}

