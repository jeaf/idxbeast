#include <fstream>
#include <iostream>
#include <string>
#include <type_traits>
#include <vector>

using namespace std;

template <int I>
struct Int2Type
{
    enum { value = I };
};

template <int I, typename T>
struct Col
{
    T get()
    {
        return T();
    }
};

template <typename T0, typename T1>
struct Stmt
{
    Col<0, T0> col0;
    Col<1, T1> col1;
};

int main()
{
    //Stmt<int, string> s;
    //cout << "0: " << s.get<0>() << endl;
    ifstream in;
    in.open("testdata_small.txt");
    vector<char> b(16000);
    in.read(b.data(), b.size());
    return 0;
}

