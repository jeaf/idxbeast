#include <iostream>

#include "core.h"
#include "util.h"

using namespace std;
using namespace idxb;

int main(int argc, char* argv[])
{
    try
    {
        auto conn = make_shared<db::Connection>("idxbeast.db");
        core::Index idx(conn);
        if (argc <= 2)
        {
            cout << "Missing argument." << endl;
            cout << "Usage: idxbeast.exe [index | search] [file | search term]" << endl;
            return 1;
        }
        string cmd = argv[1];
        if (cmd == "index")
        {
            cout << "Indexing..." << endl;
            string path = util::abspath(argv[2]);
            if (util::isdir(path))
            {
                for (auto f: util::listdir(path)) idx.index_file(f);
            }
            else if (util::isfile(path)) idx.index_file(path);
            else REQUIRE(false, "Path not found: " << path)
            idx.commit();
        }
        else if (cmd == "search")
        {
            idx.search(argv[2]);
        }
        else
        {
            REQUIRE(false, "Invalid command: " << cmd);
        }
        return 0;
    }
    catch (const std::exception& ex)
    {
        cout << "Exception:" << endl;
        cout << ex.what() << endl;
    }
}

