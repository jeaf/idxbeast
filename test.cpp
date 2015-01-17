#include <iostream>

#include "core.h"

using namespace std;
using namespace idxb;

int main()
{
    auto conn = make_shared<db::Connection>(":memory:");
    core::Index idx(conn);
    idx.index_file("testdata_small.txt");
    idx.commit();
    idx.search("abc");

    cout << "match" << endl;
    db::Statement<int64_t, int64_t> s(conn, "SELECT word_id, doc_id FROM match");
    while (s.step())
    {
        cout << s.col0 << ", " << s.col1 << endl;
    }

    cout << "word" << endl;
    db::Statement<int64_t, string> stmt_word(conn, "SELECT id, word FROM word");
    while (stmt_word.step())
    {
        cout << stmt_word.col0 << ", " << stmt_word.col1 << endl;
    }

    return 0;
}

