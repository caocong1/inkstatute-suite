"""Legal guardrail orchestration + de-AI polish (designed fresh, no Rust source).

This module enforces the four legal guardrails at code level and implements
the de-AI polish post-processing guardrail.  The four guardrails are:

1. **research-gate** — ``enforce_research_gate()`` asserts the assembled system
   prompt always contains the research-gate section.  No code path may produce
   a legal prompt without it (SAFE-04).
2. **ask-user-enforcement** — ``enforce_ask_user_mandate()`` asserts Draft and
   Evidence mode prompts include the ``ask_user`` mandate.  Chat (Q&A) mode is
   exempt by design (CORE-08).
3. **citation audit** — ``enforce_citation_audit()`` always runs the citation
   audit after a final response and labels unverified citations with
   ``[待律师复核]`` (SAFE-04, CORE-08).  It delegates to the full
   ``citations.audit()`` when the ``citations`` sub-package is available
   (Plan 102-03); until then a conservative self-contained fallback runs so
   the guardrail is never bypassed.
4. **de-AI polish** — ``de_ai_polish()`` removes AI-characteristic language
   patterns while preserving legal meaning (citations, article numbers,
   conclusions).  Designed fresh — there is no Rust implementation
   (CORE-08).

This module also enforces the ``skill_candidate.requires_human_review``
safety invariant (SAFE-01): high-risk legal conclusions stay human-reviewed.
``create_skill_candidate()`` is the ONLY constructor for skill candidates and
always sets ``requires_human_review=True``; no code path auto-synthesizes or
auto-modifies legal conclusion skills.

Depends only on the Python standard library (``re``).  No new pip
dependencies.

HG-1 (法律质量) is NOT auto-closable — these functions enforce structural
guardrail presence, not prompt legal quality.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .prompt_assembler import AgentMode

# Re-export the citation audit types from the ``citations`` sub-package
# (Plan 102-03) when it is available, so callers use one canonical
# ``CitationAudit`` / ``CitationAuditItem``.  When the sub-package is absent,
# conservative fallback types are defined so the guardrail is never bypassed.
try:  # pragma: no cover - import availability depends on plan ordering
    from .citations import (  # type: ignore[attr-defined]
        CitationAudit,
        CitationAuditItem,
        audit as _citations_audit,
    )

    _CITATIONS_AVAILABLE = True
except ImportError:  # pragma: no cover - fallback when 102-03 not landed
    _CITATIONS_AVAILABLE = False

    @dataclass(frozen=True)
    class CitationAuditItem:  # type: ignore[no-redef]
        """Fallback citation audit item (used until ``citations`` lands)."""

        kind: str
        source: str
        reference: str
        status: str = "unverified"
        note: str = ""

    @dataclass(frozen=True)
    class CitationAudit:  # type: ignore[no-redef]
        """Fallback citation audit result (used until ``citations`` lands)."""

        items: list[CitationAuditItem] = field(default_factory=list)
        total: int = 0
        verified: int = 0
        retrieved: int = 0
        unverified: int = 0


# ---------------------------------------------------------------------------
# Guardrail result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GuardrailResult:
    """Result of verifying all four guardrails are present in a prompt.

    ``passed`` is True only when every guardrail is enforced.  When False,
    ``missing_guardrails`` lists the names of guardrails that were absent.
    """

    passed: bool
    missing_guardrails: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# SkillCandidate — dataclass with requires_human_review safety invariant
# ---------------------------------------------------------------------------


@dataclass
class SkillCandidate:
    """A candidate legal skill awaiting human review.

    ``requires_human_review`` is ALWAYS ``True`` — no code path may set it
    to ``False`` (SAFE-01).  High-risk legal conclusions never auto-synthesize
    or auto-modify skills without human review.
    """

    name: str
    description: str
    requires_human_review: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Guardrail 1 — research-gate enforcement (SAFE-04)
# ---------------------------------------------------------------------------


def enforce_research_gate(prompt: str) -> None:
    """Assert the assembled system prompt contains the research-gate section.

    Raises ``ValueError`` if ``"research-gate"`` is not present in *prompt*.
    This enforces Guardrail 1 — the research-gate is non-bypassable: no code
    path may produce a legal prompt without it.
    """
    if "research-gate" not in prompt:
        raise ValueError(
            "System prompt missing research-gate — legal safety violation"
        )


# ---------------------------------------------------------------------------
# Guardrail 2 — ask-user-enforcement (CORE-08)
# ---------------------------------------------------------------------------


def enforce_ask_user_mandate(prompt: str, mode: AgentMode) -> None:
    """Assert Draft/Evidence prompts include the ``ask_user`` mandate.

    Chat (Q&A) mode is exempt by design — Q&A does not mandate ``ask_user``
    because the agent should answer rather than stop to clarify.

    Raises ``ValueError`` when *mode* is ``DRAFT`` or ``EVIDENCE`` and
    ``"ask_user"`` is not present in *prompt*.
    """
    if mode in (AgentMode.DRAFT, AgentMode.EVIDENCE):
        if "ask_user" not in prompt:
            raise ValueError(
                f"{mode.value} prompt missing ask_user mandate — "
                "legal safety violation"
            )


# ---------------------------------------------------------------------------
# Guardrail 3 — citation audit (SAFE-04, CORE-08)
# ---------------------------------------------------------------------------

# Conservative citation-extraction regexes for the fallback audit path.
# These are a minimal subset; the full 6-pattern extractor lives in the
# ``citations`` sub-package (Plan 102-03).  When that package is available,
# ``enforce_citation_audit`` delegates to its ``audit()``.
_FALLBACK_LAW_ARTICLE_RE = re.compile(
    r"《([^《》\n]{2,48})》\s*(第[零一二三四五六七八九十百千0-9]+条(?:之[一二三四五六七八九十])?)"
)
_FALLBACK_CASE_NUMBER_RE = re.compile(
    r"（(\d{4})）[^\s（)]{2,12}[^\s]*?号"
)
_REVIEW_MARKER = "待律师复核"


def _fallback_citation_audit(
    text: str,
    retrievals: list[tuple[str, str]] | None,
) -> CitationAudit:
    """Self-contained citation audit used until the ``citations`` package lands.

    Extracts law-article and case-number citations, checks each against the
    provided *retrievals* (list of ``(label, content)`` tuples), and labels
    citations not found in any retrieval as ``unverified`` with a
    ``待律师复核`` note.
    """
    retrievals = retrievals or []
    items: list[CitationAuditItem] = []

    for match in _FALLBACK_LAW_ARTICLE_RE.finditer(text):
        source, reference = match.group(1), match.group(2)
        citation_text = match.group(0)
        found = any(citation_text in content for _, content in retrievals)
        if found:
            status, note = "retrieved", ""
        else:
            status, note = "unverified", _REVIEW_MARKER
        items.append(
            CitationAuditItem(
                kind="law",
                source=source,
                reference=reference,
                status=status,
                note=note,
            )
        )

    for match in _FALLBACK_CASE_NUMBER_RE.finditer(text):
        reference = match.group(0)
        found = any(reference in content for _, content in retrievals)
        if found:
            status, note = "retrieved", ""
        else:
            status, note = "unverified", _REVIEW_MARKER
        items.append(
            CitationAuditItem(
                kind="case",
                source="",
                reference=reference,
                status=status,
                note=note,
            )
        )

    # Dedup by (kind, source, reference) preserving first-occurrence order.
    seen: set[tuple[str, str, str]] = set()
    deduped: list[CitationAuditItem] = []
    for item in items:
        key = (item.kind, item.source, item.reference)
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    verified = sum(1 for i in deduped if i.status == "verified")
    retrieved = sum(1 for i in deduped if i.status == "retrieved")
    unverified = sum(1 for i in deduped if i.status == "unverified")

    return CitationAudit(
        items=deduped,
        total=len(deduped),
        verified=verified,
        retrieved=retrieved,
        unverified=unverified,
    )


async def enforce_citation_audit(
    text: str,
    retrievals: list[tuple[str, str]] | None = None,
    law_library: Any = None,
) -> CitationAudit:
    """Run the citation audit guardrail (Guardrail 3) and return the result.

    The audit is annotation-style — it never blocks output — but it MUST
    always execute.  Unverified citations carry a ``待律师复核`` note on
    their ``CitationAuditItem``.

    When the ``citations`` sub-package (Plan 102-03) is importable, this
    delegates to its async ``audit()`` for the full 6-regex extraction and
    three-state verification.  Until then the conservative sync fallback runs
    so the guardrail is never bypassed.

    This is a coroutine — callers (the turn loop, wired in 102-05) await it
    after every final response.
    """
    if _CITATIONS_AVAILABLE:
        return await _citations_audit(text, retrievals or [], law_library)
    return _fallback_citation_audit(text, retrievals)


# ---------------------------------------------------------------------------
# Guardrail 4 — de-AI polish (designed fresh, no Rust source) (CORE-08)
# ---------------------------------------------------------------------------

# Conservative AI-characteristic language patterns.  Each entry is a
# ``(regex, replacement)`` tuple.  The set is deliberately conservative —
# over-aggressive polishing could alter legal meaning.  Patterns only
# remove AI self-references, hedging disclaimers, and "not legal advice"
# boilerplate; legal citations, article numbers, and conclusions are
# preserved.
_AI_PATTERNS: list[tuple[str, str]] = [
    # AI self-reference introductions
    (r"作为一个AI(?:助手)?[,，]?\s*", ""),
    (r"作为AI[,，]?\s*", ""),
    (r"作为(?:一个)?人工智能[,，]?\s*", ""),
    (r"请注意[,，]?\s*我是(?:一个)?AI[，,]?\s*", ""),
    # Hedging phrases that add no legal value
    (r"根据我的理解[,，]?\s*", ""),
    (r"据我所知[,，]?\s*", ""),
    # "I cannot provide legal advice" disclaimers
    (r"我无法(?:提供|给出)[^。]*法律建议[。.]?\s*", ""),
    # "The above is for reference only, not legal advice" boilerplate
    (r"以上(?:分析|建议|内容)仅供参考[,，]?\s*不构成法律建议[。.]?\s*", ""),
    (r"以上(?:分析|建议|内容)仅供参考[。.]?\s*", ""),
    # "I am an AI, I cannot" → preserve the "cannot" meaning, drop AI self-ref
    (r"我(?:是|作为一个)AI[,，]?\s*无法", "无法"),
    # Trailing standalone AI disclaimers
    (r"请注意[,，]?\s*本(?:回答|内容|分析)由AI生成[。.]?\s*", ""),
    (r"本(?:回答|内容|分析)由AI生成[,，]?\s*仅供参考[。.]?\s*", ""),
]


def de_ai_polish(text: str) -> str:
    """Remove AI-characteristic language patterns from *text*.

    Post-processing guardrail (Guardrail 4) that runs after the citation
    audit.  Removes AI self-references, hedging disclaimers, and "not legal
    advice" boilerplate while preserving legal meaning — citations, article
    numbers, and conclusions are never altered.

    After pattern removal, 3+ consecutive newlines left by removals are
    collapsed to 2 and the result is stripped.  Uses ``re.IGNORECASE``.
    """
    result = text
    for pattern, replacement in _AI_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    # Collapse 3+ consecutive newlines to 2 (blank lines left by removals).
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


# ---------------------------------------------------------------------------
# Guardrail verification — all four guardrails present in a prompt
# ---------------------------------------------------------------------------


def verify_guardrails(prompt: str, mode: AgentMode) -> GuardrailResult:
    """Verify all four guardrails are present/enforceable for *prompt* + *mode*.

    Returns a ``GuardrailResult``.  ``passed`` is True only when:
    - the research-gate section is present (Guardrail 1), and
    - the ask-user mandate is present for Draft/Evidence modes (Guardrail 2).

    Guards 3 (citation audit) and 4 (de-AI polish) are post-processing
    guardrails enforced by ``enforce_citation_audit()`` and ``de_ai_polish()``
    at runtime — their presence is confirmed by the functions existing, not
    by prompt content.  They are listed as enforced when the prompt-level
    guards pass.
    """
    missing: list[str] = []

    if "research-gate" not in prompt:
        missing.append("research-gate")
    if mode in (AgentMode.DRAFT, AgentMode.EVIDENCE) and "ask_user" not in prompt:
        missing.append("ask-user-enforcement")

    return GuardrailResult(
        passed=len(missing) == 0,
        missing_guardrails=missing,
    )


# ---------------------------------------------------------------------------
# SAFE-01 — skill_candidate.requires_human_review safety invariant
# ---------------------------------------------------------------------------


def assert_skill_candidate_safety(candidate: dict[str, Any]) -> None:
    """Assert ``candidate["requires_human_review"]`` is ``True``.

    Raises ``ValueError`` when the field is missing or ``False``.  This
    enforces SAFE-01 — high-risk legal conclusions stay human-reviewed.
    """
    if not candidate.get("requires_human_review", False):
        raise ValueError(
            "skill_candidate.requires_human_review must be True — "
            "legal safety violation"
        )


def create_skill_candidate(
    name: str,
    description: str,
    **kwargs: Any,
) -> SkillCandidate:
    """Create a ``SkillCandidate`` with ``requires_human_review=True``.

    This is the ONLY constructor for skill candidates — no code path
    auto-synthesizes skills.  Any attempt to override
    ``requires_human_review`` to ``False`` raises ``ValueError`` (SAFE-01).
    Extra keyword arguments are stored in the ``extra`` dict.
    """
    if kwargs.get("requires_human_review") is False:
        raise ValueError(
            "skill_candidate.requires_human_review must be True — "
            "legal safety violation"
        )
    requires_human_review = bool(kwargs.pop("requires_human_review", True))
    return SkillCandidate(
        name=name,
        description=description,
        requires_human_review=requires_human_review,
        extra=dict(kwargs),
    )


__all__ = [
    "CitationAudit",
    "CitationAuditItem",
    "GuardrailResult",
    "SkillCandidate",
    "apply_de_ai_polish",
    "assert_skill_candidate_safety",
    "create_skill_candidate",
    "de_ai_polish",
    "enforce_ask_user_mandate",
    "enforce_citation_audit",
    "enforce_research_gate",
    "verify_guardrails",
]


# ``apply_de_ai_polish`` is a public alias for ``de_ai_polish`` so callers can
# reference the guardrail by its descriptive name.
apply_de_ai_polish = de_ai_polish
