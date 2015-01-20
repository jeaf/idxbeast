#include <fstream>
#include <iostream>
#include <string>
#include <type_traits>
#include <vector>

using namespace std;

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
struct TypeAt<I> { static_assert(I < 0, "TypeAt index out of bounds"); };

template <int I, typename T>
struct ColGetter { static_assert(I < 0, "Unsupported type"); };
template <int I>
struct ColGetter<I, int64_t> { static int64_t get() { return 3; } };
template <int I>
struct ColGetter<I, double> { static double get() { return 999.111; } };
template <int I>
struct ColGetter<I, string> { static string get() { return "abc"; } };

template <int I, typename... Ts> struct Col {};
template <int I, typename H, typename... Ts>
struct Col<I, H, Ts...> : Col<I + 1, Ts...>
{
    template <typename R>
    R get(integral_constant<int, I>)
    {
        return ColGetter<I, R>::get();
    }

    template <typename R, int J>
    R get(integral_constant<int, J> tag)
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
        return Col<0, Ts...>::template get<RetType>(integral_constant<int, I>());
    }
};

template <int I, typename T>
struct ColDef : integral_constant<int, I> { typedef T type; };

template <int I, typename... Ts> struct ColDefLookup;
template <int I, typename H, typename... Ts>
struct ColDefLookup<I, H, Ts...>
{
    typedef typename
        conditional<I == H::value,
                    H,
                    typename ColDefLookup<I, Ts...>::result
                   >::type result;
};
template <int I> struct ColDefLookup<I>
{
    typedef struct ErrorColDefNotFound result;
};

template <int ColIdx, typename... Ts> struct Col2{};
template <int ColIdx, typename H, typename... Ts>
struct Col2<ColIdx, H, Ts...> : Col2<ColIdx + 1, Ts...>
{
    template <typename R>
    R get(integral_constant<int, H::value>)
    {
        return ColGetter<ColIdx, R>::get();
    }

    template <typename R, int J>
    R get(integral_constant<int, J> tag)
    {
        return Col2<ColIdx + 1, Ts...>::template get<R>(tag);
    }
};

template <typename... Ts>
struct Stmt2 : Col2<0, Ts...>
{
    template <int ColDefId>
    typename ColDefLookup<ColDefId, Ts...>::result::type get()
    {
        typedef typename ColDefLookup<ColDefId, Ts...>::result::type RetType;
        return Col2<0, Ts...>::template get<RetType>(integral_constant<int, ColDefId>());
    }
};

int main()
{
    Stmt<int64_t, string, double> s;
    cout << "0: " << s.get<0>() << endl;
    cout << "1: " << s.get<1>() << endl;
    cout << "2: " << s.get<2>() << endl;
    //cout << "3: " << s.get<3>() << endl;
    cout << endl;

    Stmt2<ColDef<'c1'  , int64_t>,
          ColDef<'c2'  , double >,
          ColDef<'test', string >,
          ColDef<'alfa', int64_t>> s2;
    cout << "c1: "   << s2.get<'c1'>() << endl;
    cout << "c2: "   << s2.get<'c2'>() << endl;
    cout << "test: " << s2.get<'test'>() << endl;
    cout << "alfa: " << s2.get<'alfa'>() << endl;

    return 0;
}

