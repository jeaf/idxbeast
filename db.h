// todo: make sure all prepared statements are finalized before closing the DB
//       connection

#ifndef SQLITE3WRAPPER_H
#define SQLITE3WRAPPER_H

#include <memory>
#include <string>

#include "sqlite3.h"

#include "util.h"

using namespace std;
using namespace idxb::util;

namespace idxb { namespace db
{
    ///////////////////////////////////////////////////////////////////////////
    // SqliteTraits
    ///////////////////////////////////////////////////////////////////////////
    template <typename T, int I = 0> struct SqliteTraits
    {
        static T col(sqlite3_stmt*)
            {static_assert(I!=I, "Unsupported type");}
        static void bind(sqlite3_stmt*, T)
            {static_assert(I!=I, "Unsupported type");}
    };

    template <int I> struct SqliteTraits<int64_t, I>
    {
        static int64_t col(sqlite3_stmt* stmt)
        {
            return sqlite3_column_int64(stmt, I);
        }
        static void bind(sqlite3_stmt* stmt, int64_t val)
        {
            int res = sqlite3_bind_int64(stmt, I, val);
            REQUIRE(res == SQLITE_OK, "error: " << res);
        }
    };

    template <int I> struct SqliteTraits<string, I>
    {
        static string col(sqlite3_stmt* stmt)
        {
            const unsigned char* s = sqlite3_column_text(stmt, I);
            return s ? reinterpret_cast<const char*>(s) : "";
        }
        static void bind(sqlite3_stmt* stmt, string val)
        {
            int res = sqlite3_bind_text(stmt, I, val.c_str(), -1, SQLITE_TRANSIENT);
            REQUIRE(res == SQLITE_OK, "error: " << res);
        }
    };

    ///////////////////////////////////////////////////////////////////////////
    // SqliteStmtHolder
    ///////////////////////////////////////////////////////////////////////////
    struct SqliteStmtHolder
    {
    protected:
        sqlite3_stmt* stmt_;
    };

    //////////////////////////////////////////////////////////////////////////////
    // ColDef
    //////////////////////////////////////////////////////////////////////////////
    template <int TagValue, typename Type>
    struct ColDef
    {
        enum {tag = TagValue};
        typedef Type type;
    };

    template <int Tag, typename... Ts> struct ColDefLookup;
    template <int Tag, typename H, typename... Ts>
    struct ColDefLookup<Tag, H, Ts...>
    {
        typedef typename
            conditional<Tag == H::tag,
                        H,
                        typename ColDefLookup<Tag, Ts...>::result
                       >::type result;
    };
    template <int Tag> struct ColDefLookup<Tag>
    {
        typedef struct ErrorColDefNotFound result;
    };

    //////////////////////////////////////////////////////////////////////////////
    // Col
    //////////////////////////////////////////////////////////////////////////////
    template <int ColIdx, typename... Ts> struct Col{};
    template <int ColIdx, typename H, typename... Ts>
    struct Col<ColIdx, H, Ts...> : Col<ColIdx + 1, Ts...>
    {
        template <typename R>
        R col(sqlite3_stmt* stmt, integral_constant<int, H::tag>)
        {
            return SqliteTraits<R, ColIdx>::col(stmt);
        }

        template <typename R, typename T>
        R col(sqlite3_stmt* stmt, T tag)
        {
            return Col<ColIdx + 1, Ts...>::template col<R>(stmt, tag);
        }
    };

    //////////////////////////////////////////////////////////////////////////////
    // ColSpec
    //////////////////////////////////////////////////////////////////////////////
    template <typename... Ts>
    struct ColSpec : Col<0, Ts...>, virtual SqliteStmtHolder
    {
        template <int ColTag>
        typename ColDefLookup<ColTag, Ts...>::result::type col()
        {
            typedef typename ColDefLookup<ColTag, Ts...>::result::type RetType;
            return Col<0, Ts...>::template col<RetType>(stmt_, integral_constant<int, ColTag>());
        }
    };

    //////////////////////////////////////////////////////////////////////////////
    // Bind
    //////////////////////////////////////////////////////////////////////////////
    template <int I, typename... Ts> struct Bind{};
    template <int I, typename H, typename... Ts>
    struct Bind<I, H, Ts...> : Bind<I + 1, Ts...>
    {
        template <typename T>
        void bind(sqlite3_stmt* stmt, integral_constant<int, I>, T val)
        {
            SqliteTraits<T, I>::bind(stmt, val);
        }

        template <typename T, int Idx>
        void bind(sqlite3_stmt* stmt, integral_constant<int, Idx> col_idx, T val)
        {
            Bind<I + 1, Ts...>::template bind<T>(stmt, col_idx, val);
        }
    };

    //////////////////////////////////////////////////////////////////////////////
    // BindSpec
    //////////////////////////////////////////////////////////////////////////////
    template <typename... Ts>
    struct BindSpec : Bind<0, Ts...>, virtual SqliteStmtHolder
    {
        template <int I>
        void bind(typename TypeAt<I, Ts...>::type val)
        {
            Bind<0, Ts...>::template bind<typename TypeAt<I, Ts...>::type>(
                stmt_, integral_constant<int, I>(), val);
        }
    };

    ///////////////////////////////////////////////////////////////////////////
    // Connection
    ///////////////////////////////////////////////////////////////////////////
    class Connection
    {
        template <typename T0, typename T1> friend class Stmt;

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

    ///////////////////////////////////////////////////////////////////////////
    // Stmt
    ///////////////////////////////////////////////////////////////////////////
    template <typename Spec1 = EmptyType, typename Spec2 = EmptyType>
    class Stmt : public Spec1, public Spec2, virtual SqliteStmtHolder
    {
    public:
        Stmt(std::shared_ptr<Connection> conn, std::string sql) : conn_(conn)
        {
            stmt_ = nullptr;
            reset(sql);
        }

        Stmt(const Stmt&)            = delete;
        Stmt& operator=(const Stmt&) = delete;

        ~Stmt()
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
                return true;
            }
            else
            {
                return false;
            }
        }

    private:
        std::shared_ptr<Connection> conn_;
    };

    ///////////////////////////////////////////////////////////////////////////
    // Transaction
    ///////////////////////////////////////////////////////////////////////////
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

