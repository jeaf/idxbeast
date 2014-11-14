#include <iostream>

#include "idxlib.h"
#include "util.h"

using namespace std;

int main(int argc, char* argv[])
{
    try
    {
        create_tables();
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
            string path = abspath(argv[2]);
            if (isdir(path))
            {
                for (auto f: listdir(path)) index_file(f);
            }
            else if (isfile(path)) index_file(path);
            else REQUIRE(false, "Path not found: " << path)
            dump_index();
        }
        else if (cmd == "search")
        {
            search(argv[2]);
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

