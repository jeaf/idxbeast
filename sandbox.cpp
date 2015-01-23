// todo: check that column tags are unique
// todo: create traits class for Sqlite (e.g., SqliteTraits) to keeps pointers
//       to functions for each type, e.g., sqlite_column_int, sqlite_bind_int,
//       etc.
#include <fstream>
#include <iostream>
#include <string>
#include <type_traits>
#include <vector>

using namespace std;

//////////////////////////////////////////////////////////////////////////////
// TypeAt
//////////////////////////////////////////////////////////////////////////////
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

//////////////////////////////////////////////////////////////////////////////
// SqliteCol
//////////////////////////////////////////////////////////////////////////////
template <int I, typename T>
struct SqliteCol { static_assert(I < 0, "Unsupported type"); };
template <int I>
struct SqliteCol<I, int64_t> { static int64_t get() { return 3; } };
template <int I>
struct SqliteCol<I, double> { static double get() { return 999.111; } };
template <int I>
struct SqliteCol<I, string> { static string get() { return "abc"; } };

//////////////////////////////////////////////////////////////////////////////
// ColDef
//////////////////////////////////////////////////////////////////////////////
template <typename Tag, typename Type>
struct ColDef
{
    typedef Tag  tag;
    typedef Type type;
};

template <typename Tag, typename... Ts> struct ColDefLookup;
template <typename Tag, typename H, typename... Ts>
struct ColDefLookup<Tag, H, Ts...>
{
    typedef typename
        conditional<is_same<Tag, typename H::tag>::value,
                    H,
                    typename ColDefLookup<Tag, Ts...>::result
                   >::type result;
};
template <typename Tag> struct ColDefLookup<Tag>
{
    typedef struct ErrorColDefNotFound result;
};

//////////////////////////////////////////////////////////////////////////////
// Col
//////////////////////////////////////////////////////////////////////////////
template <int ColIdx, typename... Ts> struct Col{};
template <int ColIdx, typename H, typename... Ts>
struct Col<ColIdx, H, Ts...> : Col<ColIdx + 1, Ts...>
{
    template <typename R>
    R col(typename H::tag*)
    {
        return SqliteCol<ColIdx, R>::get();
    }

    template <typename R, typename T>
    R col(T* tag)
    {
        return Col<ColIdx + 1, Ts...>::template col<R>(tag);
    }
};

//////////////////////////////////////////////////////////////////////////////
// ColSpec
//////////////////////////////////////////////////////////////////////////////
template <typename... Ts>
struct ColSpec : Col<0, Ts...>
{
    template <typename ColTag>
    typename ColDefLookup<ColTag, Ts...>::result::type col()
    {
        typedef typename ColDefLookup<ColTag, Ts...>::result::type RetType;
        return Col<0, Ts...>::template col<RetType>(static_cast<ColTag*>(nullptr));
    }

    template <int ColIdx>
    typename TypeAt<ColIdx, Ts...>::type::type col()
    {
        typedef typename TypeAt<ColIdx, Ts...>::type ColDefType;
        typedef typename ColDefType::type RetType;
        return Col<0, Ts...>::template col<RetType>(static_cast<typename ColDefType::tag*>(nullptr));
    }
};

//////////////////////////////////////////////////////////////////////////////
// Bind
//////////////////////////////////////////////////////////////////////////////
template <int I, typename... Ts> struct Bind{};
template <int I, typename H, typename... Ts>
struct Bind<I, H, Ts...> : Bind<I + 1, Ts...>
{
    template <typename T>
    void bind(integral_constant<int, I>, T val)
    {
        cout << "bind: " << val << endl;
        //return SqliteCol<ColIdx, R>::get();
    }

    template <typename T, int Idx>
    void bind(integral_constant<int, Idx> col_idx, T val)
    {
        Bind<I + 1, Ts...>::template bind<T>(col_idx, val);
    }
};

//////////////////////////////////////////////////////////////////////////////
// BindSpec
//////////////////////////////////////////////////////////////////////////////
template <typename... Ts>
struct BindSpec : Bind<0, Ts...>
{
    template <int I>
    void bind(typename TypeAt<I, Ts...>::type val)
    {
        Bind<0, Ts...>::template bind<typename TypeAt<I, Ts...>::type>(
            integral_constant<int, I>(), val);
    }
};

//////////////////////////////////////////////////////////////////////////////
// Stmt
//////////////////////////////////////////////////////////////////////////////
struct EmptyType {};
template <typename Spec1 = EmptyType, typename Spec2 = EmptyType>
struct Stmt : Spec1, Spec2
{
};

//////////////////////////////////////////////////////////////////////////////
// main
//////////////////////////////////////////////////////////////////////////////
int main()
{
    struct c1; struct c2; struct test; struct alfa; struct x1; struct x2;

    Stmt<ColSpec<ColDef<c1  , int64_t>,
                 ColDef<c2  , double >,
                 ColDef<test, string >,
                 ColDef<alfa, int64_t>>> s;

    cout << "c1: "   << s.col<c1>()   << endl;
    cout << "c2: "   << s.col<c2>()   << endl;
    cout << "test: " << s.col<test>() << endl;
    cout << "alfa: " << s.col<alfa>() << endl;
    cout << endl;

    Stmt<ColSpec<ColDef<x1, int64_t>,
                 ColDef<x2, double >>> s2;

    cout << "x1: "   << s2.col<x1>()      << endl;
    cout << "x2: "   << s2.col<x2>()      << endl;
    cout << "col1: " << s2.col<1>() << endl;
    cout << "col0: " << s2.col<0>() << endl;
    cout << endl;

    Stmt<ColSpec <ColDef<x1, int64_t>>,
         BindSpec<double, int>
        > s3;
    s3.bind<0>(123.456);
    s3.bind<1>(888);
    cout << s3.col<x1>() << endl;

    return 0;
}

