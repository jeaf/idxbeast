#include "sqlite3wrapper.h"

using namespace std;

namespace sqlite
{
    Connection::Connection(string path) : db(nullptr)
    {
        int rc = sqlite3_open(path.c_str(), &db);
        REQUIRE(!rc, "Can't open database: " << sqlite3_errmsg(db))
    }

    Connection::~Connection()
    {
        sqlite3_close_v2(db);
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

    Transaction::Transaction(std::shared_ptr<Connection> c) : conn(c), committed_(false)
    {
        REQUIRE(c, "Invalid parameter, c is null");
        conn->exec("BEGIN TRANSACTION");
    }

    Transaction::~Transaction()
    {
        if (!committed_) conn->exec("ROLLBACK");
    }

    void Transaction::commit()
    {
        REQUIRE(!committed_, "Transaction already committed");
        conn->exec("COMMIT");
        committed_ = true;
    }
}

