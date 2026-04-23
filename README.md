<p align="center">
  <a href="https://pypi.org/project/multimethods/">
    <img alt="PyPI version" src="https://img.shields.io/pypi/v/multimethods">
  </a>
  <a href="https://pypi.org/project/multimethods/">
    <img alt="PyPI Python versions" src="https://img.shields.io/pypi/pyversions/multimethods">
  </a>
  <a href="https://github.com/r0k3/multimethods/actions/workflows/ci.yml">
    <img alt="CI status" src="https://github.com/r0k3/multimethods/actions/workflows/ci.yml/badge.svg">
  </a>
  <a href="https://github.com/r0k3/multimethods/actions/workflows/pypi-publish.yml">
    <img alt="Publish status" src="https://github.com/r0k3/multimethods/actions/workflows/pypi-publish.yml/badge.svg">
  </a>
  <a href="LICENSE">
    <img alt="License" src="https://img.shields.io/pypi/l/multimethods">
  </a>
</p>

<h1 align="center">multimethods</h1>

<p align="center">
  <strong>Multiple dispatch for modern Python.</strong><br>
  Dispatch on what actually matters. Stay explicit under ambiguity. Keep methods feeling like methods.
</p>

<p align="center">
  <em>Fast exact-type hot paths, callable guards, keyword-aware calls, and class fallback that still behaves like Python.</em>
</p>

## The Pitch

Most Python dispatch tools stop at "pick an implementation based on the first argument".

That is useful, but a lot of real systems need more:

- a compiler that dispatches on `(node, backend)`
- a renderer that dispatches on `(value, target_format)`
- a pricing engine that dispatches on `(instrument, market)`
- a rules engine that dispatches on type first, then value constraints
- a class hierarchy where subclasses specialize a few cases without breaking normal fallback

That is where `multimethods` lives.

It gives you:

- multiple dispatch across more than one argument
- explicit ambiguity errors instead of silent guesswork
- callable guards instead of string `eval`
- keyword-call support through canonical signature binding
- `@staticmethod` and `@classmethod` support
- ordinary MRO fallback when a subclass only overloads part of the surface
- a fast exact-type cache for repeated hot-path calls

## Why It Feels Good

| You want | `multimethods` gives you |
| --- | --- |
| Dispatch on more than one input axis | native multi-argument dispatch |
| Refine a type case by value | `guard=` and `Annotated[..., where(...)]` |
| Predictable semantics | specificity rules, then guard rules, then explicit `priority=` |
| No hidden "best effort" guessing | `AmbiguousDispatchError` when signatures are incomparable |
| Method overloads that still behave like Python methods | bound methods, staticmethods, classmethods, and MRO fallback |
| Speed where it counts | exact winner cache for pure type-only hot paths |

## Installation

```bash
python -m pip install multimethods
```

Requires Python `3.12+`.

## A 30-Second Taste

This is the shape of the library:

```python
from multimethods import multimethod


@multimethod
def render(value: object, target: object) -> str:
    return "fallback"


@render.register
def _(value: int, target: str) -> str:
    return f"int:{value}:{target}"


@render.register
def _(value: str, target: str) -> str:
    return f"str:{value}:{target}"


assert render(3, "cli") == "int:3:cli"
assert render("hello", "cli") == "str:hello:cli"
assert render(3.14, "cli") == "fallback"
```

The mental model is simple:

1. write a normal function
2. register overloads
3. let runtime types decide which one wins
4. get an explicit error if the winner is genuinely unclear

## Examples

### 1. Dispatch On Two Real Axes

A lot of dispatch problems are naturally two-dimensional.

```python
from dataclasses import dataclass

from multimethods import multimethod


@dataclass
class JSON:
    pass


@dataclass
class CSV:
    pass


@dataclass
class User:
    name: str
    email: str


@dataclass
class Invoice:
    total: int
    currency: str


@multimethod
def dump(value: User, target: JSON) -> str:
    return f'{{"name": "{value.name}", "email": "{value.email}"}}'


@dump.register
def _(value: User, target: CSV) -> str:
    return f"{value.name},{value.email}"


@dump.register
def _(value: Invoice, target: JSON) -> str:
    return f'{{"total": {value.total}, "currency": "{value.currency}"}}'
```

That reads like the problem statement. No manual matrix dispatch table, no nested `if isinstance(...)` ladders.

### 2. Refine A Type Match With A Guard

Sometimes "type" is not enough. You want `int`, but only in a specific value range.

```python
from multimethods import multimethod


@multimethod(int, guard=lambda status: status == 429)
def retry_policy(status: int) -> str:
    return "retry-with-backoff"


@retry_policy.register(int, guard=lambda status: 500 <= status < 600)
def _(status: int) -> str:
    return "retry"


@retry_policy.register(int)
def _(status: int) -> str:
    return "do-not-retry"


assert retry_policy(429) == "retry-with-backoff"
assert retry_policy(503) == "retry"
assert retry_policy(404) == "do-not-retry"
```

