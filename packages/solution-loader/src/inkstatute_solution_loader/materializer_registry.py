"""Materializer registry: dispatch by (backend_id, solution_id).

Materializers are registered with their declared side-effects so callers
can assert "no undeclared side effects" before invoking ``materialize_for``.

The registry is keyed by the ``(backend_id, solution_id)`` tuple so that
multiple solution packs can register a materializer for the same backend
without silently overwriting each other (Plan 13-03 composability claim:
"Both packs register into the same MaterializerRegistry without conflict").
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from platform_runtime import BackendSolutionBundle, Issue, Solution


MaterializerFn = Callable[[Solution, Path | None], tuple[list[Issue], BackendSolutionBundle | None]]


class MaterializerRegistry:
    """Maps (backend_id, solution_id) → (materializer function, declared side-effects)."""

    def __init__(self) -> None:
        self._by_key: dict[
            tuple[str, str], tuple[MaterializerFn, "MaterializerSideEffects"]
        ] = {}

    def register(
        self,
        backend_id: str,
        fn: MaterializerFn,
        side_effects: "MaterializerSideEffects",
        solution_id: str,
    ) -> None:
        """Register a materializer for a given (backend_id, solution_id).

        ``solution_id`` is required so that multiple solution packs can
        register distinct materializers for the same backend without
        colliding. Duplicate registration for the same tuple overwrites
        the previous entry (same solution_id ⇒ same pack).
        """

        self._by_key[(backend_id, solution_id)] = (fn, side_effects)

    def get(self, backend_id: str, solution_id: str) -> MaterializerFn | None:
        """Return the registered materializer function, or ``None``."""

        entry = self._by_key.get((backend_id, solution_id))
        return entry[0] if entry else None

    def side_effects_for(
        self, backend_id: str, solution_id: str
    ) -> "MaterializerSideEffects | None":
        """Return the declared side-effects for a given (backend_id, solution_id), or ``None``."""

        entry = self._by_key.get((backend_id, solution_id))
        return entry[1] if entry else None

    def known_backends(self) -> tuple[str, ...]:
        """Return the sorted list of registered backend_ids (de-duplicated)."""

        return tuple(sorted({key[0] for key in self._by_key.keys()}))

    def known_solutions(self, backend_id: str) -> tuple[str, ...]:
        """Return the sorted list of solution_ids registered for a given backend_id."""

        return tuple(
            sorted(key[1] for key in self._by_key.keys() if key[0] == backend_id)
        )

    def __contains__(self, key: object) -> bool:
        # Support both ``backend_id in registry`` (backward-compatible
        # membership check against any registered backend) and
        # ``(backend_id, solution_id) in registry`` (exact tuple check).
        if isinstance(key, tuple):
            return key in self._by_key
        if isinstance(key, str):
            return any(k[0] == key for k in self._by_key.keys())
        return False