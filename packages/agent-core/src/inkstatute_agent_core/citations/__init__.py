"""Citation audit: extract every legal citation from a generated document and
verify it against the local law library (exact article text) and this
turn's retrieval-tool results. Annotation-style — never blocks output.

A Python port of the Rust ``citations/mod.rs`` from
``lawyer-desktop/src-tauri/src/citations/mod.rs`` (55 lines).

The ``audit()`` function composes ``extract_citations()`` and
``verify_items()`` to produce a ``CitationAudit`` result with per-item
verification status and aggregate counts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .extract import CitationKind, ExtractedCitation, extract_citations
from .verify import (
    ArticleLookup,
    CitationAuditItem,
    LawEntry,
    LawLibrary,
    verify_items,
)


@dataclass(frozen=True)
class CitationAudit:
    """Aggregate citation audit result.

    Attributes:
        items: List of per-citation verification results.
        total: Total number of citations.
        verified: Count of "verified" citations (local library match).
        retrieved: Count of "retrieved" citations (retrieval evidence only).
        unverified: Count of "unverified" citations (no evidence found).
    """

    items: list[CitationAuditItem] = field(default_factory=list)
    total: int = 0
    verified: int = 0
    retrieved: int = 0
    unverified: int = 0


async def audit(
    text: str,
    retrievals: list[tuple[str, str]],
    law_library: LawLibrary | None = None,
) -> CitationAudit:
    """Audit a finished answer for citation correctness.

    Extracts all citations from *text*, verifies each against the local
    law library and this turn's retrieval results, and returns a
    ``CitationAudit`` with per-item details and aggregate counts.

    Never fails — errors degrade to "unverified" items.

    Ported from ``mod.rs:43-55``.

    Args:
        text: The finished answer text to audit.
        retrievals: List of ``(tool_name, result_text)`` pairs from this
            turn's retrieval tools.
        law_library: Optional law library for authoritative verification.
            Defaults to ``None`` (all lookups fail → retrieval fallback).

    Returns:
        A ``CitationAudit`` with items and counts.
    """
    extracted = extract_citations(text)
    items = await verify_items(extracted, retrievals, law_library)

    def count(status: str) -> int:
        return sum(1 for i in items if i.status == status)

    return CitationAudit(
        items=items,
        total=len(items),
        verified=count("verified"),
        retrieved=count("retrieved"),
        unverified=count("unverified"),
    )


__all__ = [
    "ArticleLookup",
    "CitationAudit",
    "CitationAuditItem",
    "CitationKind",
    "ExtractedCitation",
    "LawEntry",
    "LawLibrary",
    "audit",
    "extract_citations",
    "verify_items",
]
