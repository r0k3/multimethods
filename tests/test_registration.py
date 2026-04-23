from __future__ import annotations

import pytest

from multimethods import RegistrationError, multimethod


def test_guard_must_be_callable() -> None:
    with pytest.raises(TypeError):

        @multimethod(int, guard="x > 0")  # type: ignore[arg-type]
        def guarded(x):
            return x


def test_missing_dispatch_annotation_is_rejected() -> None:
    with pytest.raises(RegistrationError):

        @multimethod
        def invalid(x):
            return x


def test_dispatch_parameter_names_must_match_for_keyword_support() -> None:
    @multimethod(int, int)
    def merge(x, y):
        return "xy"

    with pytest.raises(RegistrationError):

        @merge.register(str, str)
        def _(left, right):
            return "lr"


def test_forward_reference_annotations_resolve_lazily() -> None:
    @multimethod
    def identify(value: "FutureType"):
        return "future"

    class FutureType:
        pass

    assert identify(FutureType()) == "future"


def test_union_annotations_are_supported() -> None:
    @multimethod
    def stringify(value: int | str) -> str:
        return str(value)

    assert stringify(1) == "1"
    assert stringify("x") == "x"
