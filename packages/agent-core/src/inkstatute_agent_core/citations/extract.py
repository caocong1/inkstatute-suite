"""Citation extraction from generated legal documents (pure functions).

A Python port of the Rust ``extract.rs`` from
``lawyer-desktop/src-tauri/src/citations/extract.rs`` (284 lines).

The prompt's 引用书写规范 is the contract: 《法名》第N条, 法释〔YYYY〕N号,
full case numbers like （2024）渝01民初1234号, and 入库案例编号.

Six module-level ``re.compile()`` patterns (Python equivalent of Rust
``OnceLock<Regex>``) extract:

1. **Law articles** — ``《法名》第N条`` with enumeration expansion (、和及与)
2. **Article list** — individual ``第N条`` references within a law match
3. **Interpretations** — ``法释〔YYYY〕N号`` with optional adjacent 《name》
4. **State Council decrees** — ``国务院令第N号`` with optional adjacent 《name》
5. **Case numbers** — full Chinese court case numbers with case-type suffixes
6. **DB case IDs** — ``YYYY-MM-D-NNN-NNN`` database case identifiers

No external dependencies — uses only the Python standard library (``re``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class CitationKind(Enum):
    """Kind of legal citation extracted from text.

    Serializes to lowercase strings ("law", "interpretation", "case")
    matching the Rust ``#[serde(rename_all = "lowercase")]`` attribute.
    """

    LAW = "law"
    INTERPRETATION = "interpretation"
    CASE = "case"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ExtractedCitation:
    """A single citation extracted from generated text.

    Attributes:
        kind: The ``CitationKind`` (Law / Interpretation / Case).
        source: 法名 (without 《》) for laws/interpretations; empty for
            bare case numbers.
        reference: 第N条 / 法释〔YYYY〕N号 / full case number / 入库编号.
    """

    kind: CitationKind
    source: str
    reference: str


# ---------------------------------------------------------------------------
# Module-level compiled regex patterns (Python equivalent of Rust OnceLock<Regex>)
# ---------------------------------------------------------------------------

_LAW_ARTICLE_RE = re.compile(
    r"《([^《》\n]{2,48})》\s*(第[零一二三四五六七八九十百千0-9]+条(?:之[一二三四五六七八九十])?(?:[、和及与]\s*第[零一二三四五六七八九十百千0-9]+条(?:之[一二三四五六七八九十])?)*)"
)

_ARTICLE_LIST_RE = re.compile(
    r"第[零一二三四五六七八九十百千0-9]+条(?:之[一二三四五六七八九十])?"
)

_INTERPRETATION_RE = re.compile(
    r"(?:《([^《》\n]{2,64})》[^《》\n]{0,12})?(法释[〔\[（(]\d{4}[〕\]）)]\d{1,3}号)"
)

_STATE_COUNCIL_DECREE_RE = re.compile(
    r"(?:《([^《》\n]{2,64})》[^《》\n]{0,12})?(国务院令第\d{1,4}号)"
)

_CASE_NUMBER_RE = re.compile(
    r"[（(]\d{4}[）)][一-龥]{1,8}\d{0,4}(?:民初|民终|民申|民再|民辖终|民特|民督|商初|商终|刑初|刑终|刑申|行初|行终|行申|行赔|执异|执复|执恢|执|知民初|知民终|知行终|破申|破|赔|仲|清申)\d{1,6}号"
)

_DB_CASE_ID_RE = re.compile(r"\d{4}-\d{2}-\d-\d{3}-\d{3}")


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

_BRACKET_OPEN_MAP = {"[": "〔", "（": "〔", "(": "〔"}
_BRACKET_CLOSE_MAP = {"]": "〕", "）": "〕", ")": "〕"}


def _normalize_doc_number(s: str) -> str:
    """Normalize bracket variants so 法释〔2020〕28号 == 法释[2020]28号 for dedup.

    Maps ``[``, ``（``, ``(`` → ``〔`` and ``]``, ``）``, ``)`` → ``〕``.
    Ported from ``extract.rs:80-88``.
    """
    result: list[str] = []
    for ch in s:
        if ch in _BRACKET_OPEN_MAP:
            result.append(_BRACKET_OPEN_MAP[ch])
        elif ch in _BRACKET_CLOSE_MAP:
            result.append(_BRACKET_CLOSE_MAP[ch])
        else:
            result.append(ch)
    return "".join(result)


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_citations(text: str) -> list[ExtractedCitation]:
    """Extract all citations from *text*, deduplicated, in first-occurrence order.

    Runs all 6 regex patterns over the text, deduplicates by
    ``(kind, source, reference)``, and preserves first-occurrence order.

    Ported from ``extract.rs:91-162``.

    Args:
        text: The generated legal document text to scan.

    Returns:
        A list of ``ExtractedCitation`` objects, deduplicated and ordered
        by first occurrence.
    """
    out: list[ExtractedCitation] = []
    seen: set[tuple[CitationKind, str, str]] = set()

    def push(c: ExtractedCitation) -> None:
        key = (c.kind, c.source, c.reference)
        if key not in seen:
            seen.add(key)
            out.append(c)

    # 1. Law articles — 《法名》第N条 (with enumeration expansion)
    for cap in _LAW_ARTICLE_RE.finditer(text):
        law = cap.group(1).strip()
        article_section = cap.group(2)
        for article_match in _ARTICLE_LIST_RE.finditer(article_section):
            push(ExtractedCitation(
                kind=CitationKind.LAW,
                source=law,
                reference=article_match.group(0),
            ))

    # 2. Interpretations — 法释〔YYYY〕N号 (with optional adjacent 《name》)
    for cap in _INTERPRETATION_RE.finditer(text):
        source = cap.group(1)
        push(ExtractedCitation(
            kind=CitationKind.INTERPRETATION,
            source=source.strip() if source else "",
            reference=_normalize_doc_number(cap.group(2)),
        ))

    # 3. State Council decrees — 国务院令第N号 (with optional adjacent 《name》)
    for cap in _STATE_COUNCIL_DECREE_RE.finditer(text):
        source = cap.group(1)
        push(ExtractedCitation(
            kind=CitationKind.INTERPRETATION,
            source=source.strip() if source else "",
            reference=cap.group(2),
        ))

    # 4. Case numbers — full court case numbers (normalize halfwidth → fullwidth)
    for m in _CASE_NUMBER_RE.finditer(text):
        normalized = m.group(0).replace("(", "（").replace(")", "）")
        push(ExtractedCitation(
            kind=CitationKind.CASE,
            source="",
            reference=normalized,
        ))

    # 5. DB case IDs — YYYY-MM-D-NNN-NNN
    for m in _DB_CASE_ID_RE.finditer(text):
        push(ExtractedCitation(
            kind=CitationKind.CASE,
            source="",
            reference=m.group(0),
        ))

    return out


__all__ = [
    "CitationKind",
    "ExtractedCitation",
    "extract_citations",
]
