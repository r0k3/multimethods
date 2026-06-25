from __future__ import annotations

import pytest

from multimethods import AmbiguousDispatchError, NoMatchError, multimethod


def test_annotation_based_dispatch_prefers_most_specific_match() -> None:
    @multimethod
    def render(x: object) -> str:
        return "object"

    @render.register
    def _(x: int) -> str:
        return "int"

    @render.register
    def _(x: bool) -> str:
        return "bool"

    assert render("x") == "object"
    assert render(1) == "int"
    assert render(True) == "bool"


def test_explicit_types_can_dispatch_on_a_subset_of_parameters() -> None:
    @multimethod(int)
    def add(x, y):
        return x + y

    @add.register(str)
    def _(x, y):
        return x + y.upper()

    assert add(1, 2) == 3
    assert add("a", "b") == "aB"


def test_keyword_calls_use_the_canonical_signature() -> None:
    @multimethod(int, int)
    def combine(x, y):
        return "int"

    @combine.register(str, str)
    def _(x, y):
        return "str"

    assert combine(x=1, y=2) == "int"
    assert combine("a", y="b") == "str"


def test_bind_failure_reveals_less_specific_overload() -> None:
    @multimethod(int)
    def pick(x, *, flag):
        return "int-with-flag"

    @pick.register(object)
    def _(x):
        return "object"

    assert pick(1, flag=True) == "int-with-flag"
    assert pick(1) == "object"
    assert pick("x") == "object"


def test_no_match_raises_specific_error() -> None:
    @multimethod(int)
    def only_int(x):
        return x

    with pytest.raises(NoMatchError):
        only_int("x")


def test_ambiguity_raises_with_incomparable_signatures() -> None:
    @multimethod
    def collide(x: int, y: object) -> str:
        return "left"

    @collide.register
    def _(x: object, y: int) -> str:
        return "right"

    with pytest.raises(AmbiguousDispatchError):
        collide(1, 1)


def test_priority_breaks_ties_after_specificity_reduction() -> None:
    @multimethod(priority=10)
    def select(x: int, y: object) -> str:
        return "left"

    @select.register(priority=1)
    def _(x: object, y: int) -> str:
        return "right"

    assert select(1, 1) == "left"


def test_repeated_same_name_declarations_share_the_dispatcher() -> None:
    @multimethod(int)
    def same_name(x):
        return "int"

    @multimethod(str)
    def same_name(x):
        return "str"

    assert same_name(1) == "int"
    assert same_name("x") == "str"


def test_cache_is_invalidated_when_new_overloads_are_registered() -> None:
    @multimethod
    def classify(x: int) -> str:
        return "int"

    assert classify(True) == "int"

    @classify.register
    def _(x: bool) -> str:
        return "bool"

    assert classify(True) == "bool"


def test_dispatch_returns_winning_callable() -> None:
    @multimethod
    def resolve(x: object) -> str:
        return "object"

    @resolve.register
    def _(x: int) -> str:
        return "int"

    winner = resolve.dispatch(1)
    assert callable(winner)
    assert winner(1) == "int"
    assert resolve(1) == "int"


def test_registry_exposes_registered_overloads() -> None:
    @multimethod
    def collect(x: int) -> str:
        return "int"

    @collect.register
    def _(x: str) -> str:
        return "str"

    registry = collect.registry
    assert len(registry) == 2
    assert all(hasattr(entry, "constraints") for entry in registry)
    assert collect.dispatch(1) is registry[0].function
    assert collect("x") == "str"


def test_copy_clones_dispatcher_independently() -> None:
    @multimethod
    def duplicate(x: int) -> str:
        return "int"

    @duplicate.register
    def _(x: str) -> str:
        return "str"

    clone = duplicate.copy()
    assert clone is not duplicate
    assert len(clone.registry) == len(duplicate.registry)
    assert clone(1) == duplicate(1)
    assert clone("x") == duplicate("x")


def test_abc_dispatch_prefers_subclass_overload() -> None:
    from abc import ABC, abstractmethod

    class Shape(ABC):
        @abstractmethod
        def draw(self) -> None:
            raise NotImplementedError

    class Circle(Shape):
        def draw(self) -> None:
            return None

    class Rectangle(Shape):
        def draw(self) -> None:
            return None

    @multimethod
    def area(shape: Shape) -> float:
        return 0.0

    @area.register
    def _(shape: Circle) -> float:
        return 3.14

    assert area(Circle()) == 3.14
    assert area(Rectangle()) == 0.0


def test_union_ambiguity_raises_for_incomparable_signatures() -> None:
    from numbers import Number

    @multimethod
    def collide(x: int | Number, y: int) -> str:
        return "first"

    @collide.register
    def _(x: int, y: Number) -> str:
        return "second"

    with pytest.raises(AmbiguousDispatchError):
        collide(1, 1)


def test_subclass_can_add_overloads_and_inherit_parent_matches() -> None:
    class Parent:
        @multimethod
        def fn(self, value: int) -> str:
            return "parent-int"

    class Child(Parent):
        @multimethod
        def fn(self, value: bool) -> str:
            return "child-bool"

    child = Child()

    assert child.fn(True) == "child-bool"
    assert child.fn(1) == "parent-int"
