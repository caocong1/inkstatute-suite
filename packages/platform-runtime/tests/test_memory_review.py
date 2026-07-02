"""Tests for Phase 23: feedback-to-memory review loop."""

from __future__ import annotations

import unittest

from platform_contract.events import MemoryCandidate
from platform_runtime import (
    FeedbackLearningInput,
    FeedbackLearningPolicy,
    InMemoryMemoryCandidateReviewStore,
    InMemoryMemoryStore,
    MemoryCandidateReview,
    MemoryCandidateReviewAction,
    MemoryCandidateReviewDecider,
    MemoryCandidateReviewDecision,
    MemoryQuery,
    MemoryStorePolicy,
    ReviewDeciderError,
)

FIXED_NOW = "2026-07-02T14:00:00+00:00"

CORRECTION_EVENT = {
    "feedback_id": "fb-phase23-001",
    "feedback_target": "result-phase23-001",
    "event_type": "correction",
    "action": "correction",
    "status": "resolved",
    "user_id": "user-phase23-001",
    "raw_payload_ref": "fixture://phase23/feedback/fb-phase23-001/raw",
}

NEGATIVE_REPEATED_EVENT_A = {
    "feedback_id": "fb-phase23-neg-001",
    "feedback_target": "result-phase23-neg",
    "event_type": "rating",
    "action": "down",
    "status": "resolved",
    "user_id": "user-phase23-001",
    "raw_payload_ref": "fixture://phase23/feedback/fb-phase23-neg-001/raw",
}

NEGATIVE_REPEATED_EVENT_B = {
    "feedback_id": "fb-phase23-neg-002",
    "feedback_target": "result-phase23-neg",
    "event_type": "rating",
    "action": "down",
    "status": "resolved",
    "user_id": "user-phase23-001",
    "raw_payload_ref": "fixture://phase23/feedback/fb-phase23-neg-002/raw",
}

ROUTING_CANDIDATE_EVENT = {
    "feedback_id": "fb-phase23-route-001",
    "feedback_target": "result-phase23-route",
    "event_type": "correction",
    "action": "route_mismatch",
    "status": "resolved",
    "user_id": "user-phase23-001",
    "raw_payload_ref": "fixture://phase23/feedback/fb-phase23-route-001/raw",
}


def make_learning_input(events: list[dict], *, threshold: int = 2) -> tuple[FeedbackLearningPolicy, object]:
    policy = FeedbackLearningPolicy(repeated_negative_threshold=threshold)
    input = FeedbackLearningInput(
        tenant_id="tenant-phase23-001",
        workspace_id="workspace-phase23-001",
        session_id="session-phase23-001",
        user_id="user-phase23-001",
        feedback_events=tuple(events),
        context_bundle_id="bundle-phase23-001",
        run_id="run-phase23-001",
        turn_id="turn-phase23-001",
        now=FIXED_NOW,
    )
    return policy, input


def make_candidate(
    candidate_id: str,
    *,
    proposed_action: str = "create_memory_candidate",
    tenant_id: str = "tenant-phase23-001",
) -> MemoryCandidate:
    return MemoryCandidate(
        candidate_id=candidate_id,
        tenant_id=tenant_id,
        workspace_id="workspace-phase23-001",
        status="pending",
        source_refs=[f"feedback://fb-phase23/{candidate_id}/correction"],
        created_at=FIXED_NOW,
        proposed_scope="user",
        proposed_sensitivity="confidential",
        proposed_action=proposed_action,
        proposed_record_ref=f"memory://candidates/{candidate_id}",
        reason=f"Synthetic candidate for {candidate_id}.",
        confidence=0.7,
        requires_human_review=True,
        metadata={"user_id": "user-phase23-001", "category": "correction"},
    )


def make_decider() -> tuple[InMemoryMemoryStore, InMemoryMemoryCandidateReviewStore, MemoryCandidateReviewDecider]:
    memory_store = InMemoryMemoryStore()
    review_store = InMemoryMemoryCandidateReviewStore()
    decider = MemoryCandidateReviewDecider(
        memory_store=memory_store,
        review_store=review_store,
        clock=lambda: FIXED_NOW,
    )
    return memory_store, review_store, decider


