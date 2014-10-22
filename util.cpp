#include <cerrno>
#include <cstdlib>
#include <limits.h>
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
    string s(PATH_MAX, 0);
    char* res = realpath(path.c_str(), &s[0]);
    REQUIRE(res, "realpath error: " << errno << ", " << path);
    return s;
}

