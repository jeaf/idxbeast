#include <stdexcept>
#include <sstream>

// This macro implements a sort of assert that will also be enabled in release
#define REQUIRE(cond, msg) if (!(cond)) {\
    std::ostringstream oss; \
    oss << msg << " @ " << __FUNCTION__ << "(" << __LINE__ << ")"; \
    throw std::runtime_error(oss.str());}

