# No `from __future__ import annotations`: these tests exercise PEP 649 lazy annotations.
import inspect
import sys

import pytest

from multimethods import NoMatchError, multimethod

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="unquoted forward references require PEP 649 lazy annotations",
)


def test_forward_reference_in_first_overload_resolves_on_call() -> None:
    @multimethod
    def describe(value: Later) -> str:
        return "later"

    @describe.register
    def _(value: int) -> str:
        return "int"

    class Later:
        pass

    assert describe(Later()) == "later"
    assert describe(1) == "int"


def test_self_referencing_method_overload() -> None:
    class Node:
        @multimethod
        def combine(self, other: Node) -> str:
            return "node"

        @combine.register
        def _(self, other: int) -> str:
            return "int"

    assert Node().combine(Node()) == "node"
    assert Node().combine(1) == "int"


def test_self_referencing_staticmethod_and_classmethod_overloads() -> None:
    class Shape:
        @staticmethod
        @multimethod
        def make(value: Shape) -> str:
            return "shape"

        @staticmethod
        @multimethod
        def make(value: int) -> str:
            return "int"

        @classmethod
        @multimethod
        def build(cls, value: Shape) -> str:
            return "shape"

        @classmethod
        @multimethod
        def build(cls, value: int) -> str:
            return "int"

    assert Shape.make(Shape()) == "shape"
    assert Shape.make(1) == "int"
    assert Shape.build(Shape()) == "shape"
    assert Shape.build(1) == "int"


def test_forward_reference_in_return_annotation() -> None:
    @multimethod
    def convert(value: int) -> Result:
        return Result()

    @convert.register
    def _(value: str) -> Result:
        return Result()

    class Result:
        pass

    assert isinstance(convert(1), Result)
    assert isinstance(convert("x"), Result)


def test_signature_and_registry_with_forward_reference() -> None:
    @multimethod
    def describe(value: Later) -> str:
        return "later"

    assert list(inspect.signature(describe).parameters) == ["value"]

    class Later:
        pass

    assert [registration.constraints[0].options for registration in describe.registry] == [(Later,)]


def test_unresolved_forward_reference_does_not_block_other_overloads() -> None:
    @multimethod
    def describe(value: Missing) -> str:
        return "missing"

    @describe.register
    def _(value: int) -> str:
        return "int"

    assert describe(1) == "int"
    with pytest.raises(NoMatchError):
        describe("x")
