#include <chrono>
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <mutex>
#include <queue>
#include <string>
#include <thread>
#include <unistd.h>
#include <unordered_map>
#include <vector>
#include <windows.h>

#include "charmap.h"
#include "sqlite3wrapper.h"
#include "util.h"

using namespace std;

typedef int64_t docid_t;
typedef uint8_t byte;

auto conn = make_shared<sqlite::Connection>("idxbeast.db");

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

//struct Block
//{
//    Block() {}
//    Block(docid_t did, const byte* byte_ptr, int64_t len) : docid(did)
//    {
//        REQUIRE(docid > 0   , "docid must be larger than 0: " << docid)
//        REQUIRE(byte_ptr    , "byte_ptr cannot be NULL")
//        REQUIRE(len > 0     , "len must be > 0: " << len)
//        REQUIRE(len % 4 == 0, "len must be a multiple of 4: " << len);
//
//        //auto uint_ptr = reinterpret_cast<const uint32_t*>(byte_ptr);
//        //data.assign(uint_ptr, uint_ptr + len / 4);
//    }
//    docid_t docid;
//    vector<uint32_t> data;
//};

// The blocks queue
//queue<Block> block_queue;
//thread block_queue_thread;
//mutex queue_mutex;

// This function will run in a thread that constantly process blocks that are
// being pushed on the queue
//int process_queue()
//{
//    // Try to get a block from the queue
//    Block blk;
//    {
//        lock_guard<mutex> lock(queue_mutex);
//        if (!block_queue.empty())
//        {
//            blk = block_queue.front();
//            block_queue.pop();
//        }
//    }
//
//    // If the queue was empty, sleep a little
//    if (blk.docid == 0)
//    {
//        //cout << "Queue empty, sleep one second" << endl;
//        this_thread::sleep_for(chrono::seconds(1));
//    }
//
//    // Get the data from the blk
//    const uint32_t* utf32 = blk.data.data();
//    auto len = blk.data.size();
//    auto docid = blk.docid;
//
//    // Advance until non-blank char
//    while (len && !*charmap[*utf32])
//    {
//        --len;
//        ++utf32;
//    }
//
//    while (len)
//    {
//        // Process current word
//        while (len && *charmap[*utf32])
//        {
//            idx_state[docid].cur_word += charmap[*utf32];
//            --len;
//            ++utf32;
//            REQUIRE(!len || *utf32 < sizeof(charmap), "Invalid charmap index");
//        }
//
//        // Store current word
//        if (idx_state[docid].cur_word.size() > 1)
//        {
//            words[idx_state[docid].cur_word][docid].count++;
//        }
//
//        // Advance until non-blank char
//        while (len && !*charmap[*utf32])
//        {
//            --len;
//            ++utf32;
//        }
//    }
//
//    return 1;
//}

// Push a block in the queue
//int push_block(docid_t docid, const byte* data, int64_t len)
//{
//    {
//        //lock_guard<mutex> lock(queue_mutex);
//        //cout << "Pushing block" << endl;
//        block_queue.emplace(docid, data, len);
//    }
//    //if (!block_queue_thread.joinable())
//    //{
//    //    block_queue_thread = thread(process_queue);
//    //}
//    return 1;
//}

void create_tables()
{
    conn->table("doc", "id INTEGER PRIMARY KEY, create_time INTEGER NOT NULL, update_time INTEGER NOT NULL");
    conn->table("path", "id INTEGER PRIMARY KEY, name TEXT NOT NULL, parent INTEGER, UNIQUE(name, parent)");
    conn->table("file", "id INTEGER PRIMARY KEY, path INTEGER NOT NULL UNIQUE");
    conn->table("word", "id INTEGER PRIMARY KEY, word UNIQUE");
    conn->table("match", "word_id INTEGER, doc_id INTEGER, relev INTEGER NOT NULL, PRIMARY KEY(word_id, doc_id)", "WITHOUT ROWID");

    conn->exec("INSERT OR IGNORE INTO path(id, name) VALUES(1, 'root')");
}

void dump_index()
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
}

void index_file(string path)
{
    int docid = 1; // dummy, todo: replace
    ifstream in(path, ios::binary);
    vector<char> block(2, 0);
    string cur_word;
    while (in)
    {
        in.read(block.data(), block.size());
        auto it = block.cbegin();
        const vector<char>::const_iterator end = it + in.gcount();
        while (it != end)
        {
            // Process current word
            while (it != end && *charmap[static_cast<uint8_t>(*it)])
            {
                cur_word += charmap[static_cast<uint8_t>(*it)];
                ++it;
            }

            // Store current word
            if ((it != end || !in) && !cur_word.empty())
            {
                if (cur_word.size() > 1) words[cur_word][docid].count++;
                cur_word.clear();
            }

            // Advance until non-blank char
            while (it != end && !*charmap[static_cast<uint8_t>(*it)]) ++it;
        }
    }
}

vector<string> tokenize(string s, char delim)
{
    vector<string> tokens;
    string cur_tok;
    for (char c: s)
    {
        if (c != delim) cur_tok += c;
        else if (!cur_tok.empty())
        {
            tokens.push_back(cur_tok);
            cur_tok.clear();
        }
    }
    if (!cur_tok.empty()) tokens.push_back(cur_tok);
    return tokens;
}

int64_t lookup_path(string path)
{
    auto toks = tokenize(path, '/');

    int64_t cur_parent = 1; // 1 is the root
    for (auto tok: toks)
    {
        ostringstream oss;
        oss << "SELECT id FROM path WHERE name='" << tok;
        oss << "' AND parent=" << cur_parent << ";";
        auto stmt = conn->prepare(oss.str());
        if (stmt->step())
        {
            cur_parent = stmt->col_int64(0);
        }
        else
        {
            ostringstream oss2;
            oss2 << "INSERT INTO path(name, parent) VALUES('" << tok;
            oss2 << "', " << cur_parent << ");";
            conn->exec(oss2.str());
            cur_parent = conn->lastrowid();
        }
    }
    return cur_parent;
}

string abspath(string path)
{
    char buf[5000];
    GetFullPathName(path.c_str(), sizeof(buf), buf, nullptr);
    string s;
    s += tolower(buf[0]);
    s += buf + 2;
    string new_s("/cygdrive");
    auto toks = tokenize(s, '\\');
    for (auto tok: toks)
    {
        new_s += "/";
        new_s += tok;
    }
    return new_s;
}

int main(int argc, char* argv[])
{
    try
    {
        if (argc <= 1)
        {
            cout << "Missing argument." << endl;
            cout << "Usage: idxbeast.exe [root_dir | file]" << endl;
            return 1;
        }
        string path = abspath(argv[1]);
        cout << "Path: " << path << endl;
        REQUIRE(!isdir(path), "Directory not implemented yet, only single file supported, argument invalid: " << path)
        REQUIRE(isfile(path), "File not found: " << path)
        create_tables();
        cout << "lookup_path for " << path << ": " << lookup_path(path) << endl;
        //index_file(path);
        //dump_index();
        return 0;
    }
    catch (const std::exception& ex)
    {
        cout << "Exception:" << endl;
        cout << ex.what() << endl;
    }
}