This is value-aware dispatch without resorting to string expressions or a second ad hoc rule system.

### 3. Dispatch On A Subset Of Parameters

Sometimes only the first one or two arguments should participate in dispatch, while the rest are normal parameters.

```python
from multimethods import multimethod


@multimethod(int)
def parse(value, *, base=10):
    return value


@parse.register(str)
def _(value, *, base=10):
    return int(value, base=base)


assert parse(12) == 12
assert parse("1111", base=2) == 15
```

That gives you a clean way to say: "dispatch on the input shape, but keep configuration keyword-only".

### 4. Methods Still Behave Like Methods

Subclass-specific overloads should not destroy ordinary class fallback.

```python
from multimethods import multimethod


class BaseFormatter:
    def format(self, value):
        return str(value)


class ReportFormatter(BaseFormatter):
    @multimethod
    def format(self, value: int):
        return f"{value:,}"


formatter = ReportFormatter()

assert formatter.format(1250000) == "1,250,000"
assert formatter.format("raw") == "raw"
```

When no local overload matches, `multimethods` walks the class MRO and calls the next attribute with the same name. That makes partial specialization practical.

### 5. Per-Parameter Predicates With `Annotated`

For parameter-local rules, `where(...)` composes cleanly with `Annotated`.

```python
from typing import Annotated

from multimethods import multimethod, where


@multimethod
def bucket(x: Annotated[int, where(lambda x: x >= 0)]) -> str:
    return "non-negative"


@bucket.register
def _(x: int) -> str:
    return "negative"


assert bucket(10) == "non-negative"
assert bucket(-3) == "negative"
```

## Ambiguity Is A Feature, Not A Failure

Many dispatch systems quietly choose one candidate when two overloads are both plausible. That makes debugging miserable.

`multimethods` does not do that.

```python
from multimethods import AmbiguousDispatchError, multimethod


@multimethod
def collide(x: int, y: object):
    return "left"


@collide.register
def _(x: object, y: int):
    return "right"


try:
    collide(1, 1)
except AmbiguousDispatchError:
    print("good: the dispatcher refused to guess")
```

If you really want one side to win, make that decision explicit with `priority=`:

```python
@multimethod(priority=10)
def choose(x: int, y: object):
    return "left"


@choose.register(priority=1)
def _(x: object, y: int):
    return "right"
```

## Resolution Rules

Dispatch works in this order:

1. Find overloads whose type constraints match the runtime dispatch arguments.
2. Remove strictly less specific candidates.
3. Evaluate parameter guards and callable guards.
4. Prefer guarded candidates over unguarded candidates with identical type constraints.
5. Break remaining ties with `priority=`.
6. Raise `AmbiguousDispatchError` if multiple winners remain.
7. If this is a bound method call and no local overload matches, walk the class MRO and call the next attribute with the same name.

Keyword-only parameters and variadic parameters are allowed, but they never participate in dispatch.

## Supported Today

- plain classes
- abstract base classes
- `typing.Any`
- unions of supported classes, including `int | str`
- `typing.Annotated[T, where(...)]`
- annotation-based registration
- explicit decorator registration like `@multimethod(int, str)`

## What This Is Optimized For

`multimethods` is built for code that wants richer semantics than a minimal dispatch helper, while still caring about performance.

The implementation currently optimizes:

- repeated exact-type calls
- pure type-only overload sets
- positional hot paths that can bypass `inspect.Signature.bind`

On the included local benchmark, warmed exact-type calls are currently faster than the older `multimethod` / `multidispatch` implementations, roughly in the same band as `plum`, and still behind `multipledispatch` and especially `ovld` on raw microbenchmarks.

That is the honest position today:

- strong semantics
- practical ergonomics
- competitive hot-path speed
- still room to push harder on generated fast paths

You can run the benchmark yourself:

```bash
python benchmarks/compare_dispatch.py
```

## When To Reach For It

`multimethods` is a good fit when your codebase has:

- AST or IR transforms
- serializers and renderers with multiple target formats
- geometry, simulation, or collision-style double dispatch
- pricing or analytics logic driven by pairs of domain objects
- plugin systems where both the payload and backend matter
- business rules that are cleaner as overloads than as branching trees

If a plain `if` statement is enough, use a plain `if` statement.

If first-argument dispatch is enough, `functools.singledispatch` is still excellent.

This library is for the cases after that.

## Development

```bash
python -m pip install -e .[dev]
python -m ruff check .
python -m pytest -q
python -m build
python benchmarks/compare_dispatch.py
```
