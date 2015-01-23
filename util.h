#ifndef UTIL_H
#define UTIL_H

#include <fstream>
#include <iostream>
#include <stdexcept>
#include <sstream>
#include <string>
#include <vector>

// This macro implements a sort of assert that will also be enabled in release
#define REQUIRE(cond, msg) if (!(cond)) {\
    std::ostringstream oss; \
    oss << __FILE__ << "(" << __LINE__ << "):" << __FUNCTION__ << ": " << msg; \
    throw std::runtime_error(oss.str());}

namespace idxb { namespace util
{
    ///////////////////////////////////////////////////////////////////////////
    // TypeAt
    ///////////////////////////////////////////////////////////////////////////
    template <int I, typename... Ts> struct TypeAt;
    template <typename H, typename... Ts>
    struct TypeAt<0, H, Ts...>
    {
        typedef H type;
    };
    template <int I, typename H, typename... Ts>
    struct TypeAt<I, H, Ts...>
    {
        static_assert(I > 0, "TypeAt index negative");
        typedef typename TypeAt<I - 1, Ts...>::type type;
    };
    template <int I>
    struct TypeAt<I> { static_assert(I < 0, "TypeAt index out of bounds"); };

    ///////////////////////////////////////////////////////////////////////////
    // Misc
    ///////////////////////////////////////////////////////////////////////////
    struct EmptyType {};

    bool                     isfile (std::string path);
    bool                     isdir  (std::string path);
    std::string              abspath(std::string path);
    std::string              runcmd(std::string cmd);

    template <char delim>
    class Tokenizer
    {
    public:
        Tokenizer(std::string s)
        {
            std::string cur_tok;
            for (char c: s)
            {
                if (c != delim) cur_tok += c;
                else if (!cur_tok.empty())
                {
                    toks.push_back(cur_tok);
                    cur_tok.clear();
                }
            }
            if (!cur_tok.empty()) toks.push_back(cur_tok);
        }

        std::vector<std::string> toks;
    };

    // Iterates on an opened file and yields blocks of bytes
    class FileIterator
    {
    public:
        FileIterator(std::ifstream* fin, int block_size) : in_stream(fin)
                                                         , block(block_size)
                                                         , block_size(block_size)
                                                         , finished(!fin)
        {
            if (!finished) read_block();
        }
        bool operator!=(const FileIterator& other) const
        {
            return other.finished != finished;
        }
        FileIterator& operator++()
        {
            read_block();
            return *this;
        }
        std::vector<char>* operator->()
        {
            REQUIRE(!finished, "Using invalid iterator");
            return &block;
        }
    private:
        void read_block()
        {
            REQUIRE(in_stream, "in_stream is null");
            block.resize(block_size);
            in_stream->read(block.data(), block.size());
            block.resize(in_stream->gcount());
            if (block.empty()) finished = true;
        }

        std::ifstream*    in_stream;
        std::vector<char> block;
        int               block_size;
        bool              finished;
    };

    std::string fmt(std::string s);

    template <typename T, typename... TArgs>
    std::string fmt(std::string s, T arg, TArgs... args)
    {
        std::ostringstream oss;
        size_t pos = s.find("%s");
        if (pos != std::string::npos)
        {
            oss << s.substr(0, pos) << arg;
            oss << fmt(s.substr(pos + 2), args...);
            return oss.str();
        }
        else return s;
    }

    std::vector<std::string> listdir(std::string path);
}}

#endif

