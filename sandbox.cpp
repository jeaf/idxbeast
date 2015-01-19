#include <fstream>
#include <iostream>
#include <string>
#include <type_traits>
#include <vector>

using namespace std;

template <int I> struct Int2Type{};

template <int I, typename... Ts> struct TypeAt;
template <typename H, typename... Ts>
struct TypeAt<0, H, Ts...>
{
    typedef H type;
};
template <int I, typename H, typename... Ts>
struct TypeAt<I, H, Ts...>
{
    static_assert(I > 0, "TypeAt index negative");
    typedef typename TypeAt<I - 1, Ts...>::type type;
};
template <int I>
struct TypeAt<I>
{
    static_assert(I < 0, "TypeAt index out of bounds");
};

template <int I, typename... Ts> struct Col {};
template <int I, typename H, typename... Ts>
struct Col<I, H, Ts...> : Col<I + 1, Ts...>
{
    template <typename R>
    R get(Int2Type<I>)
    {
        return R();
    }

    template <typename R, int J>
    R get(Int2Type<J> tag)
    {
        return Col<I + 1, Ts...>::template get<R>(tag);
    }
};
template <typename... Ts>
struct Stmt : Col<0, Ts...>
{
    template <int I>
    typename TypeAt<I, Ts...>::type get()
    {
        typedef typename TypeAt<I, Ts...>::type RetType;
        return Col<0, Ts...>::template get<RetType>(Int2Type<I>());
    }
};

int main()
{
    Stmt<int, double, string> s;
    cout << "0: " << s.get<0>() << endl;
    cout << "1: " << s.get<1>() << endl;
    cout << "2: " << s.get<2>() << endl;
    //cout << "3: " << s.get<3>() << endl;
    return 0;
}