class FeedbackLearningIntegrationTests(unittest.TestCase):
    def test_feedback_correction_refs_from_learning(self) -> None:
        """FBL-01: learn() produces feedback_correction_refs for same-session context assembly."""
        policy, input = make_learning_input([CORRECTION_EVENT])
        result = policy.learn(input)

        self.assertGreater(len(result.feedback_correction_refs), 0)
        for ref in result.feedback_correction_refs:
            self.assertIn("feedback://", ref)

    def test_pending_candidates_queued_from_learning_result(self) -> None:
        """FBL-02: repeated negative feedback produces queued memory candidates."""
        policy, input = make_learning_input([NEGATIVE_REPEATED_EVENT_A, NEGATIVE_REPEATED_EVENT_B], threshold=2)
        result = policy.learn(input)

        review_store = InMemoryMemoryCandidateReviewStore()
        review_store.queue_many(result.memory_candidates)

        pending = review_store.get_pending(
            tenant_id="tenant-phase23-001",
            workspace_id="workspace-phase23-001",
        )
        self.assertGreater(len(pending), 0)


class MemoryCandidateReviewStoreTests(unittest.TestCase):
    def test_review_store_queue_is_idempotent_on_candidate_id(self) -> None:
        """Duplicate queue calls for same candidate_id are silently ignored."""
        review_store = InMemoryMemoryCandidateReviewStore()
        candidate = make_candidate("cand-idempotent-001")
        review_store.queue(candidate)
        review_store.queue(candidate)

        pending = review_store.get_pending(tenant_id="tenant-phase23-001")
        self.assertEqual(len(pending), 1)

    def test_get_pending_filters_by_workspace(self) -> None:
        review_store = InMemoryMemoryCandidateReviewStore()
        c1 = make_candidate("cand-ws-001")
        c2 = make_candidate("cand-ws-002")
        review_store.queue(c1)
        review_store.queue(c2)

        pending = review_store.get_pending(
            tenant_id="tenant-phase23-001", workspace_id="workspace-phase23-001"
        )
        ids = {c.candidate_id for c in pending}
        self.assertIn("cand-ws-001", ids)
        self.assertIn("cand-ws-002", ids)

    def test_resolved_candidates_not_in_pending(self) -> None:
        review_store = InMemoryMemoryCandidateReviewStore()
        candidate = make_candidate("cand-resolved-001")
        review_store.queue(candidate)

        review = MemoryCandidateReview(
            review_id="review-001",
            candidate_id="cand-resolved-001",
            action=MemoryCandidateReviewAction.reject,
        )
        review_store.resolve("cand-resolved-001", review)

        pending = review_store.get_pending(tenant_id="tenant-phase23-001")
        self.assertNotIn("cand-resolved-001", {c.candidate_id for c in pending})

    def test_list_resolved_returns_resolved_candidates(self) -> None:
        review_store = InMemoryMemoryCandidateReviewStore()
        candidate = make_candidate("cand-list-001")
        review_store.queue(candidate)
        review = MemoryCandidateReview(
            review_id="r-list-001",
            candidate_id="cand-list-001",
            action=MemoryCandidateReviewAction.approve,
        )
        review_store.resolve("cand-list-001", review)

        resolved = review_store.list_resolved(tenant_id="tenant-phase23-001")
        self.assertEqual(len(resolved), 1)


