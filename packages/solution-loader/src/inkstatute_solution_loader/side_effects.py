"""Side-effect declaration contract.

Materializers MUST declare their side-effects at registration time so callers
can assert "no undeclared side effects" per the north-star invariant.
"""

from __future__ import annotations

from dataclasses import dataclass


ALLOWED_SIDE_EFFECT_KINDS: frozenset[str] = frozenset(
    {"write_dir", "read_dir", "subprocess", "network"}
)


@dataclass(frozen=True, slots=True)
class MaterializerSideEffects:
    """Declared side-effects of a materializer."""

    backend_id: str
    declared_output_dir_relative: str | None  # e.g., "profiles/<solution_id>" or None
    side_effect_kinds: tuple[str, ...]  # subset of ALLOWED_SIDE_EFFECT_KINDS
    notes: str = ""

    def __post_init__(self) -> None:
        for kind in self.side_effect_kinds:
            if kind not in ALLOWED_SIDE_EFFECT_KINDS:
                raise ValueError(
                    f"side_effect_kind {kind!r} not in allowed set "
                    f"{sorted(ALLOWED_SIDE_EFFECT_KINDS)}"
                )