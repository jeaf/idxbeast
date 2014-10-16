#include <string>

#include "sqlite3.h"

namespace sqlite
{
    class Connection
    {
    public:
        Connection(std::string path);

    private:
        sqlite3* db;
    };
}

