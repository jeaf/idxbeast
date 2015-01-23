// todo: check that column tags are unique
#include <fstream>
#include <iostream>
#include <string>
#include <type_traits>
#include <vector>

#include "util.h"

using namespace std;
using namespace idxb::util;

//////////////////////////////////////////////////////////////////////////////
// SqliteTraits
//////////////////////////////////////////////////////////////////////////////
template <typename T, int I = 0> struct SqliteTraits
{
    static T col() {static_assert(!is_same<T, T>::value, "Unsupported type");}
    void bind(T)   {static_assert(!is_same<T, T>::value, "Unsupported type");}
};

template <int I> struct SqliteTraits<int64_t, I>
{
    static int64_t col() { return 3; };
    static void bind(int64_t val) { cout << "bind int64_t: " << val << endl; };
};

template <int I> struct SqliteTraits<double, I>
{
    static double col() { return 999.111; }
    static void bind(double val) { cout << "bind double: " << val << endl; };
};

template <int I> struct SqliteTraits<string, I>
{
    static string col() { return "abc"; }
    static void bind(string val) { cout << "bind string: " << val << endl; };
};

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
        return SqliteTraits<R, ColIdx>::col();
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
        SqliteTraits<T, I>::bind(val);
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
         BindSpec<int64_t>
        > s3;
    s3.bind<0>(123);
    //s3.bind<1>(888);
    //s3.bind<2>("delta");
    cout << s3.col<x1>() << endl;

    return 0;
}

