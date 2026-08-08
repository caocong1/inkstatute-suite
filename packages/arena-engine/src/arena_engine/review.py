"""Structured review output primitives for Modes 3+4 (SAFE-06).

Defines the structured review output format used by Mode 3 (Arena Review)
and Mode 4 (Adversarial) cross-review phases:

- ``ConfidenceLevel`` — categorical confidence (Certain/Likely/Possible),
  NOT numeric percentages (binding research anti-pattern).
- ``SeverityLevel`` — finding severity (High/Medium/Low).
- ``ReviewFinding`` — frozen slotted dataclass with description, confidence,
  severity, confirmed/disproved marking, source/reviewed slot, and metadata.
- ``_parse_review_findings`` — regex parser that extracts ``[FINDING]``
  blocks from agent output text.

ENGINE-05: this module imports zero LLM provider packages.
ENGINE-06: this module never calls ``session/resume`` or
``resume_session``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Categorical confidence (NOT numeric percentages)
# ---------------------------------------------------------------------------


class ConfidenceLevel(Enum):
    """Categorical confidence levels for review findings.

    Confidence is categorical — Certain, Likely, or Possible — never a
    numeric percentage.  Numeric confidence strings (e.g. ``"67%"``) are
    rejected by the parser and fall back to ``POSSIBLE``.
    """

    CERTAIN = "Certain"
    LIKELY = "Likely"
    POSSIBLE = "Possible"


class SeverityLevel(Enum):
    """Severity levels for review findings."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


# ---------------------------------------------------------------------------
# ReviewFinding — frozen slotted dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    """A single structured review finding from a cross-review phase.

    Fields
    ------
    description
        Human-readable description of the finding.
    confidence
        Categorical confidence (Certain/Likely/Possible) — never numeric.
    severity
        Finding severity (High/Medium/Low).
    confirmed
        Whether the finding was confirmed (True) or disproved (False).
    source_slot
        The reviewer slot that produced this finding.
    reviewed_slot
        The slot whose output was reviewed.
    metadata
        Additional structured metadata (default empty dict).
    """

    description: str
    confidence: ConfidenceLevel
    severity: SeverityLevel
    confirmed: bool
    source_slot: str
    reviewed_slot: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        """Serialize to a plain dict compatible with ``ArenaReviewCompletedPayload.findings``.

        Enum values are serialized as their string ``.value`` so the
        output is JSON-safe and compatible with
        ``ArenaReviewCompletedPayload.findings: list[JsonObject]``.
        """
        return {
            "description": self.description,
            "confidence": self.confidence.value,
            "severity": self.severity.value,
            "confirmed": self.confirmed,
            "source_slot": self.source_slot,
            "reviewed_slot": self.reviewed_slot,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_json(d: dict[str, Any]) -> ReviewFinding:
        """Deserialize from a plain dict (round-trip with :meth:`to_json`)."""
        return ReviewFinding(
            description=d["description"],
            confidence=ConfidenceLevel(d["confidence"]),
            severity=SeverityLevel(d["severity"]),
            confirmed=d["confirmed"],
            source_slot=d["source_slot"],
            reviewed_slot=d["reviewed_slot"],
            metadata=dict(d.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# Finding-block parser
# ---------------------------------------------------------------------------

# Matches [FINDING]...[/FINDING] blocks (case-insensitive tags).
_FINDING_BLOCK_RE = re.compile(
    r"\[FINDING\]\s*(.*?)\s*\[/FINDING\]",
    re.DOTALL | re.IGNORECASE,
)

# Matches "key: value" lines within a finding block (case-insensitive keys).
_KV_LINE_RE = re.compile(r"^(\w+)\s*[:：]\s*(.+)$")


def _match_confidence(raw: str) -> ConfidenceLevel:
    """Case-insensitively match a confidence string to a ``ConfidenceLevel``.

    Numeric percentages (e.g. ``"67%"``) do NOT match any enum value and
    fall back to ``ConfidenceLevel.POSSIBLE``.
    """
    normalized = raw.strip().lower()
    for level in ConfidenceLevel:
        if level.value.lower() == normalized:
            return level
    return ConfidenceLevel.POSSIBLE


def _match_severity(raw: str) -> SeverityLevel:
    """Case-insensitively match a severity string to a ``SeverityLevel``."""
    normalized = raw.strip().lower()
    for level in SeverityLevel:
        if level.value.lower() == normalized:
            return level
    return SeverityLevel.MEDIUM


def _parse_bool(raw: str) -> bool:
    """Parse a boolean from a string: true/yes/1 → True, else False."""
    return raw.strip().lower() in {"true", "yes", "1"}


def _parse_review_findings(
    content: str,
    source_slot: str,
    reviewed_slot: str,
) -> list[ReviewFinding]:
    """Extract structured :class:`ReviewFinding` objects from agent output.

    Scans *content* for ``[FINDING]...[/FINDING]`` blocks.  Within each
    block, parses ``key: value`` lines (case-insensitive keys).  Supported
    keys: ``description``, ``confidence``, ``severity``, ``confirmed``.

    Defaults for missing fields:
    - ``confidence`` → ``ConfidenceLevel.POSSIBLE``
    - ``severity`` → ``SeverityLevel.MEDIUM``
    - ``confirmed`` → ``False``
    - ``description`` → ``""`` (empty string)

    Numeric confidence strings (e.g. ``"67%"``) are rejected and fall
    back to ``POSSIBLE`` — categorical confidence only.

    Returns an empty list when no ``[FINDING]`` blocks are present.
    """
    findings: list[ReviewFinding] = []
    for block_match in _FINDING_BLOCK_RE.finditer(content):
        block_text = block_match.group(1)
        kv: dict[str, str] = {}
        for line in block_text.splitlines():
            line = line.strip()
            if not line:
                continue
            kv_match = _KV_LINE_RE.match(line)
            if kv_match:
                key = kv_match.group(1).lower()
                value = kv_match.group(2).strip()
                kv[key] = value

        description = kv.get("description", "")
        confidence = _match_confidence(kv.get("confidence", ""))
        severity = _match_severity(kv.get("severity", ""))
        confirmed = _parse_bool(kv.get("confirmed", ""))

        findings.append(
            ReviewFinding(
                description=description,
                confidence=confidence,
                severity=severity,
                confirmed=confirmed,
                source_slot=source_slot,
                reviewed_slot=reviewed_slot,
            )
        )
    return findings


__all__ = [
    "ConfidenceLevel",
    "ReviewFinding",
    "SeverityLevel",
    "_parse_review_findings",
]