class MemoryCandidateReviewDeciderTests(unittest.TestCase):
    def test_approve_promotes_candidate_to_memory_store(self) -> None:
        """FBL-04: approve creates a durable active MemoryRecord in the store."""
        memory_store, review_store, decider = make_decider()
        candidate = make_candidate("cand-approve-001")
        review_store.queue(candidate)

        decision = decider.decide(
            candidate_id="cand-approve-001",
            action=MemoryCandidateReviewAction.approve,
            reviewer_id="human-reviewer-001",
        )

        self.assertEqual(decision.promotion_status, "promoted")
        self.assertIsNotNone(decision.promoted_memory_record)
        assert decision.promoted_memory_record is not None
        self.assertEqual(decision.promoted_memory_record.status, "active")

        # Verify it's searchable in the store (user scope requires user_id in query)
        results = memory_store.search(MemoryQuery(
            tenant_id="tenant-phase23-001",
            workspace_id="workspace-phase23-001",
            user_id="user-phase23-001",
            now=FIXED_NOW,
        ))
        self.assertGreater(len(results), 0)

    def test_reject_does_not_create_memory_record(self) -> None:
        """FBL-04: rejected candidates are not recalled."""
        memory_store, review_store, decider = make_decider()
        candidate = make_candidate("cand-reject-001")
        review_store.queue(candidate)

        decision = decider.decide(
            candidate_id="cand-reject-001",
            action=MemoryCandidateReviewAction.reject,
            rejection_reason="not_applicable",
        )

        self.assertEqual(decision.promotion_status, "rejected")
        self.assertIsNone(decision.promoted_memory_record)

        results = memory_store.search(MemoryQuery(
            tenant_id="tenant-phase23-001",
            workspace_id="workspace-phase23-001",
            now=FIXED_NOW,
        ))
        self.assertEqual(len(results), 0)

    def test_tombstone_creates_tombstoned_record_in_store(self) -> None:
        memory_store, review_store, decider = make_decider()
        candidate = make_candidate("cand-tombstone-001")
        review_store.queue(candidate)

        decision = decider.decide(
            candidate_id="cand-tombstone-001",
            action=MemoryCandidateReviewAction.tombstone,
        )

        self.assertEqual(decision.promotion_status, "tombstoned")
        assert decision.promoted_memory_record is not None
        self.assertEqual(decision.promoted_memory_record.status, "tombstoned")

    def test_edit_promotes_candidate_with_edited_summary(self) -> None:
        memory_store, review_store, decider = make_decider()
        candidate = make_candidate("cand-edit-001")
        review_store.queue(candidate)

        decision = decider.decide(
            candidate_id="cand-edit-001",
            action=MemoryCandidateReviewAction.edit,
            edited_summary="Human-reviewed and corrected summary for citation error.",
        )

        self.assertEqual(decision.promotion_status, "promoted")
        assert decision.promoted_memory_record is not None
        self.assertEqual(
            decision.promoted_memory_record.summary,
            "Human-reviewed and corrected summary for citation error.",
        )

    def test_defer_leaves_candidate_in_pending_queue(self) -> None:
        """FBL-03: defer action leaves candidate pending for later review."""
        memory_store, review_store, decider = make_decider()
        candidate = make_candidate("cand-defer-001")
        review_store.queue(candidate)

        decision = decider.decide(
            candidate_id="cand-defer-001",
            action=MemoryCandidateReviewAction.defer,
        )

        self.assertEqual(decision.promotion_status, "deferred")
        pending = review_store.get_pending(tenant_id="tenant-phase23-001")
        self.assertIn("cand-defer-001", {c.candidate_id for c in pending})

    def test_already_resolved_candidate_returns_already_resolved(self) -> None:
        """Idempotency: second non-defer decision on same candidate returns already_resolved."""
        memory_store, review_store, decider = make_decider()
        candidate = make_candidate("cand-idempotent-002")
        review_store.queue(candidate)

        decider.decide(candidate_id="cand-idempotent-002", action=MemoryCandidateReviewAction.approve)
        decision2 = decider.decide(candidate_id="cand-idempotent-002", action=MemoryCandidateReviewAction.approve)
        self.assertEqual(decision2.promotion_status, "already_resolved")

    def test_routing_candidate_cannot_be_approved_or_rejected(self) -> None:
        """FBL-05: routing candidates raise ReviewDeciderError on approve/reject/edit/tombstone."""
        _, review_store, decider = make_decider()
        candidate = make_candidate("cand-routing-001", proposed_action="review_route_or_skill_candidate")
        review_store.queue(candidate)

        for action in (
            MemoryCandidateReviewAction.approve,
            MemoryCandidateReviewAction.reject,
            MemoryCandidateReviewAction.edit,
            MemoryCandidateReviewAction.tombstone,
        ):
            with self.subTest(action=action):
                with self.assertRaisesRegex(ReviewDeciderError, "routing_candidate_cannot_be_auto_approved"):
                    decider.decide(candidate_id="cand-routing-001", action=action)

    def test_routing_candidate_can_be_deferred(self) -> None:
        """FBL-05: defer is the only allowed action for routing candidates."""
        _, review_store, decider = make_decider()
        candidate = make_candidate("cand-routing-002", proposed_action="review_route_or_skill_candidate")
        review_store.queue(candidate)

        decision = decider.decide(
            candidate_id="cand-routing-002",
            action=MemoryCandidateReviewAction.defer,
        )
        self.assertEqual(decision.promotion_status, "deferred")

    def test_candidate_not_found_raises_reviewer_error(self) -> None:
        """ReviewDeciderError raised for unknown candidate_id."""
        _, _, decider = make_decider()

        with self.assertRaisesRegex(ReviewDeciderError, "candidate_not_found"):
            decider.decide(
                candidate_id="nonexistent-candidate-001",
                action=MemoryCandidateReviewAction.approve,
            )

    def test_rejected_memory_id_does_not_appear_in_recall(self) -> None:
        """FBL-04: rejected candidate never enters recall results."""
        memory_store, review_store, decider = make_decider()
        candidate = make_candidate("cand-recall-reject-001")
        review_store.queue(candidate)

        decider.decide(
            candidate_id="cand-recall-reject-001",
            action=MemoryCandidateReviewAction.reject,
        )

        query = MemoryQuery(
            tenant_id="tenant-phase23-001",
            workspace_id="workspace-phase23-001",
            now=FIXED_NOW,
        )
        results = memory_store.search(query)
        memory_ids = {r.record.memory_id for r in results}
        self.assertNotIn("cand-recall-reject-001", memory_ids)


if __name__ == "__main__":
    unittest.main()
