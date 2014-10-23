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

