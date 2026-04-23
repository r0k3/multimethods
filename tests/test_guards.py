from __future__ import annotations

from typing import Annotated

import pytest

from multimethods import AmbiguousDispatchError, multimethod, where


def test_guarded_overload_beats_unguarded_overload_with_same_types() -> None:
    @multimethod(int, guard=lambda x: x > 0)
    def classify(x):
        return "positive"

    @classify.register(int)
    def _(x):
        return "int"

    assert classify(3) == "positive"
    assert classify(-1) == "int"


def test_guard_can_accept_a_subset_of_bound_arguments() -> None:
    @multimethod(int, int, guard=lambda y: y > 0)
    def quadrant(x, y):
        return "upper"

    @quadrant.register(int, int)
    def _(x, y):
        return "lower-or-axis"

    assert quadrant(1, 2) == "upper"
    assert quadrant(1, 0) == "lower-or-axis"


def test_annotated_where_guards_work_per_parameter() -> None:
    @multimethod
    def magnitude(x: Annotated[int, where(lambda x: x >= 0)]) -> str:
        return "non-negative"

    @magnitude.register
    def _(x: int) -> str:
        return "negative"

    assert magnitude(0) == "non-negative"
    assert magnitude(-1) == "negative"


def test_multiple_matching_guards_are_ambiguous() -> None:
    @multimethod(int, guard=lambda x: x > 0)
    def overlap(x):
        return "positive"

    @overlap.register(int, guard=lambda x: x % 2 == 0)
    def _(x):
        return "even"

    with pytest.raises(AmbiguousDispatchError):
        overlap(2)
