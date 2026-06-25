# Changelog

All notable changes to this project are documented in this file.

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