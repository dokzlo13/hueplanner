import pytest

from hueplanner.ioc import IOC, Factory, Singleton, SingletonFactory


def test_singleton_declaration():
    ioc = IOC()

    class Foo:
        def __init__(self, a: int) -> None:
            self.a = a

    foo_instance = Foo(1)
    ioc.declare(Foo, Singleton(foo_instance))  # Declaring as Singleton

    resolved_foo = ioc.resolve(Foo)
    assert resolved_foo is foo_instance
    assert ioc.resolve(Foo) is ioc.resolve(Foo)
    assert resolved_foo.a == 1


def test_factory_declaration():
    ioc = IOC()

    class Foo:
        def __init__(self, a: int) -> None:
            self.a = a

    ioc.declare(Foo, Factory(lambda: Foo(2)))  # Declaring as Factory

    resolved_foo = ioc.resolve(Foo)
    assert resolved_foo.a == 2
    assert resolved_foo is not ioc.resolve(Foo)  # Factory should return a new instance


def test_factory_with_injection():
    ioc = IOC()

    class Foo:
        def __init__(self, a: int) -> None:
            self.a = a

    class Bar:
        def __init__(self, foo: Foo) -> None:
            self.foo = foo

    ioc.declare(Foo, lambda: Foo(3))  # Declaring Foo as Factory
    ioc.declare(Bar, Factory(Bar, allow_inject=True))  # Declaring Bar with automatic injection

    class FooBar:
        def __init__(self, foo: Foo, bar: Bar) -> None:
            self.foo = foo
            self.bar = bar

    resolved_foobar = ioc.make(FooBar)
    assert isinstance(resolved_foobar, FooBar)
    assert resolved_foobar.foo.a == 3
    assert resolved_foobar.bar.foo.a == 3


def test_optional_none_injection():
    ioc = IOC()

    class Foo:
        def __init__(self, a: int) -> None:
            self.a = a

    class Bar:
        def __init__(self, foo: Foo | None) -> None:
            self.foo = foo

    resolved_foobar = ioc.make(Bar)
    assert isinstance(resolved_foobar, Bar)
    assert resolved_foobar.foo is None


def test_optional_value_injection():
    ioc = IOC()

    class Foo:
        def __init__(self, a: int) -> None:
            self.a = a

    class Bar:
        def __init__(self, foo: Foo | None) -> None:
            self.foo = foo

    ioc.declare(Foo, Foo(a=1))

    resolved_foobar = ioc.make(Bar)
    assert isinstance(resolved_foobar, Bar)
    assert getattr(resolved_foobar, "foo").a == 1


def test_error_handling():
    ioc = IOC()

    class Foo:
        def __init__(self, a: int) -> None:
            self.a = a

    # No declaration for Bar
    class Bar:
        def __init__(self, foo: Foo) -> None:
            self.foo = foo

    with pytest.raises(Exception) as excinfo:
        ioc.make(Bar)
    assert "cannot resolve 'foo'" in str(excinfo.value)


def test_auto_declare():

    class Foo:
        def __init__(self, a: int) -> None:
            self.a = a

    ioc = IOC()
    ioc.auto_declare(Foo(4))  # Auto-declare as Singleton
    resolved_foo = ioc.resolve(Foo)
    assert resolved_foo.a == 4

    def make_foo() -> Foo:
        return Foo(5)

    ioc = IOC()
    ioc.auto_declare(make_foo)  # Auto-declare as function Factory
    resolved_foo = ioc.resolve(Foo)
    assert resolved_foo.a == 5

    class Bar:
        def __init__(self) -> None:
            self.a = 42

    ioc = IOC()
    ioc.auto_declare(Bar)  # Auto-declare as class Factory
    resolved_bar = ioc.resolve(Bar)
    assert resolved_bar.a == 42


def test_injection_decorator():
    ioc = IOC()

    class Foo:
        def __init__(self, a: int) -> None:
            self.a = a

    class Bar:
        def __init__(self, foo: Foo) -> None:
            self.foo = foo

    def make_bar(foo: Foo) -> Bar:
        return Bar(foo)

    ioc.declare(Foo, lambda: Foo(6))  # Declaring Foo as Factory
    ioc.declare(Bar, Factory(make_bar, allow_inject=True))  # Declaring Bar with automatic injection

    @ioc.inject
    def baz(foo: Foo, bar: Bar):
        return foo.a, bar.foo.a

    result = baz()
    assert result == (6, 6)


# def test_circular_dependency_handling():


#     class Foo:
#         def __init__(self, baz: "Baz") -> None:
#             self.baz = baz

#     class Bar:
#         def __init__(self, foo: "Foo") -> None:
#             self.foo = foo

#     class Baz:
#         def __init__(self, bar: "Bar") -> None:
#             self.bar = bar

#     ioc = IOC()
#     ioc.declare(Foo, Factory(Foo, allow_inject=True))
#     ioc.declare(Bar, Factory(Bar, allow_inject=True))
#     ioc.declare(Baz, Factory(Baz, allow_inject=True))

#     ioc.resolve(Baz)

#     # with pytest.raises(Exception) as excinfo:
#     #     ioc.make(brr)
#     # assert "recursive" in str(excinfo.value)


# def test_partial_initialization():
#     ioc = IOC()

#     class Foo:
#         def __init__(self, a: int) -> None:
#             self.a = a

#     class Bar:
#         def __init__(self, foo: Foo) -> None:
#             self.foo = foo

#     ioc.declare(Foo, Foo(7))  # Declaring Foo as Factory
#     ioc.declare(Bar, Bar)  # Declaring Bar with automatic injection

#     @ioc.inject
#     def baz(foo: Foo, bar: Bar, extra: int):
#         return foo.a + bar.foo.a + extra

#     partial_baz = ioc.make_partial(baz)
#     print(partial_baz)
#     return
#     result = partial_baz(extra=1)
#     assert result == 15  # 7 (Foo.a) + 7 (Bar.foo.a) + 1 (extra)
