"""Three-state citation verification: verified / retrieved / unverified.

A Python port of the Rust ``verify.rs`` from
``lawyer-desktop/src-tauri/src/citations/verify.rs`` (250 lines).

Each extracted citation is verified against two evidence sources:

1. **Local law library** (optional) — exact article text lookup provides
   the strongest verification level ("verified", tier "L1-法规（本地库）").
2. **Retrieval evidence** — this turn's retrieval-tool results. If the
   citation fragments appear in a retrieval result, the citation is
   "retrieved" (weaker verification, tier from ``来源层级:`` line).

If neither source confirms the citation, it is "unverified" with a
``待律师复核`` note.

The law library dependency is optional (defaults to ``None``), meaning
all library lookups fail and the verifier falls back to retrieval
evidence. This matches the Rust unit-test behavior where the library
is uninitialized.

No external dependencies — uses only the Python standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Protocol, runtime_checkable

from .extract import CitationKind, ExtractedCitation


# ---------------------------------------------------------------------------
# Law library protocol (optional dependency)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LawEntry:
    """A law library manifest entry (subset of Rust ``LawManifestEntry``).

    Only the fields used by citation verification are included.
    """

    name: str = ""
    status: str | None = None
    source_url: str | None = None
    article_count: int | None = None


@dataclass(frozen=True)
class ArticleLookup:
    """Structured result of an exact-article lookup.

    Mirrors the Rust ``ArticleLookup`` enum as a tagged dataclass.
    The ``kind`` field distinguishes the variants:

    - ``"found"`` — law and article both found; ``heading`` and ``text``
      contain the article content.
    - ``"law_found_article_missing"`` — law found but article number not
      found; ``article_count`` gives the total article count.
    - ``"bad_article_ref"`` — the article reference could not be parsed.
    - ``"law_not_found"`` — the law name was not in the library.
    """

    kind: str
    entry: LawEntry | None = None
    heading: str = ""
    text: str = ""
    article_count: int = 0


@runtime_checkable
class LawLibrary(Protocol):
    """Protocol for the optional law library dependency.

    A concrete implementation must provide these async methods.
    When ``None`` is passed to the verifier, all lookups fail and the
    verifier falls back to retrieval evidence.
    """

    async def lookup_article(self, law_name: str, article: str) -> ArticleLookup | None:
        """Look up an article by law name and article reference.

        Returns ``None`` if the library is not available or an error occurs.
        """
        ...

    async def find_by_doc_number(self, doc_number: str) -> LawEntry | None:
        """Find a library entry by 文号 (e.g. 法释〔2020〕28号).

        Returns ``None`` if the library is not available or no match found.
        """
        ...


# ---------------------------------------------------------------------------
# CitationAuditItem — the verification result for a single citation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CitationAuditItem:
    """Verification result for a single citation.

    Attributes:
        kind: The ``CitationKind`` (Law / Interpretation / Case).
        source: 法名 for laws/interpretations; empty for bare case numbers.
        reference: 第N条 / 法释〔YYYY〕N号 / case number / 入库编号.
        status: "verified" | "retrieved" | "unverified".
        tier: Optional provenance tier (e.g. "L1-法规（本地库）", "L2-入库").
        excerpt: Optional 160-char excerpt of the source text.
        url: Optional source URL.
        note: Optional human-readable note (e.g. "待律师复核" warning).
    """

    kind: CitationKind
    source: str
    reference: str
    status: str = "unverified"
    tier: str | None = None
    excerpt: str | None = None
    url: str | None = None
    note: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXCERPT_CHARS = 160


def _excerpt(text: str, max_chars: int = _EXCERPT_CHARS) -> str:
    """Truncate *text* to *max_chars* characters, appending ``…`` if truncated.

    Whitespace is collapsed (matching Rust ``split_whitespace().join(" ")``).
    Ported from ``verify.rs:9-16``.
    """
    cleaned = " ".join(text.split())
    if len(cleaned) > max_chars:
        return cleaned[:max_chars] + "…"
    return cleaned


def _tier_from_result(result: str) -> str | None:
    """Extract the first ``来源层级:`` provenance line from a retrieval result.

    Ported from ``verify.rs:18-25``.
    """
    for line in result.splitlines():
        stripped = line.strip()
        if stripped.startswith("来源层级:"):
            return stripped[len("来源层级:"):].strip()
    return None


def _find_in_retrievals(
    retrievals: list[tuple[str, str]],
    fragments: list[str],
) -> tuple[str, str] | None:
    """Find the first retrieval result containing ALL non-empty fragments.

    Ported from ``verify.rs:28-37``.
    """
    for tool_name, result in retrievals:
        if all(f and f in result for f in fragments):
            return (tool_name, result)
    return None


# ---------------------------------------------------------------------------
# Per-kind verification functions
# ---------------------------------------------------------------------------

async def verify_law_article(
    c: ExtractedCitation,
    retrievals: list[tuple[str, str]],
    law_library: LawLibrary | None = None,
) -> CitationAuditItem:
    """Verify a law-article citation against the local library and retrievals.

    Ported from ``verify.rs:39-101``.

    Flow:
    1. Try library lookup → "verified" with excerpt + tier.
    2. If library returns ``law_found_article_missing`` → "unverified" with note.
    3. If library returns ``law_not_found`` / ``bad_article_ref`` / error
       → fall back to retrievals → "retrieved" or "unverified".
    """
    base = CitationAuditItem(
        kind=c.kind,
        source=c.source,
        reference=c.reference,
    )

    # Try library lookup
    if law_library is not None:
        try:
            lookup = await law_library.lookup_article(c.source, c.reference)
        except Exception:
            lookup = None

        if lookup is not None:
            if lookup.kind == "found" and lookup.entry is not None:
                note = None
                entry = lookup.entry
                if entry.status and entry.status != "现行有效":
                    note = f"⚠ 该法规时效状态为「{entry.status}」，请核对最新版本"
                return CitationAuditItem(
                    kind=c.kind,
                    source=c.source,
                    reference=c.reference,
                    status="verified",
                    tier="L1-法规（本地库）",
                    excerpt=_excerpt(f"{lookup.heading} {lookup.text}"),
                    url=entry.source_url,
                    note=note,
                )
            elif lookup.kind == "law_found_article_missing" and lookup.entry is not None:
                entry = lookup.entry
                count = lookup.article_count or entry.article_count or 0
                return replace(base, note=f"《{entry.name}》共 {count} 条，未找到该条文号 — 引用可能有误")

    # Library not available or law not found / bad ref → retrieval fallback
    found = _find_in_retrievals(retrievals, [c.source, c.reference])
    if found is not None:
        _, result = found
        return CitationAuditItem(
            kind=c.kind,
            source=c.source,
            reference=c.reference,
            status="retrieved",
            tier=_tier_from_result(result),
            note="本地库未收录，依据本轮在线检索结果",
        )
    return replace(base, note="本地库未收录且本轮未检索到 — 待律师复核")


async def verify_interpretation(
    c: ExtractedCitation,
    retrievals: list[tuple[str, str]],
    law_library: LawLibrary | None = None,
) -> CitationAuditItem:
    """Verify an interpretation citation (法释/国务院令) against library and retrievals.

    Ported from ``verify.rs:103-158``.

    Flow:
    1. Try doc-number lookup → "verified".
    2. Try name-based lookup (第一条) → "verified" with "按名称匹配" note.
    3. Fall back to retrievals → "retrieved".
    4. Else "unverified" with "待律师复核" note.
    """
    base = CitationAuditItem(
        kind=c.kind,
        source=c.source,
        reference=c.reference,
    )

    # 1. Match by 文号 first
    if law_library is not None:
        try:
            entry = await law_library.find_by_doc_number(c.reference)
        except Exception:
            entry = None

        if entry is not None:
            note = None
            if entry.status and entry.status != "现行有效":
                note = f"⚠ 时效状态「{entry.status}」"
            return CitationAuditItem(
                kind=c.kind,
                source=c.source,
                reference=c.reference,
                status="verified",
                tier="L1-法规（本地库）",
                url=entry.source_url,
                note=note,
            )

        # 2. Try name-based lookup
        if c.source:
            try:
                lookup = await law_library.lookup_article(c.source, "第一条")
            except Exception:
                lookup = None

            if lookup is not None and lookup.entry is not None and lookup.kind in ("found", "law_found_article_missing"):
                return CitationAuditItem(
                    kind=c.kind,
                    source=c.source,
                    reference=c.reference,
                    status="verified",
                    tier="L1-法规（本地库）",
                    url=lookup.entry.source_url,
                    note="按名称匹配本地库（文号未逐字比对）",
                )

    # 3. Fall back to retrievals
    found = _find_in_retrievals(retrievals, [c.reference])
    if found is None and c.source:
        found = _find_in_retrievals(retrievals, [c.source])
    if found is not None:
        _, result = found
        return CitationAuditItem(
            kind=c.kind,
            source=c.source,
            reference=c.reference,
            status="retrieved",
            tier=_tier_from_result(result),
        )

    # 4. Unverified
    return replace(base, note="本地库未收录且本轮未检索到 — 待律师复核")


def verify_case(
    c: ExtractedCitation,
    retrievals: list[tuple[str, str]],
) -> CitationAuditItem:
    """Verify a case-number citation against retrieval evidence only.

    Ported from ``verify.rs:160-197``.

    Case numbers are weakly verified: the case number must appear in this
    turn's retrieval output. Both fullwidth and halfwidth bracket forms
    are tried.
    """
    base = CitationAuditItem(
        kind=c.kind,
        source=c.source,
        reference=c.reference,
    )

    halfwidth = c.reference.replace("（", "(").replace("）", ")")

    found = _find_in_retrievals(retrievals, [c.reference])
    if found is None:
        found = _find_in_retrievals(retrievals, [halfwidth])

    if found is not None:
        _, result = found
        return CitationAuditItem(
            kind=c.kind,
            source=c.source,
            reference=c.reference,
            status="retrieved",
            tier=_tier_from_result(result),
        )
    return replace(base, note="本轮检索结果中未出现该案号 — 待律师复核")


# ---------------------------------------------------------------------------
# Main verification entry point
# ---------------------------------------------------------------------------

async def verify_items(
    extracted: list[ExtractedCitation],
    retrievals: list[tuple[str, str]],
    law_library: LawLibrary | None = None,
) -> list[CitationAuditItem]:
    """Verify a list of extracted citations and return audit items.

    Dispatches each citation to the appropriate per-kind verifier.
    Ported from ``verify.rs:199-213``.

    Args:
        extracted: List of ``ExtractedCitation`` from ``extract_citations()``.
        retrievals: List of ``(tool_name, result_text)`` pairs from this
            turn's retrieval tools.
        law_library: Optional law library for authoritative verification.
            Defaults to ``None`` (all lookups fail → retrieval fallback).

    Returns:
        List of ``CitationAuditItem`` in the same order as *extracted*.
    """
    items: list[CitationAuditItem] = []
    for c in extracted:
        if c.kind == CitationKind.LAW:
            item = await verify_law_article(c, retrievals, law_library)
        elif c.kind == CitationKind.INTERPRETATION:
            item = await verify_interpretation(c, retrievals, law_library)
        else:
            item = verify_case(c, retrievals)
        items.append(item)
    return items


__all__ = [
    "ArticleLookup",
    "CitationAuditItem",
    "LawEntry",
    "LawLibrary",
    "verify_case",
    "verify_interpretation",
    "verify_items",
    "verify_law_article",
]
