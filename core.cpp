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
#include <vector>
#include <windows.h>

#include "core.h"
#include "util.h"

using namespace std;
using namespace idxb::db;

const int64_t DOCTYPE_PATH = 10;
const int64_t DOCTYPE_FILE = 20;

namespace
{
    // Tags used to identify columns
    struct id; struct docid; struct path_id; struct name; struct parent;

    // Useful typedefs for statements
    typedef Statement<ColSpec<ColDef<id   , int64_t>>> Statement_id;
    typedef Statement<ColSpec<ColDef<docid, int64_t>>> Statement_docid;
}

namespace idxb { namespace core
{
    Index::Index(shared_ptr<Connection> i_conn) : conn(i_conn)
    {
        create_tables();
    }

    void Index::commit()
    {
        cout << "Dumping index..." << endl;
        Transaction transaction(conn);
        for (auto word_it = words.begin(); word_it != words.end(); ++word_it)
        {
            string word     = word_it->first;
            int64_t word_id = lookup_word(word);
            for (auto it2 = word_it->second.begin(); it2 != word_it->second.end(); ++it2)
            {
                int64_t docid = it2->first;
                WordCounts wc = it2->second;
                conn->insert("match(word_id, doc_id, count, avgidx)", util::fmt("%s, %s, %s, %s", word_id, docid, wc.count, wc.totpos / wc.count), false);
            }
        }
        transaction.commit();
        cout << "Done." << endl;
    }

    void Index::index_file(string path)
    {
        REQUIRE(!util::isdir(path), "path is dir: " << path);
        REQUIRE(util::isfile(path), "path is not file: " << path);

        // Check if file is binary
        string file_enc(util::runcmd(util::fmt("/usr/bin/file --brief --mime-encoding \"%s\" 2>&1", path)));
        if (file_enc.find("binary") != string::npos) return;

        cout << path << endl;

        // Index the doc_path
        int64_t doc_path_id = lookup_doc_path(path);
        index_blocks(doc_path_id, &path, &path + 1);

        // Index the doc_file
        int64_t docid = lookup_doc_file(doc_path_id);
        ifstream in(path, ios::binary);
        REQUIRE(in.good(), "Could not open file " << path);
        util::FileIterator fi_begin(&in, 16384);
        util::FileIterator fi_end(nullptr, 0);
        index_blocks(docid, fi_begin, fi_end);

        // Delete existing matches
        conn->exec(util::fmt("DELETE FROM match WHERE doc_id = %s", doc_path_id));
        conn->exec(util::fmt("DELETE FROM match WHERE doc_id = %s", docid));
    }

    void Index::search(string word)
    {
        int64_t word_id = lookup_word(word);
        Statement_docid stmt(conn,
            util::fmt("SELECT doc_id FROM match WHERE word_id=%s", word_id));
        while (stmt.step())
        {
            // Get path
            Statement_id stmt2(conn,
                util::fmt("SELECT path FROM doc_path WHERE id=%s", stmt.col<docid>()));
            if (stmt2.step())
            {
                cout << "Path: " << build_path(stmt.col<docid>()) << endl;
            }

            // Get file
            stmt2.reset(util::fmt("SELECT path FROM doc_file WHERE id=%s", stmt.col<docid>()));
            if (stmt2.step())
            {
                cout << "File: " << build_path(stmt2.col<0>()) << endl;
            }
        }
    }

    void Index::create_tables()
    {
        // The base class for all documents. A document is something that can be
        // found using the index
        conn->table("doc", "id INTEGER PRIMARY KEY, type_ INTEGER NOT NULL, create_time INTEGER NOT NULL DEFAULT (strftime('%s', 'now')), update_time INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))");

        // The classes derived from doc
        conn->table("doc_path", "id INTEGER PRIMARY KEY, path INTEGER NOT NULL UNIQUE");
        conn->table("doc_file", "id INTEGER PRIMARY KEY, path INTEGER NOT NULL UNIQUE");

        // Each indexed word appears only once in the DB in that table
        conn->table("word", "id INTEGER PRIMARY KEY, word TEXT NOT NULL UNIQUE");

        // This table joins word and doc
        conn->table("match", "word_id INTEGER, doc_id INTEGER, count INTEGER NOT NULL, avgidx INTEGER NOT NULL, PRIMARY KEY(word_id, doc_id)", "WITHOUT ROWID");

        // The path table's purpose is to store the paths as separate components,
        // hopefully to reduce storage (todo: is this useful?). It also stores a
        // default root with an id of 1.
        conn->table("path", "id INTEGER PRIMARY KEY, name TEXT NOT NULL, parent INTEGER, UNIQUE(name, parent)");
        conn->exec("INSERT OR IGNORE INTO path(id, name) VALUES(1, 'root')");
    }

    int64_t Index::lookup_word(string word)
    {
        Statement_id stmt(conn, util::fmt("SELECT id FROM word WHERE word='%s';", word));
        if (stmt.step()) return stmt.col<0>();
        return conn->insert("word(word)", util::fmt("'%s'", word));
    }

    string Index::build_path(int64_t doc_path_id)
    {
        // Find the path object
        Statement_id stmt_path(conn, util::fmt("SELECT path FROM doc_path WHERE id=%s", doc_path_id));
        if (!stmt_path.step()) REQUIRE(false, "doc_path id not found: " << doc_path_id);

        // Build the path
        string path;
        Statement<ColSpec<ColDef<name, string>, ColDef<parent, int64_t>>>
            stmt_name_parent(conn, util::fmt("SELECT name, parent FROM path WHERE id=%s;", stmt_path.col<0>()));
        if (stmt_name_parent.step())
        {
            while (stmt_name_parent.col<parent>() > 0)
            {
                path = string("/") + stmt_name_parent.col<name>() + path;
                stmt_name_parent.reset(util::fmt("SELECT name, parent FROM path WHERE id=%s;", stmt_name_parent.col<parent>()));
                bool res = stmt_name_parent.step();
                REQUIRE(res, "Could not find parent: " << stmt_name_parent.col<parent>());
            }
            return path;
        }
        else return "<path not found>";
    }

    int64_t Index::lookup_doc_path(string path)
    {
        int64_t parent = 1; // 1 is the root
        for (auto tok: util::Tokenizer<'/'>(path).toks)
        {
            Statement_id stmt(conn, util::fmt("SELECT id FROM path WHERE name='%s' AND parent=%s;", tok, parent));
            if (stmt.step()) parent = stmt.col<id>();
            else
            {
                parent = conn->insert("path(name, parent)", util::fmt("'%s', %s", tok, parent));
            }
        }

        // Find or create corresponding doc_path
        Statement_id stmt(conn, util::fmt("SELECT id FROM doc_path WHERE path=%s", parent));
        if (stmt.step()) return stmt.col<id>();
        int64_t newdoc = conn->insert("doc(type_)", util::fmt("%s", DOCTYPE_PATH));
        return conn->insert("doc_path(id, path)", util::fmt("%s, %s", newdoc, parent));
    }

    int64_t Index::lookup_doc_file(int64_t path_id)
    {
        string s = util::fmt("SELECT id FROM doc_file WHERE path=%s", path_id);
        Statement_id stmt(conn, s);
        if (stmt.step()) return stmt.col<id>();
        int64_t newdoc = conn->insert("doc(type_)", util::fmt("%s", DOCTYPE_FILE));
        return conn->insert("doc_file(id, path)", util::fmt("%s, %s", newdoc, path_id));
    }
}}

