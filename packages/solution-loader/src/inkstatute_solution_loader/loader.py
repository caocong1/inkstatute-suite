"""DefaultSolutionLoader: validate / load / materialize_for.

Wraps the ``platform_runtime.protocols.SolutionLoader`` Protocol with a
path-traversal guard, side-effect assertion, and a default-off posture.
"""

from __future__ import annotations

from pathlib import Path

from platform_runtime import (
    BackendSolutionBundle,
    Issue,
    Solution,
    SolutionPackageManifest,
)

from .config import DefaultSolutionLoaderConfig
from .manifest_validator import ManifestValidator
from .materializer_registry import MaterializerRegistry
from .side_effects import MaterializerSideEffects


class DefaultSolutionLoader:
    """Concrete ``SolutionLoader`` implementation.

    Construct with ``DefaultSolutionLoader(config, registry)``. The default
    registry is empty; callers register materializers explicitly.
    """

    def __init__(
        self,
        config: DefaultSolutionLoaderConfig | None = None,
        registry: MaterializerRegistry | None = None,
    ) -> None:
        self._config = config or DefaultSolutionLoaderConfig()
        self._registry = registry or MaterializerRegistry()
        self._validator = ManifestValidator()

    def validate(self, manifest: SolutionPackageManifest) -> list[Issue]:
        """Delegate to ManifestValidator."""
        return self._validator.validate(manifest)

    def load(self, manifest: SolutionPackageManifest) -> Solution:
        """Wrap a manifest in a Solution. Pure compute, no I/O."""
        return Solution(
            solution_id=manifest.solution_id,
            version=manifest.version,
            manifest=manifest,
            metadata=dict(manifest.metadata or {}),
        )

    def materialize_for(
        self,
        solution: Solution,
        backend_id: str,
        output_dir: Path | None = None,
    ) -> tuple[list[Issue], BackendSolutionBundle | None]:
        """Invoke the registered materializer.

        Returns ``(issues, bundle_or_none)``:
        - Empty issues and a non-None bundle on success.
        - Non-empty issues and ``None`` on refusal (no materializer registered,
          materializer pre-flight refusal, or path-traversal guard trip).

        When ``output_dir is None`` and the materializer's declared side-effects
        include ``write_dir``, the loader returns a refusal Issue explaining
        that an explicit output_dir is required.
        """

        fn = self._registry.get(backend_id, solution.solution_id)
        if fn is None:
            return (
                [
                    Issue(
                        path=f"materialize_for({backend_id}, {solution.solution_id})",
                        code="no_materializer_registered",
                        message=(
                            f"no materializer registered for "
                            f"backend_id={backend_id!r}, solution_id={solution.solution_id!r}"
                        ),
                        severity="error",
                    )
                ],
                None,
            )

        side_effects = self._registry.side_effects_for(backend_id, solution.solution_id)
        # pragma: no cover - invariant: get() and side_effects_for() share state
        if side_effects is None:
            return (
                [
                    Issue(
                        path=f"materialize_for({backend_id}, {solution.solution_id})",
                        code="no_materializer_registered",
                        message=(
                            f"materializer registered for "
                            f"backend_id={backend_id!r}, solution_id={solution.solution_id!r} "
                            "but side-effects entry is missing (registry invariant broken)"
                        ),
                        severity="error",
                    )
                ],
                None,
            )

        if "write_dir" in side_effects.side_effect_kinds:
            if output_dir is None:
                return (
                    [
                        Issue(
                            path="materialize_for.output_dir",
                            code="write_dir_requires_output_dir",
                            message=(
                                f"materializer for {backend_id!r} declares write_dir; "
                                "an explicit output_dir is required"
                            ),
                            severity="error",
                        )
                    ],
                    None,
                )

        # Call materializer. Two cases:
        # 1. Materializer that takes output_dir (write_dir kind).
        # 2. Materializer that ignores output_dir (read-only / pure compute).
        if output_dir is not None:
            issues, bundle = fn(solution, output_dir)
        else:
            issues, bundle = fn(solution, None)

        if bundle is None:
            return issues, None

        # Path-traversal guard: bundle.bundle_ref must resolve inside output_dir.
        if output_dir is not None:
            bundle_path = Path(bundle.bundle_ref)
            try:
                resolved_bundle = bundle_path.resolve()
                resolved_output = output_dir.resolve()
                if not resolved_bundle.is_relative_to(resolved_output):
                    return (
                        issues
                        + [
                            Issue(
                                path="materialize_for.bundle_ref",
                                code="bundle_ref_outside_output_dir",
                                message=(
                                    f"bundle_ref {bundle.bundle_ref!r} resolves "
                                    f"outside output_dir {str(output_dir)!r}"
                                ),
                                severity="error",
                            )
                        ],
                        None,
                    )
            except (OSError, ValueError):
                return (
                    issues
                    + [
                        Issue(
                            path="materialize_for.bundle_ref",
                            code="bundle_ref_unresolvable",
                            message=f"bundle_ref {bundle.bundle_ref!r} could not be resolved",
                            severity="error",
                        )
                    ],
                    None,
                )

        return issues, bundle

    def classify_side_effects(
        self, backend_id: str, solution_id: str | None = None
    ) -> MaterializerSideEffects | None:
        """Return the declared side-effects for a given (backend_id, solution_id), or ``None``.

        When ``solution_id`` is ``None`` and exactly one materializer is
        registered for ``backend_id``, return its side-effects. This keeps
        the single-pack path ergonomic while the tuple-keyed registry
        supports multi-pack composability.
        """

        if solution_id is not None:
            return self._registry.side_effects_for(backend_id, solution_id)
        solutions = self._registry.known_solutions(backend_id)
        if len(solutions) == 1:
            return self._registry.side_effects_for(backend_id, solutions[0])
        return None