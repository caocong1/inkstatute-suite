"""GuardrailBoundary — post-hoc citation audit + de-AI polish + high-risk review.

This module enforces the legal guardrails at the arena-engine boundary for
external ACP agents (SAFE-01..04).  External agents (Hermes, Codex, Claude
Code, Gemini CLI) do not run the v3.0 guardrails internally, so the arena
engine applies them post-hoc:

1. **Citation audit** (SAFE-02) — ``enforce_citation_audit()`` from
   ``inkstatute_agent_core.guardrails`` runs the full citation extraction
   and three-state verification.
2. **De-AI polish** (SAFE-03) — ``de_ai_polish()`` removes AI-characteristic
   language patterns while preserving legal meaning.
3. **High-risk review** (SAFE-04) — ``_is_high_risk_legal_conclusion()``
   detects high-risk legal keywords and sets ``requires_human_review=True``.

Self-built agents (``is_external=False``) skip post-hoc guardrails because
the v3.0 guardrails already run inside ``turn_loop.py`` — no double
execution (SAFE-01).

The boundary is **non-bypassable**: ``apply_post_hoc_guardrails`` is the
ONLY public entry point for external agent content, and when
``is_external=True`` it always calls ``enforce_citation_audit`` and
``de_ai_polish``.  There is no skip or fast path for external agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from inkstatute_agent_core.citations import CitationAudit
from inkstatute_agent_core.guardrails import de_ai_polish, enforce_citation_audit

# ---------------------------------------------------------------------------
# High-risk legal conclusion keywords (SAFE-04)
# ---------------------------------------------------------------------------

_HIGH_RISK_KEYWORDS: frozenset[str] = frozenset(
    {
        "违法",
        "无效",
        "撤销",
        "解除",
        "赔偿",
        "刑事责任",
        "犯罪",
        "构成犯罪",
        "合同无效",
        "法律无效",
    }
)


def _is_high_risk_legal_conclusion(text: str) -> bool:
    """Return True if any high-risk keyword appears in *text*.

    High-risk legal conclusions (违法, 无效, 撤销, etc.) always set
    ``requires_human_review=True`` — they never auto-synthesize or
    auto-modify without human review (SAFE-04).
    """
    return any(keyword in text for keyword in _HIGH_RISK_KEYWORDS)


# ---------------------------------------------------------------------------
# GuardrailResult — frozen slotted dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GuardrailResult:
    """Result of applying post-hoc guardrails to external agent content.

    Attributes:
        polished_content: Content after de-AI polish.
        citation_audit: ``CitationAudit`` result or ``None`` when skipped.
        requires_human_review: True when high-risk keywords detected.
        skipped: True when self-built agent (guardrails in turn_loop).
        reason: Skip reason or ``None`` when guardrails were applied.
        metadata: Additional metadata (citation counts, etc.).
    """

    polished_content: str
    citation_audit: Any | None
    requires_human_review: bool
    skipped: bool
    reason: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# apply_post_hoc_guardrails — the ONLY public entry point (non-bypassable)
# ---------------------------------------------------------------------------


async def apply_post_hoc_guardrails(
    *,
    content: str,
    retrievals: list[tuple[str, str]] | None = None,
    is_external: bool = True,
) -> GuardrailResult:
    """Apply post-hoc guardrails to agent content at the arena boundary.

    When ``is_external=True`` (external ACP agents), this ALWAYS runs:
    1. ``enforce_citation_audit(content, retrievals)`` — citation audit
    2. ``de_ai_polish(content)`` — de-AI polish
    3. ``_is_high_risk_legal_conclusion(content)`` — high-risk detection

    There is no skip or fast path for external agents — the guardrails
    are non-bypassable (SAFE-01).

    When ``is_external=False`` (self-built agents), guardrails already run
    inside ``turn_loop.py``, so post-hoc application is skipped to avoid
    double execution.
    """
    if not is_external:
        return GuardrailResult(
            polished_content=content,
            citation_audit=None,
            requires_human_review=False,
            skipped=True,
            reason="self_built_agent_guardrails_in_turn_loop",
        )

    # External agent — always apply citation audit + de-AI polish (non-bypassable)
    citation_audit: CitationAudit = await enforce_citation_audit(
        content, retrievals
    )
    polished_content = de_ai_polish(content)
    requires_human_review = _is_high_risk_legal_conclusion(content)

    return GuardrailResult(
        polished_content=polished_content,
        citation_audit=citation_audit,
        requires_human_review=requires_human_review,
        skipped=False,
        reason=None,
        metadata={
            "citation_total": citation_audit.total,
            "citation_verified": citation_audit.verified,
            "citation_unverified": citation_audit.unverified,
        },
    )


__all__ = [
    "GuardrailResult",
    "apply_post_hoc_guardrails",
]
