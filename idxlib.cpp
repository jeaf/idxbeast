#include <chrono>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <mutex>
#include <queue>
#include <sstream>
#include <string>
#include <thread>
#include <unistd.h>
#include <unordered_map>
#include <vector>
#include <windows.h>

#include "charmap.h"
#include "idxlib.h"
#include "sqlite3wrapper.h"
#include "util.h"

using namespace std;

const int64_t DOCTYPE_PATH = 10;
const int64_t DOCTYPE_FILE = 20;

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
unordered_map<string, unordered_map<int64_t, WordCounts>> words;

void create_tables()
{
    // The base class for all documents. A document is something that can be
    // found using the index
    conn->table("doc", "id INTEGER PRIMARY KEY, type_ INTEGER NOT NULL, create_time INTEGER NOT NULL DEFAULT (strftime('%s', 'now')), update_time INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))");

    // The classes derived from doc
    conn->table("doc_path", "id INTEGER PRIMARY KEY, path INTEGER NOT NULL UNIQUE");
    conn->table("doc_file", "id INTEGER PRIMARY KEY, path INTEGER NOT NULL UNIQUE");

    // Each indexed word appears only once in the DB in that table
    conn->table("word", "id INTEGER PRIMARY KEY, word UNIQUE");

    // This table joins word and doc
    conn->table("match", "word_id INTEGER, doc_id INTEGER, count INTEGER NOT NULL, avgidx INTEGER NOT NULL, PRIMARY KEY(word_id, doc_id)", "WITHOUT ROWID");

    // The path table's purpose is to store the paths as separate components,
    // hopefully to reduce storage (todo: is this useful?). It also stores a
    // default root with an id of 1.
    conn->table("path", "id INTEGER PRIMARY KEY, name TEXT NOT NULL, parent INTEGER, UNIQUE(name, parent)");
    conn->exec("INSERT OR IGNORE INTO path(id, name) VALUES(1, 'root')");
}

int64_t lookup_word(string word)
{
    sqlite::Statement<int64_t> stmt(conn->db, fmt("SELECT id FROM word WHERE word='%s';", word));
    if (stmt.step()) return stmt.col0();
    return conn->insert("word(word)", fmt("'%s'", word));
}

void dump_index()
{
    cout << "Dumping index..." << endl;
    sqlite::Transaction transaction(conn);
    for (auto word_it = words.begin(); word_it != words.end(); ++word_it)
    {
        string word     = word_it->first;
        int64_t word_id = lookup_word(word);
        for (auto it2 = word_it->second.begin(); it2 != word_it->second.end(); ++it2)
        {
            int64_t docid = it2->first;
            WordCounts wc = it2->second;
            conn->insert("match(word_id, doc_id, count, avgidx)", fmt("%s, %s, %s, %s", word_id, docid, wc.count, wc.totpos / wc.count), false);
        }
    }
    cout << "Done." << endl;
}

string build_path(int64_t doc_path_id)
{
    // Find the path object
    sqlite::Statement<int64_t> stmt_path(conn->db, fmt("SELECT path FROM doc_path WHERE id=%s", doc_path_id));
    if (!stmt_path.step()) REQUIRE(false, "doc_path id not found: " << doc_path_id);
    int64_t path_id = stmt_path.col0();

    // Build the path
    string path;
    sqlite::Statement<string, int64_t> stmt_name_parent(conn->db, fmt("SELECT name, parent FROM path WHERE id=%s;", path_id));
    if (stmt_name_parent.step())
    {
        string name = stmt_name_parent.col0();
        int64_t parent = stmt_name_parent.col1();
        while (parent > 0)
        {
            path = string("/") + name + path;
            stmt_name_parent.reset(conn->db, fmt("SELECT name, parent FROM path WHERE id=%s;", parent));
            bool res = stmt_name_parent.step();
            REQUIRE(res, "Could not find parent: " << parent);
            name = stmt_name_parent.col0();
            parent = stmt_name_parent.col1();
        }
        return path;
    }
    else
    {
        return "<path not found>";
    }
}

