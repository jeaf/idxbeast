// todo: make sure all prepared statements are finalized before closing the DB
//       connection

#include <memory>
#include <string>

#include "sqlite3.h"

#include "util.h"

namespace sqlite
{
    class Connection
    {
    public:
        Connection(std::string path);
        Connection(const Connection&)            = delete;
        Connection& operator=(const Connection&) = delete;
        ~Connection();

        void exec(std::string sql);
        void table(std::string name, std::string cols, std::string extra = "");
        int64_t insert(std::string table, std::string values = "", bool check_rowid = true);
        int64_t lastrowid();

        sqlite3* db;
    };

    class Statement
    {
    public:
        Statement(sqlite3* db, std::string sql) : stmt(nullptr)
        {
            REQUIRE(db, "db is null");
            int res = sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, NULL);
            REQUIRE(res == SQLITE_OK, "Error: " << sqlite3_errstr(res) << " (" << res << ") sql: " << sql);
            REQUIRE(stmt, "Error, stmt is null");
        }

        Statement(const Statement&)            = delete;
        Statement& operator=(const Statement&) = delete;

        ~Statement()
        {
            sqlite3_finalize(stmt);
        }

        void reset(sqlite3* db, std::string sql)
        {
            sqlite3_finalize(stmt);
            REQUIRE(db, "db is null");
            int res = sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, NULL);
            REQUIRE(res == SQLITE_OK, "Error: " << sqlite3_errstr(res) << " (" << res << ") sql: " << sql);
            REQUIRE(stmt, "Error, stmt is null");
        }

        bool step()
        {
            int res = sqlite3_step(stmt);
            REQUIRE(res == SQLITE_ROW || res == SQLITE_DONE,
                    "sqlite3_step failed: " << sqlite3_errstr(res) << " (" << res << ")");
            return res == SQLITE_ROW;
        }

        template <typename T, int col_idx = 0>
        T col()
        {
            return sqlite3_column_int64(stmt, col_idx);
        }

        template <typename T, int col_idx = 0>
        T col_text()
        {
            const unsigned char* s = sqlite3_column_text(stmt, col_idx);
            return s ? reinterpret_cast<const char*>(s) : "";
        }

    private:
        sqlite3_stmt* stmt;
    };

    class Transaction
    {
    public:
        Transaction(std::shared_ptr<Connection> c);
        ~Transaction();

        // Disabled copy constructor and assignment operator
        Transaction(const Transaction&) = delete;
        Transaction& operator=(const Transaction&) = delete;

    private:
        std::shared_ptr<Connection> conn;
    };
}

