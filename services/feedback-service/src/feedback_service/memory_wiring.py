"""Feedback-to-memory wiring for InkStatute V2 feedback callbacks.

This module connects feedback callback/service ingestion to platform-runtime
feedback learning and review primitives through lightweight injected stores.
It does not start a daemon, add a database, or import backend-specific code.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from platform_contract.events import JsonObject, MemoryCandidate
from platform_runtime.memory import (
    FeedbackLearningInput,
    FeedbackLearningPolicy,
    FeedbackLearningResult,
)
from platform_runtime.memory_review import (
    InMemoryMemoryCandidateReviewStore,
    MemoryCandidateReviewAction,
    MemoryCandidateReviewDecider,
    MemoryCandidateReviewDecision,
    ReviewDeciderError,
)
from platform_runtime.session_resolver import _new_id, _timestamp


@runtime_checkable
class FeedbackMemoryContextStore(Protocol):
    """Lightweight port for same-session feedback correction refs."""

    def remember_feedback_correction_refs(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        session_id: str,
        user_id: str,
        correction_refs: tuple[str, ...],
        feedback_ids: tuple[str, ...],
        now: str,
        metadata: JsonObject | None = None,
    ) -> None:
        """Persist refs-only correction metadata for the given session scope."""

    def list_feedback_correction_refs(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        session_id: str,
        user_id: str,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        """Return refs suitable for ContextBundle assembly."""


@dataclass(frozen=True, slots=True)
class FeedbackMemoryWiringResult:
    """Outcome of wiring feedback into memory learning and review."""

    feedback_correction_refs: tuple[str, ...] = ()
    queued_memory_candidate_ids: tuple[str, ...] = ()
    queued_routing_candidate_ids: tuple[str, ...] = ()
    persisted_candidate_ids: tuple[str, ...] = ()
    metadata: JsonObject = field(default_factory=dict)


class InMemoryFeedbackMemoryContextStore:
    """In-process, scope-isolated store for feedback correction refs."""

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._clock = clock
        self._entries: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    def remember_feedback_correction_refs(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        session_id: str,
        user_id: str,
        correction_refs: tuple[str, ...],
        feedback_ids: tuple[str, ...],
        now: str,
        metadata: JsonObject | None = None,
    ) -> None:
        if not correction_refs:
            return
        key = (tenant_id, workspace_id, session_id, user_id)
        entry = self._entries.setdefault(
            key,
            {
                "refs": [],
                "feedback_ids": [],
                "created_at": now,
                "updated_at": now,
                "metadata": {"privacy": "refs_hashes_lengths_statuses_only"},
            },
        )
        entry["updated_at"] = now
        for ref in correction_refs:
            if ref not in entry["refs"]:
                entry["refs"].append(ref)
        for fid in feedback_ids:
            if fid not in entry["feedback_ids"]:
                entry["feedback_ids"].append(fid)
        if metadata:
            entry["metadata"].update(metadata)

    def list_feedback_correction_refs(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        session_id: str,
        user_id: str,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        key = (tenant_id, workspace_id, session_id, user_id)
        entry = self._entries.get(key)
        if entry is None:
            return ()
        return tuple(entry["refs"])


def wire_feedback_to_memory(
    *,
    events: Sequence[Mapping[str, Any]],
    tenant_id: str,
    workspace_id: str,
    session_id: str,
    user_id: str,
    context_bundle_id: str | None = None,
    run_id: str | None = None,
    turn_id: str | None = None,
    policy: FeedbackLearningPolicy | None = None,
    context_store: FeedbackMemoryContextStore | None = None,
    review_store: InMemoryMemoryCandidateReviewStore | None = None,
    durable_candidate_store: Any | None = None,
    selected_memory_ids: tuple[str, ...] = (),
    now: str | None = None,
    clock: Callable[[], str] | None = None,
) -> FeedbackMemoryWiringResult:
    """Normalize feedback, learn from it, and queue candidates for review.

    This function does not auto-promote candidates; it only queues them for
    explicit human review via ``apply_memory_candidate_review``.
    """
    # Local imports avoid a circular module dependency with queue.py.
    from .classification import classify_feedback_event
    from .queue import _privacy_checked_clone, dedupe_feedback_events

    safe_events = dedupe_feedback_events([_privacy_checked_clone(event) for event in events])
    if not safe_events:
        return FeedbackMemoryWiringResult(
            metadata={"privacy": "refs_hashes_lengths_statuses_only", "feedback_count": 0}
        )

    effective_now = now or _clock_now(clock)
    effective_policy = policy or FeedbackLearningPolicy()

    # Validate that classification still marks route/skill candidates safely.
    for event in safe_events:
        classification = classify_feedback_event(event)
        if classification.no_auto_modify and classification.requires_human_review:
            event_meta = dict(event.get("metadata") or {})
            event_meta["requires_human_review"] = True
            event_meta["no_auto_modify"] = True
            event["metadata"] = event_meta

    learning_input = FeedbackLearningInput(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        session_id=session_id,
        user_id=user_id,
        feedback_events=tuple(safe_events),
        context_bundle_id=context_bundle_id or "",
        run_id=run_id,
        turn_id=turn_id,
        selected_memory_ids=selected_memory_ids,
        now=effective_now,
        metadata={"privacy": "refs_hashes_lengths_statuses_only"},
    )
    learning_result: FeedbackLearningResult = effective_policy.learn(learning_input)

    if context_store is not None and learning_result.feedback_correction_refs:
        feedback_ids = tuple(
            str(event.get("feedback_id") or "")
            for event in safe_events
            if event.get("feedback_id")
        )
        context_store.remember_feedback_correction_refs(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            session_id=session_id,
            user_id=user_id,
            correction_refs=learning_result.feedback_correction_refs,
            feedback_ids=feedback_ids,
            now=effective_now,
            metadata={
                "feedback_count": len(safe_events),
                "duplicate_count": sum(
                    int(event.get("metadata", {}).get("duplicate_count", 1))
                    for event in safe_events
                ),
            },
        )

    queued_memory_ids: list[str] = []
    queued_routing_ids: list[str] = []
    persisted_ids: list[str] = []

    if review_store is not None:
        for candidate in learning_result.memory_candidates:
            enriched = _enrich_candidate_with_user_id(candidate, user_id)
            review_store.queue(enriched)
            queued_memory_ids.append(enriched.candidate_id)
            if durable_candidate_store is not None and callable(
                getattr(durable_candidate_store, "upsert_candidate", None)
            ):
                durable_candidate_store.upsert_candidate(enriched)
                persisted_ids.append(enriched.candidate_id)

        for candidate in learning_result.routing_candidates:
            enriched = _enrich_candidate_with_user_id(candidate, user_id)
            review_store.queue(enriched)
            queued_routing_ids.append(enriched.candidate_id)
            if durable_candidate_store is not None and callable(
                getattr(durable_candidate_store, "upsert_candidate", None)
            ):
                durable_candidate_store.upsert_candidate(enriched)
                persisted_ids.append(enriched.candidate_id)

    metadata: JsonObject = {
        "privacy": "refs_hashes_lengths_statuses_only",
        "feedback_count": len(safe_events),
        "correction_ref_count": len(learning_result.feedback_correction_refs),
        "memory_candidate_count": len(queued_memory_ids),
        "routing_candidate_count": len(queued_routing_ids),
        "durable_candidate_count": len(persisted_ids),
    }
    if learning_result.metadata:
        metadata["learning_metadata"] = learning_result.metadata

    return FeedbackMemoryWiringResult(
        feedback_correction_refs=learning_result.feedback_correction_refs,
        queued_memory_candidate_ids=tuple(queued_memory_ids),
        queued_routing_candidate_ids=tuple(queued_routing_ids),
        persisted_candidate_ids=tuple(persisted_ids),
        metadata=metadata,
    )


def apply_memory_candidate_review(
    *,
    candidate_id: str,
    action: MemoryCandidateReviewAction,
    memory_store: Any,
    review_store: InMemoryMemoryCandidateReviewStore,
    reviewer_id: str | None = None,
    rejection_reason: str | None = None,
    edited_summary: str | None = None,
    clock: Callable[[], str] | None = None,
    id_factory: Callable[[str], str] | None = None,
) -> MemoryCandidateReviewDecision:
    """Explicit human review action for a queued memory candidate.

    This helper is never called by ``wire_feedback_to_memory``; callback
    ingestion only queues candidates, and review promotion is an explicit step.
    """
    decider = MemoryCandidateReviewDecider(
        memory_store=memory_store,
        review_store=review_store,
        clock=clock,
        id_factory=id_factory,
    )
    return decider.decide(
        candidate_id=candidate_id,
        action=action,
        reviewer_id=reviewer_id,
        rejection_reason=rejection_reason,
        edited_summary=edited_summary,
    )


def _enrich_candidate_with_user_id(candidate: MemoryCandidate, user_id: str) -> MemoryCandidate:
    """Ensure candidate metadata carries user_id for review promotion."""
    from dataclasses import replace as _replace

    enriched_meta = dict(candidate.metadata or {})
    enriched_meta["user_id"] = user_id
    return _replace(
        candidate,
        metadata=enriched_meta,
    )


def _clock_now(clock: Callable[[], str] | None) -> str:
    if clock is None:
        from datetime import datetime, timezone

        return datetime.now(tz=timezone.utc).isoformat()
    return clock()


__all__ = [
    "FeedbackMemoryContextStore",
    "InMemoryFeedbackMemoryContextStore",
    "FeedbackMemoryWiringResult",
    "apply_memory_candidate_review",
    "ingest_feedback_callback_for_memory",
    "wire_feedback_to_memory",
]
