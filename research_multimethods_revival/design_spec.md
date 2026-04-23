# Multimethods Design Spec

## Goals

- Python 3.12+ only
- practical multi-argument dispatch
- explicit ambiguity behavior
- useful keyword-call support
- safe guard-based dispatch
- low overhead on repeated exact-type calls
- good introspection and method behavior

## Non-Goals For This Rewrite

- full generic-type dispatch for arbitrary `typing` constructs
- code generation
- static type-checker completeness for overload inference
- every advanced feature offered by `ovld` or `plum`

## Public API

### Decorator Forms

```python
@multimethod
def f(x: int, y: str): ...

@multimethod(int, str)
def f(x, y): ...

@multimethod(int, guard=lambda x: x > 0)
def f(x): ...

@f.register
def _(x: bool, y: str): ...

@f.register(int, str, priority=10)
def _(x, y): ...
```

### Additional Helpers

- `DispatchError`
- `NoMatchError`
- `AmbiguousDispatchError`
- `where(predicate)` for `typing.Annotated` guard metadata

## Dispatch Axes

- Dispatch uses ordered positional parameters after stripping leading `self` or `cls`.
- Keyword calls are supported by binding arguments to a canonical signature.
- Keyword-only parameters are allowed but never participate in dispatch.
- Variadic positional and variadic keyword parameters are allowed on implementations, but they do not participate in dispatch.

## Canonical Signature

- The first registered implementation defines the canonical public signature.
- Subsequent registrations must have the same number of dispatch parameters.
- The leading dispatch parameters must be structurally compatible with the canonical signature.
- For positional-or-keyword dispatch parameters, names should remain consistent. If they differ, keyword-call behavior is undefined and registration should fail fast.

## Supported Type Constraints

- plain classes
- abstract base classes
- `object`
- `typing.Any`
- PEP 604 unions of supported constraints
- tuples of types passed explicitly in decorator arguments
- `typing.Annotated[T, where(...)]`

Everything else should raise a clear registration error for now.

## Guards

- Guards are Python callables, not strings.
- A guard receives bound arguments using the implementation parameter names.
- Guarded methods are only considered after type applicability succeeds.
- For identical type constraints, a guarded method is treated as more specific than an unguarded method.
- If multiple guarded methods of equal specificity and priority match, dispatch is ambiguous.

## Resolution Algorithm

1. Normalize the call to canonical dispatch values.
2. Resolve type-compatible registrations for the runtime type tuple.
3. Remove strictly less specific registrations using pairwise partial ordering.
4. Evaluate guards on the remaining candidates.
5. Re-apply specificity with guard-awareness.
6. Break ties by explicit `priority`.
7. If multiple winners remain, raise `AmbiguousDispatchError`.
8. If none remain, attempt MRO fallback for bound methods.
9. If still none remain, raise `NoMatchError`.

## Specificity Rules

A registration `A` is more specific than registration `B` when:

- every dispatch constraint in `A` is at least as specific as the corresponding constraint in `B`, and
- at least one dispatch constraint in `A` is strictly more specific, and
- `A` is not less specific on any axis.

For unions, specificity is based on set inclusion after normalization.
For guards, `guarded > unguarded` when the underlying type constraints are identical.

## Method Fallback

If a multimethod is bound as an instance or class attribute and no local registration matches:

- walk the owner MRO
- find the next attribute with the same name
- invoke it normally

This preserves ordinary OOP fallback when a subclass only overloads a subset of cases.

## Caching

- Cache the reduced candidate set for exact runtime type tuples.
- Do not cache final winners across guards, since guards depend on values.
- Clear caches on every registration mutation.

## Documentation Priorities

- multimethod basics
- ambiguity and precedence
- guards
- methods and MRO fallback
- keyword-call rules
- performance notes and benchmark methodology
