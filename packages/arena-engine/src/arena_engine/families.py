"""Cross-family review enforcement primitives for Modes 3+4 (SAFE-06).

Ensures that review pairs satisfy ``backend_family(A) != backend_family(B)``
so an agent is never reviewed by a sibling from the same model family.

- ``DEFAULT_FAMILY_MAP`` — known ``backend_id`` → family mappings.
- ``get_backend_family()`` — resolves a backend ID to its family.
- ``CrossFamilyPairingResult`` — frozen slotted result with degradation flag.
- ``_pair_cross_family()`` — greedy cross-family pairing algorithm.

When only same-family agents are available, the system does NOT silently
proceed — it returns an explicit degradation result with ``degraded=True``
and a non-empty ``reason`` so the caller can emit a warning.

ENGINE-05: this module imports zero LLM provider packages.
ENGINE-06: this module never calls ``session/resume`` or
``resume_session``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Backend → family mapping
# ---------------------------------------------------------------------------

DEFAULT_FAMILY_MAP: dict[str, str] = {
    "hermes": "claude",
    "codex": "gpt",
    "gemini-cli": "gemini",
    "inkstatute-agent": "inkstatute",
    "claude-code": "claude",
    "claude": "claude",
    "gpt": "gpt",
    "gemini": "gemini",
}


def get_backend_family(backend_id: str) -> str:
    """Resolve a backend ID to its model family.

    Known backends are mapped via :data:`DEFAULT_FAMILY_MAP`.
    Unknown backends default to their own ID as the family — this
    ensures that two different unknown backends are treated as
    different families (conservative for cross-family enforcement).
    """
    return DEFAULT_FAMILY_MAP.get(backend_id, backend_id)


# ---------------------------------------------------------------------------
# Cross-family pairing result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CrossFamilyPairingResult:
    """Result of cross-family pairing with explicit degradation flag.

    Fields
    ------
    pairs
        Mapping of reviewer slot → reviewed slot.  Empty when degraded.
    degraded
        ``True`` when not all slots could be cross-paired.
    reason
        Degradation reason: ``""``, ``"same_family_only"``,
        ``"single_agent"``, or ``"partial_same_family"``.
    metadata
        Additional structured metadata (e.g. ``unpaired_slots``).
    """

    pairs: dict[str, str]
    degraded: bool
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Cross-family pairing algorithm
# ---------------------------------------------------------------------------


def _pair_cross_family(
    slots: list[str],
    families: dict[str, str],
) -> CrossFamilyPairingResult:
    """Produce a cross-family reviewer → reviewed pairing.

    Each slot is assigned exactly one slot to review, and each slot is
    reviewed by exactly one other slot (when possible).  The constraint
    is ``families[reviewer] != families[reviewed]``.

    Degradation cases (NEVER silent):
    - ``len(slots) <= 1`` → ``degraded=True, reason="single_agent"``
    - All slots same family → ``degraded=True, reason="same_family_only"``
    - Some slots cannot be cross-paired → ``degraded=True,
      reason="partial_same_family"`` (unpaired slots in metadata)

    On full success: ``degraded=False, reason=""``.
    """
    n = len(slots)
    if n <= 1:
        return CrossFamilyPairingResult(
            pairs={},
            degraded=True,
            reason="single_agent",
        )

    # Check if all slots are the same family.
    distinct_families = {families.get(s, s) for s in slots}
    if len(distinct_families) == 1:
        return CrossFamilyPairingResult(
            pairs={},
            degraded=True,
            reason="same_family_only",
        )

    # Greedy cyclic pairing: slot[i] tries to review slot[(i+k) % n]
    # for k = 1, 2, …, skipping self and same-family.
    # Each reviewer reviews exactly one slot; each slot is reviewed by
    # exactly one slot (bijection when possible).
    pairs: dict[str, str] = {}
    used_reviewers: set[str] = set()
    used_reviewed: set[str] = set()

    for i, reviewer in enumerate(slots):
        reviewer_family = families.get(reviewer, reviewer)
        for k in range(1, n):
            candidate_idx = (i + k) % n
            candidate = slots[candidate_idx]
            if candidate == reviewer:
                continue
            if candidate in used_reviewed:
                continue
            candidate_family = families.get(candidate, candidate)
            if candidate_family == reviewer_family:
                continue
            pairs[reviewer] = candidate
            used_reviewers.add(reviewer)
            used_reviewed.add(candidate)
            break

    unpaired = [s for s in slots if s not in pairs]

    if unpaired:
        return CrossFamilyPairingResult(
            pairs=pairs,
            degraded=True,
            reason="partial_same_family",
            metadata={"unpaired_slots": unpaired},
        )

    return CrossFamilyPairingResult(
        pairs=pairs,
        degraded=False,
        reason="",
    )


__all__ = [
    "CrossFamilyPairingResult",
    "DEFAULT_FAMILY_MAP",
    "_pair_cross_family",
    "get_backend_family",
]
