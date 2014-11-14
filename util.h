#ifndef UTIL_H
#define UTIL_H

#include <fstream>
#include <stdexcept>
#include <sstream>
#include <string>
#include <vector>

// This macro implements a sort of assert that will also be enabled in release
#define REQUIRE(cond, msg) if (!(cond)) {\
    std::ostringstream oss; \
    oss << __FILE__ << "(" << __LINE__ << "):" << __FUNCTION__ << ": " << msg; \
    throw std::runtime_error(oss.str());}

bool                     isfile (std::string path);
bool                     isdir  (std::string path);
std::string              abspath(std::string path);
std::vector<std::string> tokenize(std::string s, char delim);
std::string              runcmd(std::string cmd);

// Iterates on an opened file and yields blocks of bytes
class FileIterator
{
public:
    FileIterator(std::ifstream* fin, int block_size) : in_stream(fin)
                                                     , block(block_size)
                                                     , block_size(block_size)
                                                     , finished(!fin)
    {
    }
    bool operator!=(const FileIterator& other) const
    {
        return other.finished != finished;
    }
    FileIterator& operator++()
    {
        REQUIRE(in_stream, "in_stream is null");
        block.resize(block_size);
        in_stream->read(block.data(), block.size());
        block.resize(in_stream->gcount());
        if (!(*in_stream)) finished = true;
        return *this;
    }
    std::vector<char>* operator->()
    {
        return &block;
    }
private:
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

#endif

