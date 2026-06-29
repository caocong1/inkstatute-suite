"""Default-off configuration for the SolutionLoader."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


_TRUTHY = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True, slots=True)
class SolutionLoaderFeatureFlags:
    """Default-off feature flag for the SolutionLoader.

    The loader is opt-in: callers must explicitly assert
    ``require_enabled() is True`` before invoking
    ``materialize_for``.
    """

    enabled: bool = False

    def require_enabled(self) -> bool:
        """Return True only when the loader is explicitly enabled."""
        return self.enabled


def load_solution_loader_feature_flags(
    env: Mapping[str, str] | None = None,
) -> SolutionLoaderFeatureFlags:
    """Parse ``INKSTATUTE_SOLUTION_LOADER_ENABLED`` defensively.

    Absent, empty, or malformed values resolve to ``enabled=False``.
    """

    raw = (env or os.environ).get("INKSTATUTE_SOLUTION_LOADER_ENABLED", "")
    if not isinstance(raw, str):
        return SolutionLoaderFeatureFlags(enabled=False)
    return SolutionLoaderFeatureFlags(enabled=raw.strip().lower() in _TRUTHY)


@dataclass(frozen=True, slots=True)
class DefaultSolutionLoaderConfig:
    """Loader configuration.

    ``declared_output_root``: optional anchor for the loader's path-traversal
    guard. When ``None`` (default), the loader only enforces that any
    ``bundle_ref`` returned by a materializer resolves inside the caller-
    provided ``output_dir`` of ``materialize_for``.
    """

    declared_output_root: Path | None = None
    allow_unknown_backends: bool = False  # if True, materialize_for returns empty Issues + None for unknown