"""Materializer registry: dispatch by backend_id.

Materializers are registered with their declared side-effects so callers
can assert "no undeclared side effects" before invoking ``materialize_for``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from platform_runtime import BackendSolutionBundle, Issue, Solution


MaterializerFn = Callable[[Solution, Path], tuple[list[Issue], BackendSolutionBundle | None]]


class MaterializerRegistry:
    """Maps backend_id → (materializer function, declared side-effects)."""

    def __init__(self) -> None:
        self._by_backend: dict[str, tuple[MaterializerFn, "MaterializerSideEffects"]] = {}

    def register(
        self,
        backend_id: str,
        fn: MaterializerFn,
        side_effects: "MaterializerSideEffects",
    ) -> None:
        """Register a materializer for a given backend_id."""

        self._by_backend[backend_id] = (fn, side_effects)

    def get(self, backend_id: str) -> MaterializerFn | None:
        """Return the registered materializer function, or ``None``."""

        entry = self._by_backend.get(backend_id)
        return entry[0] if entry else None

    def side_effects_for(self, backend_id: str) -> "MaterializerSideEffects | None":
        """Return the declared side-effects for a given backend_id, or ``None``."""

        entry = self._by_backend.get(backend_id)
        return entry[1] if entry else None

    def known_backends(self) -> tuple[str, ...]:
        """Return the sorted list of registered backend_ids."""

        return tuple(sorted(self._by_backend.keys()))

    def __contains__(self, backend_id: str) -> bool:
        return backend_id in self._by_backend