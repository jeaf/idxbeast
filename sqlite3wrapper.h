// todo: make sure all prepared statements are finalized before closing the DB
//       connection

#ifndef SQLITE3WRAPPER_H
#define SQLITE3WRAPPER_H

#include <memory>
#include <string>

#include "sqlite3.h"

#include "util.h"

namespace sqlite
{
    template <typename T, int col_idx> struct Column{};

    template <int col_idx>
    struct Column<int64_t, col_idx>
    {
        int64_t get(sqlite3_stmt* stmt)
        {
            return sqlite3_column_int64(stmt, col_idx);
        }
    };

    template <int col_idx>
    struct Column<std::string, col_idx>
    {
        std::string get(sqlite3_stmt* stmt)
        {
            const unsigned char* s = sqlite3_column_text(stmt, col_idx);
            return s ? reinterpret_cast<const char*>(s) : "";
        }
    };

    class EmptyType{};

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

    template <typename T0 = EmptyType, typename T1 = EmptyType>
    class Statement
    {
    public:
        Statement(sqlite3* db, std::string sql) : stmt_(nullptr)
        {
            reset(db, sql);
        }

        Statement(const Statement&)            = delete;
        Statement& operator=(const Statement&) = delete;

        ~Statement()
        {
            sqlite3_finalize(stmt_);
        }

        void reset(sqlite3* db, std::string sql)
        {
            sqlite3_finalize(stmt_);
            REQUIRE(db, "db is null");
            int res = sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt_, NULL);
            REQUIRE(res == SQLITE_OK, "Error: " << sqlite3_errstr(res) << " (" << res << ") sql: " << sql);
            REQUIRE(stmt_, "Error, stmt_ is null");
        }

        bool step()
        {
            int res = sqlite3_step(stmt_);
            REQUIRE(res == SQLITE_ROW || res == SQLITE_DONE,
                    "sqlite3_step failed: " << sqlite3_errstr(res) << " (" << res << ")");
            return res == SQLITE_ROW;
        }

        T0 col0()
        {
            return col0_.get(stmt_);
        }

        T1 col1()
        {
            return col1_.get(stmt_);
        }

    private:
        sqlite3_stmt* stmt_;

        Column<T0, 0> col0_;
        Column<T1, 1> col1_;
    };

    class Transaction
    {
    public:
        Transaction(std::shared_ptr<Connection> c);
        Transaction(const Transaction&) = delete;
        Transaction& operator=(const Transaction&) = delete;
        ~Transaction();

        void commit();

    private:
        std::shared_ptr<Connection> conn;
        bool committed_;
    };
}

#endif

