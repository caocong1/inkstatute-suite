"""Legal-risk classifier for the HYBRID routing strategy.

Provides a ``LegalRiskClassifierPort`` Protocol and a default keyword-based
implementation (``KeywordLegalRiskClassifier``) that classifies user
messages into low / medium / high legal-risk levels.  When a query is
classified as high-risk, the HYBRID strategy forces routing to Hermes
regardless of the confidence score produced by the Rule → Skill → Model
cascade.

The classifier is pure and stateless, matching the pattern of
``classifier.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class LegalRiskLevel(StrEnum):
    """Legal-risk classification levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class LegalRiskAssessment:
    """Result of classifying a message for legal risk.

    ``is_high_risk`` is the primary signal consumed by the HYBRID strategy.
    ``evidence`` lists the matched keywords that triggered the assessment.
    ``metadata`` is an open dict for host-injected classifiers to attach
    additional diagnostics.
    """

    risk_level: str
    is_high_risk: bool
    evidence: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class LegalRiskClassifierPort(Protocol):
    """Protocol for injectable legal-risk classifiers.

    Implementations must be stateless and side-effect free.  When no
    classifier is injected (``None``), the HYBRID strategy skips the
    legal-risk override.
    """

    def classify(self, message: str | None) -> LegalRiskAssessment:
        """Classify *message* into a legal-risk level."""
        ...


# High-risk keywords — queries that carry significant legal risk if
# answered incorrectly or routed to a weak/cheap model.
HIGH_RISK_KEYWORDS: list[str] = [
    # Chinese
    "诉讼", "起诉", "仲裁", "判决", "法律意见", "合规审查",
    "赔偿", "犯罪", "刑事", "合同审查", "合同起草", "法律风险",
    "上诉", "抗诉", "立案", "庭审", "证据保全",
    # English
    "litigation", "lawsuit", "arbitration", "judgment", "legal opinion",
    "compliance review", "criminal", "compensation", "legal risk",
    "appeal", "indictment", "trial", "evidence preservation",
]

# Medium-risk keywords — legal-adjacent queries that are not inherently
# high-risk but warrant closer attention.
MEDIUM_RISK_KEYWORDS: list[str] = [
    # Chinese
    "合同", "法律", "法规", "条款", "权利", "义务", "违约",
    # English
    "contract", "legal", "law", "regulation", "clause",
    "rights", "obligations", "breach",
]


class KeywordLegalRiskClassifier:
    """Default keyword-based legal-risk classifier.

    Matches high-risk and medium-risk keywords against the message using
    the same pattern as ``classifier.classify_intent``: Chinese keywords
    are matched as substrings; English keywords are matched with ``\\b``
    word boundaries to avoid false substring matches.
    """

    def classify(self, message: str | None) -> LegalRiskAssessment:
        """Classify *message* into a legal-risk level.

        Returns ``LegalRiskAssessment`` with ``is_high_risk=True`` if any
        high-risk keyword matches.  If no high-risk keyword matches but a
        medium-risk keyword does, returns ``risk_level="medium"``.  For
        empty/``None`` messages or no keyword matches, returns
        ``risk_level="low"``.
        """
        if not message:
            return LegalRiskAssessment(
                risk_level=LegalRiskLevel.LOW.value,
                is_high_risk=False,
                evidence=[],
            )

        high_evidence = _match_keywords(message, HIGH_RISK_KEYWORDS)
        if high_evidence:
            return LegalRiskAssessment(
                risk_level=LegalRiskLevel.HIGH.value,
                is_high_risk=True,
                evidence=high_evidence,
                metadata={"matched_keywords": high_evidence},
            )

        medium_evidence = _match_keywords(message, MEDIUM_RISK_KEYWORDS)
        if medium_evidence:
            return LegalRiskAssessment(
                risk_level=LegalRiskLevel.MEDIUM.value,
                is_high_risk=False,
                evidence=medium_evidence,
                metadata={"matched_keywords": medium_evidence},
            )

        return LegalRiskAssessment(
            risk_level=LegalRiskLevel.LOW.value,
            is_high_risk=False,
            evidence=[],
        )


def _match_keywords(message: str, keywords: list[str]) -> list[str]:
    """Return the list of keywords from *keywords* that match *message*."""
    matched: list[str] = []
    for keyword in keywords:
        if _is_ascii(keyword):
            pattern = rf"\b{re.escape(keyword)}\b"
        else:
            pattern = re.escape(keyword)
        if re.search(pattern, message, re.IGNORECASE):
            matched.append(keyword)
    return matched


def _is_ascii(text: str) -> bool:
    """Return True if *text* contains only ASCII characters."""
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


__all__ = [
    "KeywordLegalRiskClassifier",
    "LegalRiskAssessment",
    "LegalRiskClassifierPort",
    "LegalRiskLevel",
]
