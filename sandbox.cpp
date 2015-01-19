#include <fstream>
#include <iostream>
#include <string>
#include <type_traits>
#include <vector>

#define TL2(T0, T1) TypeList<T0, TypeList<T1, NullType> >
#define TL3(T0, T1, T2) TypeList<T0, TypeList<T1, TypeList<T2, NullType> > >

using namespace std;

struct NullType;

template <int I> struct Int2Type{};

template <typename H, typename T>
struct TypeList
{
    typedef H head;
    typedef T tail;
};


template <typename TL, int I> struct TypeAt;
template <typename H, typename T>
struct TypeAt<TypeList<H, T>, 0>
{
    typedef H type;
};
template <typename H, typename T, int I>
struct TypeAt<TypeList<H, T>, I>
{
    static_assert(!is_same<T, NullType>::value, "Invalid TypeAt index");
    typedef typename TypeAt<T, I - 1>::type type;
};

template <typename TL> struct Length;
template <> struct Length<NullType>
{
    enum { value = 0 };
};
template <typename H, typename T>
struct Length<TypeList<H, T>>
{
    enum { value = 1 + Length<T>::value };
};

template <int I, typename TL>
struct Col : Col<I + 1, typename TL::tail>
{
    template <typename R>
    R get(Int2Type<I>)
    {
        return R();
    }

    template <typename R, int J>
    R get(Int2Type<J> tag)
    {
        return Col<I + 1, typename TL::tail>::template get<R>(tag);
    }
};

template <int I> struct Col<I, NullType> {};

template <typename TL>
struct Stmt : Col<0, TL>
{
    template <int I>
    typename TypeAt<TL, I>::type get()
    {
        typedef typename TypeAt<TL, I>::type RetType;
        return Col<0, TL>::template get<RetType>(Int2Type<I>());
    }
};

int main()
{
    Stmt<TL3(int, string, double)> s;
    cout << "0: " << s.get<0>() << endl;
    cout << "1: " << s.get<1>() << endl;
    cout << "2: " << s.get<2>() << endl;
    return 0;
}

