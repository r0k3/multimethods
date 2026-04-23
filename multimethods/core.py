from __future__ import annotations

import functools
import inspect
import typing
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import UnionType
from typing import Annotated, Any, get_args, get_origin, get_type_hints

from .errors import AmbiguousDispatchError, NoMatchError, RegistrationError

Guard = Callable[..., bool]
Decorator = Callable[[Callable[..., Any] | staticmethod | classmethod], Any]

_EMPTY = inspect.Signature.empty
_DISPATCH_KINDS = {
    inspect.Parameter.POSITIONAL_ONLY,
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
}
_METHOD_NAMES = {"self", "cls"}


@dataclass(frozen=True, slots=True)
class Where:
    predicate: Callable[[Any], bool]


def where(predicate: Callable[[Any], bool]) -> Where:
    if not callable(predicate):
        raise TypeError("where() expects a callable predicate")
    return Where(predicate)


@dataclass(frozen=True, slots=True)
class TypeConstraint:
    options: tuple[type, ...] | None = None

    def matches(self, actual_type: type) -> bool:
        if self.options is None:
            return True
        return any(issubclass(actual_type, option) for option in self.options)

    def implies(self, other: "TypeConstraint") -> bool:
        if other.options is None:
            return True
        if self.options is None:
            return False
        return all(
            any(issubclass(option, other_option) for other_option in other.options)
            for option in self.options
        )

    def render(self) -> str:
        if self.options is None:
            return "Any"
        return " | ".join(option.__name__ for option in self.options)


@dataclass(frozen=True, slots=True)
class ParameterGuard:
    parameter_name: str
    predicate: Callable[[Any], bool]

    def matches(self, bound: inspect.BoundArguments) -> bool:
        return bool(self.predicate(bound.arguments[self.parameter_name]))


@dataclass(slots=True)
class PendingRegistration:
    function: Callable[..., Any]
    explicit_types: tuple[Any, ...] | None
    guard: Guard | None
    priority: int
    same_name_return: bool
    localns: dict[str, Any] | None


@dataclass(slots=True)
class Registration:
    function: Callable[..., Any]
    signature: inspect.Signature
    constraints: tuple[TypeConstraint, ...]
    parameter_guards: tuple[ParameterGuard, ...]
    guard: Guard | None
    priority: int
    order: int
    needs_binding: bool

    def type_matches(self, actual_types: tuple[type, ...]) -> bool:
        return all(
            constraint.matches(actual_type)
            for constraint, actual_type in zip(self.constraints, actual_types, strict=True)
        )

    def more_specific_than(self, other: "Registration") -> bool:
        same_or_better = all(
            current.implies(previous)
            for current, previous in zip(self.constraints, other.constraints, strict=True)
        )
        strictly_better = any(
            current.implies(previous) and not previous.implies(current)
            for current, previous in zip(self.constraints, other.constraints, strict=True)
        )
        if same_or_better and strictly_better:
            return True
        if self.constraints == other.constraints:
            return bool(self.has_guard and not other.has_guard)
        return False

    @property
    def has_guard(self) -> bool:
        return self.guard is not None or bool(self.parameter_guards)

    def describe(self) -> str:
        rendered = ", ".join(constraint.render() for constraint in self.constraints)
        suffix = []
        if self.parameter_guards:
            suffix.append("parameter guard")
        if self.guard is not None:
            suffix.append("guard")
        if self.priority:
            suffix.append(f"priority={self.priority}")
        details = f" [{' '.join(suffix)}]" if suffix else ""
        return f"{self.function.__qualname__}({rendered}){details}"


