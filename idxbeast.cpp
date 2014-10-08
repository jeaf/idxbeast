#define DLLEXP extern "C" __attribute__((dllexport))

#include "charmap.c"

#include <cstdint>
#include <iostream>
#include <sstream>
#include <stdexcept>

using namespace std;

#define REQUIRE(cond, msg) if (!(cond)) {\
    ostringstream oss; \
    oss << msg << " @ " << __FUNCTION__ << "(" << __LINE__ << ")"; \
    throw runtime_error(oss.str());}

DLLEXP int parse_doc(int64_t docid, uint32_t* text, int64_t textlen)
{
    REQUIRE(docid   > 0, "docid must be larger than 0"      )
    REQUIRE(text       , "text cannot be NULL"              )
    REQUIRE(textlen > 0, "text length must be larger than 0")

    return 0;
}

