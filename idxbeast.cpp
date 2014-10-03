#define DLLEXP extern "C" __attribute__((dllexport))

#include <iostream>

using namespace std;

DLLEXP int test()
{
    cout << "abc" << endl;
    return 22;
}

