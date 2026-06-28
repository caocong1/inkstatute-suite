"""Rule-based FeedbackEvent classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


FEEDBACK_CATEGORIES = {
    "rating",
    "correction",
    "fact_missing",
    "citation_error",
    "route_mismatch",
    "format_issue",
    "compliance_issue",
    "skill_candidate",
}


@dataclass(frozen=True)
class FeedbackClassification:
    category: str
    reason: str
    labels: list[str] = field(default_factory=list)
    requires_human_review: bool = False
    no_auto_modify: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "reason": self.reason,
            "labels": list(self.labels),
            "requires_human_review": self.requires_human_review,
            "no_auto_modify": self.no_auto_modify,
        }


def classify_feedback_event(event: Mapping[str, Any]) -> FeedbackClassification:
    labels = _labels(event)
    message = _string(event.get("message"))
    event_type = _string(event.get("event_type"))
    action = _string(event.get("action"))
    skill_candidate = event.get("skill_candidate")

    if bool(event.get("route_mismatch")) or event_type == "route_mismatch" or "route_mismatch" in labels:
        return _human_review("route_mismatch", "route mismatch evidence", labels)
    if event_type == "skill_candidate" or "skill_candidate" in labels or isinstance(skill_candidate, Mapping):
        return _human_review("skill_candidate", "skill candidate evidence", labels)

    label_category = _category_from_labels(labels)
    if label_category is not None:
        return FeedbackClassification(category=label_category, reason="label match", labels=labels)

    message_category = _category_from_message(message)
    if message_category is not None:
        return FeedbackClassification(category=message_category, reason="message hint", labels=labels)

    if action == "up":
        return FeedbackClassification(category="rating", reason="positive button action", labels=labels)
    if action in {"down", "needs_fix"}:
        return FeedbackClassification(category="correction", reason="negative or fix button action", labels=labels)
    if event_type in FEEDBACK_CATEGORIES:
        return FeedbackClassification(category=event_type, reason="event_type", labels=labels)
    return FeedbackClassification(category="correction", reason="default fallback", labels=labels)


def _human_review(category: str, reason: str, labels: list[str]) -> FeedbackClassification:
    return FeedbackClassification(
        category=category,
        reason=reason,
        labels=labels,
        requires_human_review=True,
        no_auto_modify=True,
    )


def _category_from_labels(labels: list[str]) -> str | None:
    for label in labels:
        normalized = label.replace("-", "_")
        if normalized in FEEDBACK_CATEGORIES:
            return normalized
        if normalized in {"missing_fact", "missing_facts", "fact_gap"}:
            return "fact_missing"
        if normalized in {"bad_citation", "citation_missing", "wrong_citation"}:
            return "citation_error"
        if normalized in {"format", "formatting"}:
            return "format_issue"
        if normalized in {"compliance", "policy"}:
            return "compliance_issue"
    return None


def _category_from_message(message: str | None) -> str | None:
    if message is None:
        return None
    lowered = message.lower()
    if "citation" in lowered or "cite" in lowered or "引用" in lowered:
        return "citation_error"
    if "fact" in lowered or "事实" in lowered:
        return "fact_missing"
    if "format" in lowered or "格式" in lowered:
        return "format_issue"
    if "compliance" in lowered or "合规" in lowered:
        return "compliance_issue"
    return None


def _labels(event: Mapping[str, Any]) -> list[str]:
    raw_labels = event.get("labels")
    if not isinstance(raw_labels, list):
        return []
    return [label for label in (_string(item) for item in raw_labels) if label is not None]


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text.lower() if text else None


__all__ = [
    "FEEDBACK_CATEGORIES",
    "FeedbackClassification",
    "classify_feedback_event",
]

