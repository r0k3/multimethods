from __future__ import annotations

import inspect

from multimethods import multimethod


def test_instance_method_dispatch_and_mro_fallback() -> None:
    class Base:
        def convert(self, value):
            return f"base:{value}"

    class Derived(Base):
        @multimethod
        def convert(self, value: int):
            return f"int:{value}"

    instance = Derived()

    assert instance.convert(3) == "int:3"
    assert instance.convert("x") == "base:x"


def test_unbound_method_call_works_with_explicit_self() -> None:
    class Example:
        @multimethod
        def scale(self, value: int):
            return value * 2

    assert Example.scale(Example(), 4) == 8


def test_staticmethod_supports_repeated_same_name_registration() -> None:
    class Example:
        @staticmethod
        @multimethod
        def render(value: int):
            return "int"

        @staticmethod
        @multimethod
        def render(value: str):
            return "str"

    assert Example.render(1) == "int"
    assert Example.render("x") == "str"


def test_classmethod_supports_repeated_same_name_registration() -> None:
    class Example:
        label = "example"

        @classmethod
        @multimethod
        def build(cls, value: int):
            return f"{cls.label}:int"

        @classmethod
        @multimethod
        def build(cls, value: str):
            return f"{cls.label}:str"

    assert Example.build(1) == "example:int"
    assert Example.build("x") == "example:str"


def test_bound_signature_hides_self() -> None:
    class Example:
        @multimethod
        def combine(self, left: int, right: int):
            return left + right

    signature = inspect.signature(Example().combine)
    assert tuple(signature.parameters) == ("left", "right")
