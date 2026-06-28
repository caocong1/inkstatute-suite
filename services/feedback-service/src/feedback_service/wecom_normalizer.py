"""Minimal WeCom feedback normalizer for Phase 5 validation fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class FeedbackNormalizationIssue:
    code: str
    message: str
    feedback_ref: str | None = None
    path: str | None = None


@dataclass(frozen=True)
class NormalizedFeedbackBatch:
    events: list[dict[str, Any]]
    issues: list[FeedbackNormalizationIssue]


def normalize_wecom_feedback_records(
    feedback_records: list[Mapping[str, Any]],
    preview_records: list[Mapping[str, Any]],
    *,
    now: str | None = None,
) -> NormalizedFeedbackBatch:
    """Normalize sanitized Hermes feedback records into FeedbackEvent payloads."""

    del feedback_records, preview_records, now
    return NormalizedFeedbackBatch(events=[], issues=[])


__all__ = [
    "FeedbackNormalizationIssue",
    "NormalizedFeedbackBatch",
    "normalize_wecom_feedback_records",
]
