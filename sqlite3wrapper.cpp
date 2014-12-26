#include <cstring>
#include <iostream>

#include "sqlite3wrapper.h"
#include "util.h"

using namespace std;

namespace sqlite
{
    Statement::Statement(sqlite3* db, string sql) : stmt(nullptr)
    {
        REQUIRE(db, "db is null");
        int res = sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, NULL);
        REQUIRE(res == SQLITE_OK, "Error: " << sqlite3_errstr(res) << " (" << res << ") sql: " << sql);
        REQUIRE(stmt, "Error, stmt is null");
    }

    Statement::~Statement()
    {
        sqlite3_finalize(stmt);
    }

    bool Statement::step()
    {
        int res = sqlite3_step(stmt);
        REQUIRE(res == SQLITE_ROW || res == SQLITE_DONE,
                "sqlite3_step failed: " << sqlite3_errstr(res) << " (" << res << ")");
        return res == SQLITE_ROW;
    }

    Connection::Connection(string path) : db(nullptr)
    {
        int rc = sqlite3_open(path.c_str(), &db);
        REQUIRE(!rc, "Can't open database: " << sqlite3_errmsg(db))
    }

    Connection::~Connection()
    {
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

    int64_t Connection::insert(string table, string values, bool check_rowid)
    {
        string sql = fmt("INSERT INTO %s VALUES(%s);", table, values);
        if (values.empty())
        {
            sql = fmt("INSERT INTO %s DEFAULT VALUES;", table);
        }
        exec(sql);
        int64_t rowid = lastrowid();
        if (check_rowid) REQUIRE(rowid, "Could not get lastrowid")
        return rowid;
    }

    int64_t Connection::lastrowid()
    {
        return sqlite3_last_insert_rowid(db);
    }

    Transaction::Transaction(std::shared_ptr<Connection> c) : conn(c)
    {
        REQUIRE(c, "Invalid parameter, c is null");
        conn->exec("BEGIN TRANSACTION");
    }

    Transaction::~Transaction()
    {
        conn->exec("COMMIT");
    }
}

