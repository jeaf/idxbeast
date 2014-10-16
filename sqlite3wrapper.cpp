#include "sqlite3wrapper.h"
#include "util.h"

using namespace std;

namespace sqlite
{
    Connection::Connection(string path) : db(nullptr)
    {
        int rc = sqlite3_open(path.c_str(), &db);
        REQUIRE(!rc, "Can't open database: " << sqlite3_errmsg(db))
    }
}

