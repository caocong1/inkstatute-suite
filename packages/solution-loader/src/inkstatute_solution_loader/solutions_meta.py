"""Aggregate registration helpers for bundled solution materializers.

These functions import from the concrete solution packs (lawfirm, demo_non_legal)
and wire them into a MaterializerRegistry. They exist so Phase 13 evidence tests
do not have to know how each pack exposes its materializer.

Each pack registers under ``(backend_id, solution_id)`` so that multiple packs
can share the same backend without colliding (Plan 13-03 composability claim).
"""

from __future__ import annotations

from inkstatute_solution_loader.materializer_registry import MaterializerRegistry


def register_lawfirm_materializer(registry: MaterializerRegistry, backend_id: str = "hermes") -> None:
    """Register the lawfirm Hermes materializer into the given registry."""

    from inkstatute_solutions_lawfirm import LAWFIRM_SOLUTION_ID, LawfirmHermesMaterializer

    mat = LawfirmHermesMaterializer()
    registry.register(
        backend_id, mat.materialize, mat.side_effects(), solution_id=LAWFIRM_SOLUTION_ID
    )


def register_demo_non_legal_materializer(
    registry: MaterializerRegistry, backend_id: str = "hermes"
) -> None:
    """Register the demo_non_legal Hermes materializer into the given registry."""

    from inkstatute_solutions_demo_non_legal import (
        DEMO_NON_LEGAL_SOLUTION_ID,
        DemoNonLegalHermesMaterializer,
    )

    mat = DemoNonLegalHermesMaterializer()
    registry.register(
        backend_id,
        mat.materialize,
        mat.side_effects(),
        solution_id=DEMO_NON_LEGAL_SOLUTION_ID,
    )


__all__ = [
    "register_demo_non_legal_materializer",
    "register_lawfirm_materializer",
]