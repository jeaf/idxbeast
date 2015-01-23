#include <iostream>

#include "db.h"
#include "core.h"

using namespace idxb;
using namespace idxb::db;
using namespace std;

namespace
{
    struct wordid; struct docid; struct word;
}

int main()
{
    auto conn = make_shared<Connection>(":memory:");
    core::Index idx(conn);
    idx.index_file("testdata_small.txt");
    idx.commit();
    idx.search("abc");

    cout << "match" << endl;
    Statement<ColSpec<ColDef<wordid, int64_t>, ColDef<docid, int64_t>>> s(conn,
        "SELECT word_id, doc_id FROM match");
    while (s.step())
    {
        cout << s.col<wordid>() << ", " << s.col<docid>() << endl;
    }

    cout << "word" << endl;
    Statement<ColSpec<ColDef<wordid, int64_t>, ColDef<word, string>>> stmt_word(
        conn, "SELECT id, word FROM word");
    while (stmt_word.step())
    {
        cout << stmt_word.col<wordid>() << ", " << stmt_word.col<word>() << endl;
    }

    return 0;
}

