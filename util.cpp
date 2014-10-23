#include <cerrno>
#include <cstdlib>
#include <limits.h>
#include <memory>
#include <sys/stat.h>
#include <unistd.h>

#include "util.h"

using namespace std;

bool isfile(string path)
{
    struct stat sb;
    stat(path.c_str(), &sb);
    return S_ISREG(sb.st_mode);
}

bool isdir(string path)
{
    struct stat sb;
    stat(path.c_str(), &sb);
    return S_ISDIR(sb.st_mode);
}

string abspath(string path)
{
    unique_ptr<char, void(*)(void*)> res(realpath(path.c_str(), nullptr), std::free);
    REQUIRE(res, "realpath error: " << errno << ", " << path);
    return res.get();
}

vector<string> tokenize(string s, char delim)
{
    vector<string> tokens;
    string cur_tok;
    for (char c: s)
    {
        if (c != delim) cur_tok += c;
        else if (!cur_tok.empty())
        {
            tokens.push_back(cur_tok);
            cur_tok.clear();
        }
    }
    if (!cur_tok.empty()) tokens.push_back(cur_tok);
    return tokens;
}

