// todo: make sure all prepared statements are finalized before closing the DB
//       connection

#include <memory>
#include <string>

#include "sqlite3.h"

namespace sqlite
{
    class Statement
    {
    public:
        Statement(sqlite3* db, std::string sql);
        ~Statement();

        bool step();

        int64_t     col_int64(int col);
        std::string col_text(int col);

    private:
        sqlite3_stmt* stmt;

        // Disabled copy constructor and assignment operator
        Statement(const Statement&)            = delete;
        Statement& operator=(const Statement&) = delete;
    };

    class Connection
    {
    public:
        Connection(std::string path);
        ~Connection();

        std::shared_ptr<Statement> prepare(std::string sql);
        void exec(std::string sql);
        void table(std::string name, std::string cols, std::string extra = "");
        int64_t insert(std::string table, std::string values = "", bool check_rowid = true);
        int64_t lastrowid();

    private:
        sqlite3* db;

        // Disabled copy constructor and assignment operator
        Connection(const Connection&)            = delete;
        Connection& operator=(const Connection&) = delete;
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

