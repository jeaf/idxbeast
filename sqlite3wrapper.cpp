#include <iostream>

#include "sqlite3wrapper.h"
#include "util.h"

using namespace std;

namespace sqlite
{
    Statement::Statement(sqlite3* db, string sql) : stmt(nullptr)
    {
        sqlite3_prepare_v2(db, sql.c_str(), sql.size(), &stmt, NULL);
    }

    Statement::~Statement()
    {
        sqlite3_finalize(stmt);
    }

    bool Statement::step()
    {
        int res = sqlite3_step(stmt);
        return res == SQLITE_ROW;
    }

    int64_t Statement::col_int64(int col)
    {
        return sqlite3_column_int64(stmt, col);
    }

    Connection::Connection(string path) : db(nullptr)
    {
        cout << "Connecting to database " << path << endl;
        int rc = sqlite3_open(path.c_str(), &db);
        REQUIRE(!rc, "Can't open database: " << sqlite3_errmsg(db))
    }

    Connection::~Connection()
    {
        cout << "Closing connection to database" << endl;
        sqlite3_close_v2(db);
    }

    shared_ptr<Statement> Connection::prepare(string sql)
    {
        return make_shared<Statement>(db, sql);
    }

    void Connection::exec(string sql)
    {
        char* errmsg = nullptr;
        sqlite3_exec(db, sql.c_str(), nullptr, nullptr, &errmsg);
        string s = errmsg ? errmsg : "";
        sqlite3_free(errmsg);
        REQUIRE(s.empty(), s << ", " << sql);
    }

    void Connection::table(string name, string cols, string extra)
    {
        string sql("CREATE TABLE IF NOT EXISTS ");
        sql += name;
        sql += "(";
        sql += cols;
        sql += ")";
        sql += extra;
        sql += ";";
        exec(sql);
    }
}

