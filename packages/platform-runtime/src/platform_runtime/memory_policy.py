"""Classification, retention, and focus policies for long-term memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from platform_contract.events import JsonObject

from .long_term_memory import MemoryPrivacyError


class MemoryCategory(StrEnum):
    """Durability category for a memory fragment."""

    USER_PREFERENCE = "user_preference"
    PROJECT_FACT = "project_fact"
    LESSON_LEARNED = "lesson_learned"
    TASK_DETAIL = "task_detail"
    TRANSIENT = "transient"


@dataclass(frozen=True, slots=True)
class MemoryContentClassification:
    """Result of classifying a piece of memory content."""

    category: MemoryCategory
    confidence: float = 1.0
    reason: str = ""
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryRetentionPolicy:
    """Policy controlling what content is retained as durable memory."""

    allowed_categories: tuple[MemoryCategory, ...] = (
        MemoryCategory.USER_PREFERENCE,
        MemoryCategory.PROJECT_FACT,
        MemoryCategory.LESSON_LEARNED,
    )
    extract_facts: bool = True
    min_confidence: float = 0.5
    default_category: MemoryCategory = MemoryCategory.TRANSIENT


@dataclass(frozen=True, slots=True)
class MemoryFocusPolicy:
    """Policy controlling what recalled memories are injected into the agent context."""

    max_results: int = 8
    minimum_relevance_score: float = 0.0
    required_categories: tuple[MemoryCategory, ...] = ()
    prefer_recent: bool = False


@dataclass(frozen=True, slots=True)
class MemoryRetentionDecision:
    """Outcome of a retain operation under a retention policy."""

    retained_count: int = 0
    discarded_count: int = 0
    classifications: tuple[MemoryContentClassification, ...] = ()
    reason: str = ""
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryFocusResult:
    """Outcome of a recall operation under a focus policy."""

    selected_count: int = 0
    filtered_count: int = 0
    selected_memory_ids: tuple[str, ...] = ()
    metadata: JsonObject = field(default_factory=dict)


class MemoryContentClassifier:
    """Rule-based classifier for durable vs transient memory content.

    This is intentionally lightweight and deterministic. It does not call an LLM.
    Callers may replace it with a more sophisticated classifier in later phases.
    """

    def __init__(self, *, default_category: MemoryCategory = MemoryCategory.TRANSIENT) -> None:
        self._default_category = default_category
        self._rules = [
            (MemoryCategory.USER_PREFERENCE, ("prefer", "like", "dislike", "always", "never", "favorite")),
            (MemoryCategory.PROJECT_FACT, ("project", "case", "client", "contract", "active case", "working on")),
            (MemoryCategory.LESSON_LEARNED, ("lesson", "learned", "should not", "must not", "avoid", "remember to")),
            (MemoryCategory.TASK_DETAIL, ("draft", "send", "file", "upload", "download", "today", "right now")),
        ]

    def classify(self, text: str, *, metadata: JsonObject | None = None) -> MemoryContentClassification:
        if not isinstance(text, str):
            raise MemoryPrivacyError("classifier input must be a string")
        lower = text.lower()
        scores: dict[MemoryCategory, int] = {}
        for category, keywords in self._rules:
            score = sum(1 for kw in keywords if kw in lower)
            if score:
                scores[category] = scores.get(category, 0) + score
        if not scores:
            return MemoryContentClassification(
                category=self._default_category,
                confidence=1.0,
                reason="no durable category keywords matched",
            )
        best_category = max(scores, key=lambda c: scores[c])
        best_score = scores[best_category]
        total = sum(scores.values())
        confidence = round(best_score / total, 2) if total else 0.0
        return MemoryContentClassification(
            category=best_category,
            confidence=confidence,
            reason=f"matched keywords: {best_category.value}",
        )

    def classify_all(
        self,
        texts: tuple[str, ...],
        *,
        metadata: JsonObject | None = None,
    ) -> tuple[MemoryContentClassification, ...]:
        return tuple(self.classify(text, metadata=metadata) for text in texts)
