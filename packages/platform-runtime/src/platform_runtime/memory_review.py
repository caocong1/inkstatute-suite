"""Human-review layer for memory candidates produced by FeedbackLearningPolicy."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from platform_contract.events import MemoryCandidate, MemoryRecord

from .session_resolver import _json_clone, _new_id, _sha16, _timestamp


class MemoryCandidateReviewAction(str, Enum):
    """Possible review decisions for a pending memory candidate."""

    approve = "approve"
    reject = "reject"
    edit = "edit"
    tombstone = "tombstone"
    defer = "defer"


class ReviewDeciderError(ValueError):
    """Raised when the decider encounters an invalid or unsafe review request."""


@dataclass(frozen=True, slots=True)
class MemoryCandidateReview:
    """A single human review decision applied to a memory candidate."""

    review_id: str
    candidate_id: str
    action: MemoryCandidateReviewAction
    reviewer_id: str | None = None
    reviewed_at: str | None = None
    rejection_reason: str | None = None
    edited_summary: str | None = None
    """Replacement summary written by a human reviewer; no raw legal text allowed."""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryCandidateReviewDecision:
    """Outcome of a review decision applied by MemoryCandidateReviewDecider."""

    review: MemoryCandidateReview
    promoted_memory_record: MemoryRecord | None = None
    promotion_status: str = "pending"
    """One of: promoted, rejected, tombstoned, deferred, already_resolved."""


class InMemoryMemoryCandidateReviewStore:
    """Lightweight in-memory queue for pending and resolved memory candidates."""

    def __init__(self) -> None:
        self._pending: dict[str, MemoryCandidate] = {}
        self._resolved: dict[str, MemoryCandidate] = {}
        self._reviews: dict[str, list[MemoryCandidateReview]] = {}

    def queue(self, candidate: MemoryCandidate) -> None:
        """Queue a candidate for review. Idempotent on candidate_id."""
        if candidate.candidate_id in self._pending or candidate.candidate_id in self._resolved:
            return
        self._pending[candidate.candidate_id] = candidate

    def queue_many(self, candidates: Iterable[MemoryCandidate]) -> None:
        for candidate in candidates:
            self.queue(candidate)

    def get(self, candidate_id: str) -> MemoryCandidate | None:
        return self._pending.get(candidate_id) or self._resolved.get(candidate_id)

    def get_pending(
        self,
        *,
        tenant_id: str,
        workspace_id: str | None = None,
    ) -> tuple[MemoryCandidate, ...]:
        results = []
        for candidate in self._pending.values():
            if candidate.tenant_id != tenant_id:
                continue
            if workspace_id is not None and candidate.workspace_id != workspace_id:
                continue
            results.append(candidate)
        return tuple(results)

    def is_resolved(self, candidate_id: str) -> bool:
        return candidate_id in self._resolved

    def resolve(self, candidate_id: str, review: MemoryCandidateReview) -> None:
        """Move candidate from pending → resolved and attach review."""
        candidate = self._pending.pop(candidate_id, None)
        if candidate is None:
            candidate = self._resolved.get(candidate_id)
        if candidate is not None:
            self._resolved[candidate_id] = candidate
        self._reviews.setdefault(candidate_id, []).append(review)

    def get_reviews(self, candidate_id: str) -> tuple[MemoryCandidateReview, ...]:
        return tuple(self._reviews.get(candidate_id, []))

    def list_resolved(self, *, tenant_id: str) -> tuple[MemoryCandidate, ...]:
        return tuple(c for c in self._resolved.values() if c.tenant_id == tenant_id)


class MemoryCandidateReviewDecider:
    """Apply review decisions against pending memory candidates.

    On ``approve`` or ``edit``, the candidate is promoted to a durable
    ``MemoryRecord`` via the bound memory store.  ``reject`` and ``tombstone``
    record the decision without writing a recall-visible record.  ``defer``
    leaves the candidate in the pending queue.

    High-risk routing and skill candidates (``proposed_action ==
    "review_route_or_skill_candidate"``) may only be ``defer``-ed; any other
    action raises ``ReviewDeciderError``.
    """

    def __init__(
        self,
        *,
        memory_store: Any,
        review_store: InMemoryMemoryCandidateReviewStore,
        clock: Any | None = None,
        id_factory: Any | None = None,
    ) -> None:
        self._memory_store = memory_store
        self._review_store = review_store
        self._clock = clock
        self._id_factory = id_factory

    def decide(
        self,
        *,
        candidate_id: str,
        action: MemoryCandidateReviewAction,
        reviewer_id: str | None = None,
        rejection_reason: str | None = None,
        edited_summary: str | None = None,
    ) -> MemoryCandidateReviewDecision:
        """Apply a review decision to the named candidate.

        Args:
            candidate_id: The candidate to review.
            action: One of approve, reject, edit, tombstone, defer.
            reviewer_id: Optional identifier of the human reviewer.
            rejection_reason: Required for ``reject``; recorded in review.
            edited_summary: Replacement summary for ``edit``; human-authored only.

        Returns:
            MemoryCandidateReviewDecision with promoted_memory_record when applicable.

        Raises:
            ReviewDeciderError: On candidate_not_found or routing_candidate guard.
        """
        candidate = self._review_store.get(candidate_id)
        if candidate is None:
            raise ReviewDeciderError(f"candidate_not_found: {candidate_id!r}")

        # Idempotency: already resolved
        if self._review_store.is_resolved(candidate_id) and action is not MemoryCandidateReviewAction.defer:
            reviews = self._review_store.get_reviews(candidate_id)
            last_review = reviews[-1] if reviews else MemoryCandidateReview(
                review_id="n/a",
                candidate_id=candidate_id,
                action=action,
            )
            return MemoryCandidateReviewDecision(
                review=last_review,
                promotion_status="already_resolved",
            )

        # FBL-05: routing/skill candidates cannot be auto-approved
        if (
            candidate.proposed_action == "review_route_or_skill_candidate"
            and action is not MemoryCandidateReviewAction.defer
        ):
            raise ReviewDeciderError(
                f"routing_candidate_cannot_be_auto_approved: candidate {candidate_id!r} "
                f"has proposed_action='review_route_or_skill_candidate'; only 'defer' is allowed"
            )

        now_str = _clock_now(self._clock)
        review_id = _new_id(self._id_factory, "review")

        review = MemoryCandidateReview(
            review_id=review_id,
            candidate_id=candidate_id,
            action=action,
            reviewer_id=reviewer_id,
            reviewed_at=now_str,
            rejection_reason=rejection_reason,
            edited_summary=edited_summary,
            metadata={"privacy": "refs_hashes_lengths_statuses_only"},
        )

        if action is MemoryCandidateReviewAction.defer:
            # Deferred candidates stay in the pending queue.
            return MemoryCandidateReviewDecision(review=review, promotion_status="deferred")

        # All non-defer actions resolve the candidate.
        self._review_store.resolve(candidate_id, review)

        if action is MemoryCandidateReviewAction.reject:
            return MemoryCandidateReviewDecision(review=review, promotion_status="rejected")

        record_status = "tombstoned" if action is MemoryCandidateReviewAction.tombstone else "active"
        summary = edited_summary if edited_summary is not None else (candidate.reason or "")

        candidate_meta = dict(candidate.metadata) if candidate.metadata else {}
        record = MemoryRecord(
            memory_id=_new_id(self._id_factory, "memory"),
            tenant_id=candidate.tenant_id,
            workspace_id=candidate.workspace_id,
            scope=candidate.proposed_scope or "user",
            status=record_status,
            sensitivity=candidate.proposed_sensitivity or "confidential",
            created_at=now_str,
            updated_at=now_str,
            source_refs=list(candidate.source_refs),
            summary=summary,
            subject=str(candidate_meta.get("category", "")),
            related_user_id=str(candidate_meta.get("user_id", "")) or None,
            session_id=str(candidate_meta.get("session_id", "")) or None,
            raw_payload_ref=candidate.raw_payload_ref,
            confidence=float(candidate.confidence if candidate.confidence is not None else 0.5),
            metadata=_json_clone({
                "candidate_id": candidate.candidate_id,
                "review_id": review_id,
                "privacy": "refs_hashes_lengths_statuses_only",
            }),
        )

        self._memory_store.upsert(record)

        promotion = "tombstoned" if action is MemoryCandidateReviewAction.tombstone else "promoted"
        return MemoryCandidateReviewDecision(
            review=review,
            promoted_memory_record=record,
            promotion_status=promotion,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clock_now(clock: Any | None) -> str:
    if clock is None:
        return datetime.now(tz=timezone.utc).isoformat()
    if callable(clock):
        result = clock()
        if isinstance(result, str):
            return result
        if isinstance(result, datetime):
            return result.isoformat()
        return str(result)
    if isinstance(clock, str):
        return clock
    return str(clock)


__all__ = [
    "InMemoryMemoryCandidateReviewStore",
    "MemoryCandidateReview",
    "MemoryCandidateReviewAction",
    "MemoryCandidateReviewDecider",
    "MemoryCandidateReviewDecision",
    "ReviewDeciderError",
]