void search(string word)
{
    int64_t word_id = lookup_word(word);
    sqlite::Statement<int64_t> stmt(conn->db, fmt("SELECT doc_id FROM match WHERE word_id=%s", word_id));
    while (stmt.step())
    {
        int64_t docid = stmt.col0();

        // Get path
        sqlite::Statement<int64_t> stmt2(conn->db, fmt("SELECT path FROM doc_path WHERE id=%s", docid));
        if (stmt2.step())
        {
            cout << "Path: " << build_path(docid) << endl;
        }

        // Get file
        stmt2.reset(conn->db, fmt("SELECT path FROM doc_file WHERE id=%s", docid));
        if (stmt2.step())
        {
            cout << "File: " << build_path(stmt2.col0()) << endl;
        }
    }
}

int64_t lookup_doc_path(string path)
{
    int64_t parent = 1; // 1 is the root
    for (auto tok: tokenize(path, '/'))
    {
        sqlite::Statement<int64_t> stmt(conn->db, fmt("SELECT id FROM path WHERE name='%s' AND parent=%s;", tok, parent));
        if (stmt.step()) parent = stmt.col0();
        else
        {
            parent = conn->insert("path(name, parent)", fmt("'%s', %s", tok, parent));
        }
    }

    // Find or create corresponding doc_path
    sqlite::Statement<int64_t> stmt(conn->db, fmt("SELECT id FROM doc_path WHERE path=%s", parent));
    if (stmt.step()) return stmt.col0();
    int64_t newdoc = conn->insert("doc(type_)", fmt("%s", DOCTYPE_PATH));
    return conn->insert("doc_path(id, path)", fmt("%s, %s", newdoc, parent));
}

int64_t lookup_doc_file(int64_t path_id)
{
    string s = fmt("SELECT id FROM doc_file WHERE path=%s", path_id);
    sqlite::Statement<int64_t> stmt(conn->db, s);
    if (stmt.step()) return stmt.col0();
    int64_t newdoc = conn->insert("doc(type_)", fmt("%s", DOCTYPE_FILE));
    return conn->insert("doc_file(id, path)", fmt("%s, %s", newdoc, path_id));
}

template <typename Iterator>
void index_blocks(int64_t docid, Iterator blocks_it, Iterator blocks_it_end)
{
    string cur_word;
    int    cur_word_pos = 0;
    for (; blocks_it != blocks_it_end; ++blocks_it)
    {
        auto char_it     = blocks_it->cbegin();
        auto char_it_end = blocks_it->cend();

        while (char_it != char_it_end)
        {
            // Process current word
            while (char_it != char_it_end &&
                   *charmap[static_cast<uint8_t>(*char_it)])
            {
                cur_word += charmap[static_cast<uint8_t>(*char_it)];
                ++char_it;
            }

            // Store current word
            if (char_it != char_it_end && !cur_word.empty())
            {
                if (cur_word.size() > 1)
                {
                    words[cur_word][docid].count++;
                    words[cur_word][docid].totpos += cur_word_pos;
                }
                ++cur_word_pos;
                cur_word.clear();
            }

            // Advance until non-blank char
            while (char_it != char_it_end &&
                   !*charmap[static_cast<uint8_t>(*char_it)]) ++char_it;
        }
    }

    // After reading all the blocks, store the last word
    if (cur_word.size() > 1)
    {
        words[cur_word][docid].count++;
        words[cur_word][docid].totpos += cur_word_pos;
    }
}

void index_file(string path)
{
    REQUIRE(!isdir(path), "path is dir: " << path);
    REQUIRE(isfile(path), "path is not file: " << path);

    // Check if file is binary
    string file_enc(runcmd(fmt("/usr/bin/file --brief --mime-encoding \"%s\" 2>&1", path)));
    if (file_enc.find("binary") != string::npos) return;

    cout << path << endl;

    // Index the doc_path
    int64_t doc_path_id = lookup_doc_path(path);
    index_blocks(doc_path_id, &path, &path + 1);

    // Index the doc_file
    int64_t docid = lookup_doc_file(doc_path_id);
    ifstream in(path, ios::binary);
    FileIterator fi_begin(&in, 16384);
    FileIterator fi_end(nullptr, 0);
    index_blocks(docid, fi_begin, fi_end);

    // Delete existing matches
    conn->exec(fmt("DELETE FROM match WHERE doc_id = %s", doc_path_id));
    conn->exec(fmt("DELETE FROM match WHERE doc_id = %s", docid));
}

