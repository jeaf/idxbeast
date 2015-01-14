// todo: make sure all prepared statements are finalized before closing the DB
//       connection

#ifndef SQLITE3WRAPPER_H
#define SQLITE3WRAPPER_H

#include <memory>
#include <string>

#include "sqlite3.h"

#include "util.h"

namespace idxb { namespace db
{
    template <typename T, int col_idx>
    struct Column
    {
        static void get(T&, sqlite3_stmt*)
        {
        }
    };

    template <int col_idx>
    struct Column<int64_t, col_idx>
    {
        static void get(int64_t& o_val, sqlite3_stmt* stmt)
        {
            o_val = sqlite3_column_int64(stmt, col_idx);
        }
    };

    template <int col_idx>
    struct Column<std::string, col_idx>
    {
        static void get(std::string& o_val, sqlite3_stmt* stmt)
        {
            const unsigned char* s = sqlite3_column_text(stmt, col_idx);
            o_val = s ? reinterpret_cast<const char*>(s) : "";
        }
    };

    class Connection
    {
        template <typename T0, typename T1> friend class Statement;

    public:
        Connection(std::string path);
        Connection(const Connection&)            = delete;
        Connection& operator=(const Connection&) = delete;
        ~Connection();

        void exec(std::string sql);
        void table(std::string name, std::string cols, std::string extra = "");
        int64_t insert(std::string table, std::string values = "", bool check_rowid = true);
        int64_t lastrowid();

    private:
        sqlite3* db;
    };

    class EmptyType {};

    template <typename T0 = EmptyType, typename T1 = EmptyType>
    class Statement
    {
    public:
        Statement(std::shared_ptr<Connection> conn, std::string sql) : conn_(conn), stmt_(nullptr)
        {
            reset(sql);
        }

        Statement(const Statement&)            = delete;
        Statement& operator=(const Statement&) = delete;

        ~Statement()
        {
            sqlite3_finalize(stmt_);
        }

        void reset(std::string sql)
        {
            sqlite3_finalize(stmt_);
            int res = sqlite3_prepare_v2(conn_->db, sql.c_str(), -1, &stmt_, NULL);
            REQUIRE(res == SQLITE_OK, "Error: " << sqlite3_errstr(res) << " (" << res << ") sql: " << sql);
            REQUIRE(stmt_, "Error, stmt_ is null");
        }

        bool step()
        {
            int res = sqlite3_step(stmt_);
            REQUIRE(res == SQLITE_ROW || res == SQLITE_DONE,
                    "sqlite3_step failed: " << sqlite3_errstr(res) << " (" << res << ")");
            if (res == SQLITE_ROW)
            {
                Column<T0, 0>::get(col0, stmt_);
                Column<T1, 1>::get(col1, stmt_);
                return true;
            }
            else
            {
                return false;
            }
        }

        T0 col0;
        T1 col1;

    private:
        std::shared_ptr<Connection> conn_;
        sqlite3_stmt* stmt_;
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
}}

#endif

