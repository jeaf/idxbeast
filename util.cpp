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

