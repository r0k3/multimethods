# Changelog

All notable changes to this project are documented in this file.

## [2.2.0] - 2026-10-11

### Added

- Python 3.14 and 3.15 support, with trove classifiers and CI coverage
- Publish workflow tests the built wheel on Python 3.12-3.15 before uploading

### Fixed

- Python 3.14+: an unquoted forward reference in the first overload no longer raises
  `NameError` at decoration time; it resolves on first call like later overloads
- Overloads registered after the first now use the exact-type cache when their parameter
  layout matches; previously differing annotations alone excluded them, making those calls
  roughly 8x slower. Calling such an overload with the wrong number of arguments now raises
  `TypeError`, as the first overload already did, instead of `NoMatchError`

## [2.1.0] - 2026-06-25

### Added

- PyPI project URLs (Repository, Issues, Changelog)
- README comparison with alternative dispatch libraries
- README documentation for `.dispatch()`, `.registry`, and `.copy()`
- README type checker integration guide using `typing.overload`
- Tests for introspection APIs, ABC dispatch, union ambiguity, and subclass overload inheritance

## [2.0.1] - 2026-06-01

Complete rewrite of the library for modern Python 3.12+.

### Highlights

- True multiple dispatch across two or more arguments
- Explicit `AmbiguousDispatchError` instead of silent guesswork
- Callable `guard=` predicates and `Annotated[..., where(...)]` per-parameter guards
- Keyword-aware dispatch through canonical signature binding
- `@staticmethod` and `@classmethod` support
- MRO fallback when a subclass overloads only part of a method surface
- Fast exact-type cache for repeated type-only hot paths
- Zero runtime dependencies; ships `py.typed` for type checker consumers

### About the legacy 1.0.0 release

PyPI also lists a `1.0.0` release from 2012 under the same package name. That
earlier version was a minimal prototype. Version 2.x is a ground-up redesign with
different APIs, semantics, and implementation. Treat 1.0.0 as historical only.