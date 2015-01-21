// todo: check that column IDs are unique (whether they are types of ints)
// todo: use types instead of ints for column ids, and check if template
//       overload works to detect get<0> (use col idx), get<col_id_type> (use
//       col id)
// todo: create traits class for Sqlite (e.g., SqliteTraits) to keeps pointers
//       to functions for each type, e.g., sqlite_column_int, sqlite_bind_int,
//       etc.
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

template <int ColIdx, typename... Ts> struct Col{};
template <int ColIdx, typename H, typename... Ts>
struct Col<ColIdx, H, Ts...> : Col<ColIdx + 1, Ts...>
{
    template <typename R>
    R get(integral_constant<int, H::value>)
    {
        return ColGetter<ColIdx, R>::get();
    }

    template <typename R, int J>
    R get(integral_constant<int, J> tag)
    {
        return Col<ColIdx + 1, Ts...>::template get<R>(tag);
    }
};

template <typename... Ts>
struct Stmt : Col<0, Ts...>
{
    template <int ColDefId>
    typename ColDefLookup<ColDefId, Ts...>::result::type get()
    {
        typedef typename ColDefLookup<ColDefId, Ts...>::result::type RetType;
        return Col<0, Ts...>::template get<RetType>(integral_constant<int, ColDefId>());
    }

    template <int ColIdx>
    typename TypeAt<ColIdx, Ts...>::type::type get_bycol()
    {
        typedef typename TypeAt<ColIdx, Ts...>::type ColDefType;
        typedef typename ColDefType::type RetType;
        return Col<0, Ts...>::template get<RetType>(integral_constant<int, ColDefType::value>());
    }
};

int main()
{
    Stmt<ColDef<'c1'  , int64_t>,
         ColDef<'c2'  , double >,
         ColDef<'test', string >,
         ColDef<'alfa', int64_t>> s;

    cout << "c1: "   << s.get<'c1'>()   << endl;
    cout << "c2: "   << s.get<'c2'>()   << endl;
    cout << "test: " << s.get<'test'>() << endl;
    cout << "alfa: " << s.get<'alfa'>() << endl;
    cout << endl;

    enum ColIds {x1, x2};
    Stmt<ColDef<x1, int64_t>,
         ColDef<x2, double >> s2;

    cout << "x1: "   << s2.get<x1>()      << endl;
    cout << "x2: "   << s2.get<x2>()      << endl;
    cout << "col1: " << s2.get_bycol<1>() << endl;
    cout << "col0: " << s2.get_bycol<0>() << endl;
    cout << endl;

    return 0;
}

