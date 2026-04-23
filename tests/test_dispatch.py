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
