#include <stdexcept>
#include <sstream>
#include <string>

// This macro implements a sort of assert that will also be enabled in release
#define REQUIRE(cond, msg) if (!(cond)) {\
    std::ostringstream oss; \
    oss << __FUNCTION__ << "(" << __LINE__ << "): " << msg; \
    throw std::runtime_error(oss.str());}

bool isfile(std::string path);
bool isdir(std::string path);