@dataclass(slots=True)
class BoundMultimethod:
    dispatcher: "MultiMethod"
    bound_target: object
    owner: type

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        full_args = (self.bound_target, *args)
        exact = self.dispatcher._fast_exact_lookup(full_args, kwargs)
        if exact is not None:
            return exact.function(*full_args, **kwargs)
        return self.dispatcher._invoke(
            full_args,
            kwargs,
            bound_target=self.bound_target,
            owner=self.owner,
        )

    def dispatch(self, *args: Any, **kwargs: Any) -> Callable[..., Any]:
        full_args = (self.bound_target, *args)
        exact = self.dispatcher._fast_exact_lookup(full_args, kwargs)
        if exact is not None:
            return exact.function
        registration = self.dispatcher._resolve(
            full_args,
            kwargs,
            bound_target=self.bound_target,
            owner=self.owner,
        )
        return registration.function

    @property
    def __wrapped__(self) -> Callable[..., Any]:
        return self.dispatcher.__wrapped__

    @property
    def __signature__(self) -> inspect.Signature:
        if not self.dispatcher._drops_leading_argument:
            return self.dispatcher.__signature__
        parameters = list(self.dispatcher.__signature__.parameters.values())[1:]
        return self.dispatcher.__signature__.replace(parameters=parameters)

    def __getattr__(self, item: str) -> Any:
        return getattr(self.dispatcher, item)


