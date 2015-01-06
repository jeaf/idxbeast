#include <cerrno>
#include <cstdlib>
#include <dirent.h>
#include <limits.h>
#include <memory>
#include <sys/stat.h>
#include <unistd.h>

#include "util.h"

using namespace std;

namespace
{
    class ScopedPopen
    {
    public:
        ScopedPopen(string cmd) : fp(nullptr)
        {
            fp = popen(cmd.c_str(), "r");
            REQUIRE(fp, "popen failed: " << cmd);
        }
        ~ScopedPopen()
        {
            pclose(fp);
        }
        FILE* fp;
    };
}

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

string runcmd(string cmd)
{
    ScopedPopen pop(cmd);
    string retval;
    char buf[30];
    while (fgets(buf, sizeof(buf), pop.fp))
    {
        retval += buf;
    }
    return retval;
}

string fmt(string s)
{
    return s;
}

vector<string> listdir(string path)
{
    REQUIRE(isdir(path), "Invalid path: " << path);
    vector<string> out;
    class dirent *ent;
    class stat st;
    DIR* dir = opendir(path.c_str());
    while ((ent = readdir(dir)) != NULL)
    {
        const string file_name = ent->d_name;
        const string full_file_name = path + "/" + file_name;
        if (file_name[0] == '.') continue;
        if (stat(full_file_name.c_str(), &st) == -1) continue;
        const bool is_directory = (st.st_mode & S_IFDIR) != 0;
        if (is_directory)
        {
            vector<string> subdir = listdir(full_file_name);
            out.insert(out.end(), subdir.begin(), subdir.end());
        }
        else
        {
            out.push_back(full_file_name);
        }
    }
    closedir(dir);
    return out;
}

