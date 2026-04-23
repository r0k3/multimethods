from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DispatchError(LookupError):
    name: str
    message: str

    def __str__(self) -> str:
        return f"{self.name}: {self.message}"


@dataclass(slots=True)
class NoMatchError(DispatchError):
    argument_types: tuple[type, ...]

    def __str__(self) -> str:
        rendered = ", ".join(t.__name__ for t in self.argument_types) or "<no dispatch args>"
        return f"{self.name}: no matching overload for ({rendered})"


@dataclass(slots=True)
class AmbiguousDispatchError(DispatchError):
    argument_types: tuple[type, ...]
    candidates: tuple[str, ...]

    def __str__(self) -> str:
        rendered_types = ", ".join(t.__name__ for t in self.argument_types) or "<no dispatch args>"
        rendered_candidates = "; ".join(self.candidates)
        return (
            f"{self.name}: ambiguous dispatch for ({rendered_types}); "
            f"candidates: {rendered_candidates}"
        )


class RegistrationError(TypeError):
    """Raised when an overload cannot be registered safely."""