class MultiMethod:
    __slots__ = (
        "__dict__",
        "__wrapped__",
        "_cache",
        "_can_slice_dispatch",
        "_canonical_dispatch_names",
        "_canonical_dispatch_params",
        "_canonical_signature",
        "_dispatch_offset",
        "_drops_leading_argument",
        "_exact_cache",
        "_name",
        "_order",
        "_owner",
        "_pending",
        "_registrations",
    )

    def __init__(
        self,
        function: Callable[..., Any],
        explicit_types: tuple[Any, ...] | None,
        guard: Guard | None,
        priority: int,
        localns: dict[str, Any] | None,
    ) -> None:
        functools.update_wrapper(self, function)
        self.__wrapped__ = function
        self._name = function.__name__
        self._owner: type | None = None
        self._order = 0
        self._registrations: list[Registration] = []
        self._pending: list[PendingRegistration] = []
        self._cache: dict[tuple[type, ...], tuple[Registration, ...]] = {}
        self._exact_cache: dict[tuple[type, ...], Registration] = {}

        self._canonical_signature = inspect.signature(function)
        self._drops_leading_argument = _drops_leading_argument(self._canonical_signature)
        self._canonical_dispatch_params = _select_dispatch_parameters(
            self._canonical_signature,
            explicit_count=len(explicit_types) if explicit_types is not None else None,
            drop_leading=self._drops_leading_argument,
        )
        self._canonical_dispatch_names = tuple(
            parameter.name for parameter in self._canonical_dispatch_params
        )
        self._dispatch_offset = 1 if self._drops_leading_argument else 0
        self._can_slice_dispatch = not _has_non_dispatch_tail(
            self._canonical_signature,
            dispatch_count=len(self._canonical_dispatch_params),
            drop_leading=self._drops_leading_argument,
        )

        self._add_registration(
            function=function,
            explicit_types=explicit_types,
            guard=guard,
            priority=priority,
            same_name_return=True,
            localns=localns,
        )

    def __set_name__(self, owner: type, name: str) -> None:
        self._owner = owner
        self._name = name

    def __get__(self, instance: object, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return BoundMultimethod(self, instance, owner or type(instance))

    @property
    def __signature__(self) -> inspect.Signature:
        return self._canonical_signature

    @property
    def registry(self) -> tuple[Registration, ...]:
        self._resolve_pending()
        return tuple(self._registrations)

    def copy(self) -> "MultiMethod":
        self._resolve_pending()
        clone = object.__new__(type(self))
        clone.__dict__ = dict(self.__dict__)
        clone.__wrapped__ = self.__wrapped__
        clone._cache = {}
        clone._can_slice_dispatch = self._can_slice_dispatch
        clone._canonical_dispatch_names = self._canonical_dispatch_names
        clone._canonical_dispatch_params = self._canonical_dispatch_params
        clone._canonical_signature = self._canonical_signature
        clone._dispatch_offset = self._dispatch_offset
        clone._drops_leading_argument = self._drops_leading_argument
        clone._exact_cache = {}
        clone._name = self._name
        clone._order = self._order
        clone._owner = self._owner
        clone._pending = list(self._pending)
        clone._registrations = list(self._registrations)
        return clone

    def register(
        self,
        *types_or_function: Any,
        guard: Guard | None = None,
        priority: int = 0,
    ) -> Decorator | "MultiMethod" | Callable[..., Any]:
        if len(types_or_function) == 1 and _is_function_like(types_or_function[0]):
            function = typing.cast(
                Callable[..., Any] | staticmethod | classmethod,
                types_or_function[0],
            )
            return self._register_decorated(function, None, guard=guard, priority=priority)

        explicit_types = tuple(types_or_function)

        def decorator(function: Callable[..., Any] | staticmethod | classmethod) -> Any:
            return self._register_decorated(
                function,
                explicit_types,
                guard=guard,
                priority=priority,
            )

        return decorator

    def dispatch(self, *args: Any, **kwargs: Any) -> Callable[..., Any]:
        exact = self._fast_exact_lookup(args, kwargs)
        if exact is not None:
            return exact.function
        registration = self._resolve(args, kwargs, bound_target=None, owner=None)
        return registration.function

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        exact = self._fast_exact_lookup(args, kwargs)
        if exact is not None:
            return exact.function(*args, **kwargs)
        return self._invoke(args, kwargs, bound_target=None, owner=None)

    def _invoke(
        self,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
        *,
        bound_target: object | None,
        owner: type | None,
    ) -> Any:
        registration = self._resolve(args, kwargs, bound_target=bound_target, owner=owner)
        if isinstance(registration, _FunctionRegistration):
            return registration.function(*args[registration.skip_leading :], **kwargs)
        return registration.function(*args, **kwargs)

    def _resolve(
        self,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
        *,
        bound_target: object | None,
        owner: type | None,
    ) -> Registration | _FunctionRegistration:
        self._resolve_pending()
        dispatch_values = self._extract_dispatch_values(args, kwargs)
        actual_types = tuple(type(value) for value in dispatch_values)
        type_candidates = self._cache.get(actual_types)
        if not kwargs:
            winner = self._exact_cache.get(actual_types)
            if winner is not None:
                return winner
        if type_candidates is None:
            type_candidates = tuple(
                registration
                for registration in self._registrations
                if registration.type_matches(actual_types)
            )
            self._cache[actual_types] = type_candidates
        if (
            not kwargs
            and type_candidates
            and all(
                not registration.needs_binding and not registration.has_guard
                for registration in type_candidates
            )
        ):
            winners = _apply_priority(_reduce_specificity(type_candidates))
            if len(winners) == 1:
                self._exact_cache[actual_types] = winners[0]
                return winners[0]

        applicable: list[tuple[Registration, inspect.BoundArguments | None]] = []
        for registration in type_candidates:
            bound = None
            if registration.needs_binding or kwargs:
                try:
                    bound = registration.signature.bind(*args, **kwargs)
                    bound.apply_defaults()
                except TypeError:
                    continue
            if not self._guards_match(registration, bound, args, kwargs):
                continue
            applicable.append((registration, bound))

        if not applicable:
            fallback = self._resolve_mro_fallback(
                args,
                kwargs,
                bound_target=bound_target,
                owner=owner,
            )
            if fallback is not None:
                return fallback
            raise NoMatchError(self._name, "no matching overload", actual_types)

        winners = _reduce_specificity([registration for registration, _ in applicable])
        winners = _apply_priority(winners)
        if len(winners) > 1:
            raise AmbiguousDispatchError(
                self._name,
                "ambiguous dispatch",
                actual_types,
                tuple(candidate.describe() for candidate in winners),
            )
        return winners[0]

    def _extract_dispatch_values(
        self,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> tuple[Any, ...]:
        if (
            not kwargs
            and self._can_slice_dispatch
            and len(args) >= self._dispatch_offset + len(self._canonical_dispatch_params)
        ):
            start = self._dispatch_offset
            stop = start + len(self._canonical_dispatch_params)
            return tuple(args[start:stop])

        bound = self._canonical_signature.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        missing = [name for name in self._canonical_dispatch_names if name not in bound.arguments]
        if missing:
            self._canonical_signature.bind(*args, **kwargs)
        return tuple(bound.arguments[name] for name in self._canonical_dispatch_names)

    def _guards_match(
        self,
        registration: Registration,
        bound: inspect.BoundArguments | None,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> bool:
        if not registration.has_guard:
            return True
        if bound is None:
            bound = registration.signature.bind(*args, **kwargs)
            bound.apply_defaults()

        for parameter_guard in registration.parameter_guards:
            if not parameter_guard.matches(bound):
                return False
        if registration.guard is None:
            return True
        return bool(_invoke_guard(registration.guard, bound))

    def _fast_exact_lookup(
        self,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> Registration | None:
        if kwargs or self._pending or not self._can_slice_dispatch:
            return None
        required = self._dispatch_offset + len(self._canonical_dispatch_params)
        if len(args) < required:
            return None
        dispatch_args = args[self._dispatch_offset : required]
        actual_types = tuple(map(type, dispatch_args))
        return self._exact_cache.get(actual_types)

    def _resolve_mro_fallback(
        self,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
        *,
        bound_target: object | None,
        owner: type | None,
    ) -> _FunctionRegistration | None:
        if bound_target is None or owner is None or self._owner is None:
            return None

        for candidate_owner in owner.__mro__[1:]:
            if candidate_owner in {object, type}:
                continue
            descriptor = candidate_owner.__dict__.get(self._name)
            if descriptor is None:
                continue

            raw_descriptor = _unwrap_descriptor(descriptor)[0]
            if raw_descriptor is self:
                continue

            if hasattr(descriptor, "__get__"):
                bound = descriptor.__get__(bound_target, owner)
            else:
                bound = descriptor
            skip_leading = 0 if isinstance(descriptor, staticmethod) else 1
            try:
                return _FunctionRegistration(bound, skip_leading=skip_leading)
            except TypeError:
                continue
        return None

    def _add_registration(
        self,
        *,
        function: Callable[..., Any],
        explicit_types: tuple[Any, ...] | None,
        guard: Guard | None,
        priority: int,
        same_name_return: bool,
        localns: dict[str, Any] | None,
    ) -> Any:
        try:
            registration = self._build_registration(
                function,
                explicit_types,
                guard,
                priority,
                localns,
            )
        except NameError:
            self._pending.append(
                PendingRegistration(
                    function=function,
                    explicit_types=explicit_types,
                    guard=guard,
                    priority=priority,
                    same_name_return=same_name_return,
                    localns=localns,
                )
            )
            self._cache.clear()
            self._exact_cache.clear()
            return self if same_name_return else function

        self._registrations.append(registration)
        self._cache.clear()
        self._exact_cache.clear()
        return self if same_name_return else function

    def _register_decorated(
        self,
        function: Callable[..., Any] | staticmethod | classmethod,
        explicit_types: tuple[Any, ...] | None,
        *,
        guard: Guard | None,
        priority: int,
    ) -> Any:
        if guard is not None and not callable(guard):
            raise TypeError("guard must be callable")
        raw_function, wrapper = _unwrap_descriptor(function)
        registered = self._add_registration(
            function=raw_function,
            explicit_types=explicit_types,
            guard=guard,
            priority=priority,
            same_name_return=raw_function.__name__ == self._name,
            localns=_caller_locals(),
        )
        return _rewrap_descriptor(registered, wrapper)

    def _resolve_pending(self) -> None:
        if not self._pending:
            return

        remaining: list[PendingRegistration] = []
        runtime_localns = _caller_locals()
        for pending in self._pending:
            try:
                registration = self._build_registration(
                    pending.function,
                    pending.explicit_types,
                    pending.guard,
                    pending.priority,
                    _merge_localns(pending.localns, runtime_localns),
                )
            except NameError:
                remaining.append(pending)
                continue
            self._registrations.append(registration)
        self._pending = remaining
        self._cache.clear()
        self._exact_cache.clear()

    def _build_registration(
        self,
        function: Callable[..., Any],
        explicit_types: tuple[Any, ...] | None,
        guard: Guard | None,
        priority: int,
        localns: dict[str, Any] | None,
    ) -> Registration:
        signature = inspect.signature(function)
        dispatch_params = _select_dispatch_parameters(
            signature,
            explicit_count=len(self._canonical_dispatch_params),
            drop_leading=_drops_leading_argument(signature),
        )
        _validate_dispatch_shape(self, function, signature, dispatch_params)

        constraints, parameter_guards = self._resolve_constraints(function, explicit_types, localns)
        needs_binding = (
            bool(parameter_guards)
            or guard is not None
            or signature != self._canonical_signature
            or _has_non_dispatch_tail(
                signature,
                dispatch_count=len(self._canonical_dispatch_params),
                drop_leading=_drops_leading_argument(signature),
            )
        )
        registration = Registration(
            function=function,
            signature=signature,
            constraints=constraints,
            parameter_guards=parameter_guards,
            guard=guard,
            priority=priority,
            order=self._order,
            needs_binding=needs_binding,
        )
        self._order += 1
        return registration

    def _resolve_constraints(
        self,
        function: Callable[..., Any],
        explicit_types: tuple[Any, ...] | None,
        localns: dict[str, Any] | None,
    ) -> tuple[tuple[TypeConstraint, ...], tuple[ParameterGuard, ...]]:
        if explicit_types is not None:
            if len(explicit_types) != len(self._canonical_dispatch_params):
                raise RegistrationError(
                    f"{self._name}: expected "
                    f"{len(self._canonical_dispatch_params)} dispatch types, "
                    f"got {len(explicit_types)}"
                )
            return (
                tuple(_normalize_constraint(value) for value in explicit_types),
                (),
            )

        hints = _resolve_type_hints(function, self._owner, localns)
        constraints: list[TypeConstraint] = []
        parameter_guards: list[ParameterGuard] = []
        for parameter in _select_dispatch_parameters(
            inspect.signature(function),
            explicit_count=len(self._canonical_dispatch_params),
            drop_leading=_drops_leading_argument(inspect.signature(function)),
        ):
            if parameter.name not in hints:
                raise RegistrationError(
                    f"{self._name}: missing type annotation for dispatch parameter "
                    f"{parameter.name!r}"
                )
            constraint, annotations = _parse_annotation(hints[parameter.name])
            constraints.append(constraint)
            parameter_guards.extend(
                ParameterGuard(parameter.name, predicate)
                for predicate in annotations
            )
        return tuple(constraints), tuple(parameter_guards)


class _FunctionRegistration:
    __slots__ = ("function", "skip_leading")

    def __init__(self, function: Callable[..., Any], *, skip_leading: int) -> None:
        self.function = function
        self.skip_leading = skip_leading


def multimethod(
    *types_or_function: Any,
    guard: Guard | None = None,
    priority: int = 0,
) -> Any:
    if len(types_or_function) == 1 and _is_function_like(types_or_function[0]):
        function = typing.cast(
            Callable[..., Any] | staticmethod | classmethod,
            types_or_function[0],
        )
        return _decorate_multimethod(function, explicit_types=None, guard=guard, priority=priority)

    explicit_types = tuple(types_or_function)

    def decorator(function: Callable[..., Any] | staticmethod | classmethod) -> Any:
        return _decorate_multimethod(
            function,
            explicit_types=explicit_types,
            guard=guard,
            priority=priority,
        )

    return decorator


def _decorate_multimethod(
    function: Callable[..., Any] | staticmethod | classmethod,
    *,
    explicit_types: tuple[Any, ...] | None,
    guard: Guard | None,
    priority: int,
) -> Any:
    if guard is not None and not callable(guard):
        raise TypeError("guard must be callable")
    raw_function, wrapper = _unwrap_descriptor(function)
    caller_locals = _caller_locals()
    homonym = None if caller_locals is None else caller_locals.get(raw_function.__name__)

    existing, existing_wrapper = _extract_dispatcher(homonym)
    wrapper = wrapper or existing_wrapper

    dispatcher = existing or MultiMethod(
        raw_function,
        explicit_types=explicit_types,
        guard=guard,
        priority=priority,
        localns=caller_locals,
    )
    if existing is not None:
        dispatcher._add_registration(
            function=raw_function,
            explicit_types=explicit_types,
            guard=guard,
            priority=priority,
            same_name_return=True,
            localns=caller_locals,
        )

    return _rewrap_descriptor(dispatcher, wrapper)


def _unwrap_descriptor(
    obj: Any,
) -> tuple[Callable[..., Any] | MultiMethod, type[staticmethod] | type[classmethod] | None]:
    if isinstance(obj, staticmethod):
        return obj.__func__, staticmethod
    if isinstance(obj, classmethod):
        return obj.__func__, classmethod
    return obj, None


def _rewrap_descriptor(
    obj: Any,
    wrapper: type[staticmethod] | type[classmethod] | None,
) -> Any:
    if wrapper is None:
        return obj
    return wrapper(obj)


def _extract_dispatcher(
    obj: Any,
) -> tuple[MultiMethod | None, type[staticmethod] | type[classmethod] | None]:
    if obj is None:
        return None, None
    raw, wrapper = _unwrap_descriptor(obj)
    if isinstance(raw, MultiMethod):
        return raw, wrapper
    return None, None


def _is_function_like(obj: Any) -> bool:
    return inspect.isfunction(obj) or isinstance(obj, (staticmethod, classmethod))


def _drops_leading_argument(signature: inspect.Signature) -> bool:
    parameters = list(signature.parameters.values())
    return bool(parameters and parameters[0].name in _METHOD_NAMES)


def _select_dispatch_parameters(
    signature: inspect.Signature,
    *,
    explicit_count: int | None,
    drop_leading: bool,
) -> tuple[inspect.Parameter, ...]:
    parameters = list(signature.parameters.values())
    if drop_leading and parameters:
        parameters = parameters[1:]

    dispatchable = [parameter for parameter in parameters if parameter.kind in _DISPATCH_KINDS]
    count = len(dispatchable) if explicit_count is None else explicit_count
    if count > len(dispatchable):
        raise RegistrationError(
            f"expected at least {count} positional dispatch parameters, got {len(dispatchable)}"
        )
    return tuple(dispatchable[:count])


def _validate_dispatch_shape(
    dispatcher: MultiMethod,
    function: Callable[..., Any],
    signature: inspect.Signature,
    dispatch_params: Sequence[inspect.Parameter],
) -> None:
    if len(dispatch_params) != len(dispatcher._canonical_dispatch_params):
        raise RegistrationError(
            f"{dispatcher._name}: overload {function.__qualname__} has "
            f"{len(dispatch_params)} dispatch parameters, expected "
            f"{len(dispatcher._canonical_dispatch_params)}"
        )

    for canonical, current in zip(
        dispatcher._canonical_dispatch_params,
        dispatch_params,
        strict=True,
    ):
        if canonical.kind != current.kind:
            raise RegistrationError(
                f"{dispatcher._name}: dispatch parameter {current.name!r} changes kind "
                f"from {canonical.kind.name} to {current.kind.name}"
            )
        if (
            canonical.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
            and canonical.name != current.name
        ):
            raise RegistrationError(
                f"{dispatcher._name}: dispatch parameter name mismatch, expected "
                f"{canonical.name!r}, got {current.name!r}"
            )
        if (canonical.default is _EMPTY) != (current.default is _EMPTY):
            raise RegistrationError(
                f"{dispatcher._name}: dispatch parameter {canonical.name!r} "
                f"changes default presence"
            )
        if canonical.default is not _EMPTY and canonical.default != current.default:
            raise RegistrationError(
                f"{dispatcher._name}: dispatch parameter {canonical.name!r} changes default value"
            )

    try:
        signature.bind_partial(*([None] * len(signature.parameters)))
    except TypeError:
        pass


def _resolve_type_hints(
    function: Callable[..., Any],
    owner: type | None,
    localns: dict[str, Any] | None,
) -> dict[str, Any]:
    namespace: dict[str, Any] = {}
    if owner is not None:
        namespace.update(vars(owner))
    if localns is not None:
        namespace.update(localns)
    resolved_localns = namespace or None
    return get_type_hints(
        function,
        globalns=function.__globals__,
        localns=resolved_localns,
        include_extras=True,
    )


def _parse_annotation(annotation: Any) -> tuple[TypeConstraint, tuple[Callable[[Any], bool], ...]]:
    predicates: list[Callable[[Any], bool]] = []
    while get_origin(annotation) is Annotated:
        args = get_args(annotation)
        annotation = args[0]
        for metadata in args[1:]:
            if isinstance(metadata, Where):
                predicates.append(metadata.predicate)
            else:
                raise RegistrationError(f"unsupported Annotated metadata: {metadata!r}")
    return _normalize_constraint(annotation), tuple(predicates)


def _normalize_constraint(value: Any) -> TypeConstraint:
    if value in {Any, typing.Any}:
        return TypeConstraint(None)
    if isinstance(value, tuple):
        return _normalize_union(value)

    origin = get_origin(value)
    if origin in {typing.Union, UnionType}:
        return _normalize_union(get_args(value))
    if inspect.isclass(value):
        return TypeConstraint((value,))
    raise RegistrationError(
        "unsupported dispatch annotation or explicit type "
        f"{value!r}; use classes, unions of classes, Any, or Annotated[T, where(...)]"
    )


def _normalize_union(values: Sequence[Any]) -> TypeConstraint:
    options: list[type] = []
    for value in values:
        if value in {Any, typing.Any}:
            return TypeConstraint(None)
        if not inspect.isclass(value):
            raise RegistrationError(
                f"unsupported union member {value!r}; only classes and Any are supported"
            )
        options.append(value)

    normalized: list[type] = []
    for option in options:
        if any(existing is option for existing in normalized):
            continue
        if any(issubclass(option, existing) for existing in normalized):
            continue
        normalized = [existing for existing in normalized if not issubclass(existing, option)]
        normalized.append(option)
    return TypeConstraint(tuple(normalized))


def _invoke_guard(guard: Guard, bound: inspect.BoundArguments) -> bool:
    signature = inspect.signature(guard)
    parameters = list(signature.parameters.values())
    if not parameters:
        return bool(guard())

    accepts_var_keyword = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters
    )
    if accepts_var_keyword:
        return bool(guard(**bound.arguments))

    supported = {}
    for parameter in parameters:
        if parameter.kind in _DISPATCH_KINDS or parameter.kind is inspect.Parameter.KEYWORD_ONLY:
            if parameter.name in bound.arguments:
                supported[parameter.name] = bound.arguments[parameter.name]
    return bool(guard(**supported))


def _has_non_dispatch_tail(
    signature: inspect.Signature,
    *,
    dispatch_count: int,
    drop_leading: bool,
) -> bool:
    parameters = list(signature.parameters.values())
    if drop_leading and parameters:
        parameters = parameters[1:]
    tail = parameters[dispatch_count:]
    return any(
        parameter.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }
        for parameter in tail
    )


def _caller_locals() -> dict[str, Any] | None:
    frame = inspect.currentframe()
    while frame is not None:
        frame = frame.f_back
        if frame is None:
            return None
        if frame.f_code.co_filename != __file__:
            return dict(frame.f_locals)
    return None


def _merge_localns(
    first: dict[str, Any] | None,
    second: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if first is None and second is None:
        return None
    merged: dict[str, Any] = {}
    if first is not None:
        merged.update(first)
    if second is not None:
        merged.update(second)
    return merged


def _reduce_specificity(registrations: Sequence[Registration]) -> list[Registration]:
    winners: list[Registration] = []
    for candidate in registrations:
        if any(
            other.more_specific_than(candidate)
            for other in registrations
            if other is not candidate
        ):
            continue
        winners.append(candidate)
    winners.sort(key=lambda item: (item.priority, -item.order), reverse=True)
    return winners


def _apply_priority(registrations: Sequence[Registration]) -> list[Registration]:
    if len(registrations) <= 1:
        return list(registrations)
    top_priority = max(registration.priority for registration in registrations)
    prioritized = [
        registration
        for registration in registrations
        if registration.priority == top_priority
    ]
    return prioritized
