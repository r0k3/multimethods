# Multimethods Revival Research Plan

## Main Question

What should a modern Python 3.12+ multi-dispatch library provide to be genuinely useful in 2026, competitive with the best existing libraries, and still fast enough to justify its existence?

## Subtopics

### 1. Existing Dispatch Libraries

Investigate the current capabilities, semantics, and stated tradeoffs of:

- `functools.singledispatch` / `singledispatchmethod`
- `multimethod`
- `multipledispatch`
- `plum-dispatch`
- other notable predicate or overload-oriented libraries if relevant

Expected output:

- feature comparison
- ambiguity behavior
- keyword argument support
- method/classmethod/staticmethod behavior
- annotation support
- performance-related design choices

### 2. Target Semantics

Define explicit semantics for this rewrite:

- registration model
- dispatch scope
- precedence rules
- ambiguity errors
- conditional dispatch semantics
- caching behavior
- introspection and debugging surface

Expected output:

- a concise design spec that can drive implementation and tests

### 3. Practical Use Cases

Identify real use cases where modern Python users would choose multi-dispatch over:

- plain `if`/`match`
- `singledispatch`
- ad hoc overload helpers

Expected output:

- representative examples for docs and tests
- constraints that affect API design

### 4. Packaging and Release Readiness

Define what a modern publishable library requires:

- `pyproject.toml`
- typed package
- pytest coverage
- benchmark hooks
- documentation examples

Expected output:

- packaging and QA checklist

## Synthesis

Use the research to produce:

1. a clear public API
2. a precise dispatch resolution algorithm
3. a performant implementation strategy
4. a comprehensive pytest suite
5. publishable packaging and documentation
