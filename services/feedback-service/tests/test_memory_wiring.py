"""Tests for Phase 25.1 Plan 02: feedback-to-memory service wiring."""

from __future__ import annotations

import unittest

from feedback_service import (
    FeedbackMemoryContextStore,
    FeedbackMemoryWiringResult,
    InMemoryFeedbackMemoryContextStore,
    apply_memory_candidate_review,
    ingest_feedback_callback_for_memory,
    wire_feedback_to_memory,
)
from platform_runtime import (
    InMemoryMemoryCandidateReviewStore,
    InMemoryMemoryStore,
    MemoryCandidateReviewAction,
    ReviewDeciderError,
)
from platform_runtime.memory import FeedbackLearningPolicy
from platform_runtime.sqlite_memory import SQLiteMemoryStore

FIXED_NOW = "2026-07-02T16:00:00+00:00"


def _make_feedback_event(
    feedback_id: str,
    *,
    action: str = "down",
    event_type: str = "correction",
    target: str = "target-001",
    labels: list[str] | None = None,
) -> dict[str, object]:
    return {
        "feedback_id": feedback_id,
        "turn_id": "turn-001",
        "conversation_id": "conversation-001",
        "user_id": "user-001",
        "source": "card_button",
        "event_type": event_type,
        "status": "pending",
        "created_at": "2026-06-28T05:00:00Z",
        "feedback_target": target,
        "action": action,
        "raw_payload_ref": f"fixture://wecom/callback/{feedback_id}",
        "labels": labels or [],
        "metadata": {"idempotency_key": f"wecom:feedback:{feedback_id}"},
    }


class FeedbackCallbackMemoryIngestionTests(unittest.TestCase):
    def test_ingest_callback_persists_correction_refs(self) -> None:
        """FBL-01: callback ingestion persists correction refs and they are retrievable."""
        context_store = InMemoryFeedbackMemoryContextStore(clock=lambda: FIXED_NOW)
        event = _make_feedback_event("fb-corr-001", action="needs_fix")

        result = ingest_feedback_callback_for_memory(
            wecom_callback_events=[event],
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            session_id="session-001",
            user_id="user-001",
            context_store=context_store,
        )

        self.assertEqual(result.feedback_correction_refs, ("feedback://fb-corr-001/correction",))
        refs = context_store.list_feedback_correction_refs(
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            session_id="session-001",
            user_id="user-001",
        )
        self.assertEqual(refs, ("feedback://fb-corr-001/correction",))

    def test_correction_refs_are_refs_only_no_raw_text(self) -> None:
        """Privacy: correction refs are URI refs and do not carry raw message text."""
        event = _make_feedback_event("fb-corr-002", action="down")
        event["message"] = "Please fix the citation format."
        result = ingest_feedback_callback_for_memory(
            wecom_callback_events=[event],
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            session_id="session-001",
            user_id="user-001",
        )
        self.assertTrue(all("://" in ref for ref in result.feedback_correction_refs))
        self.assertNotIn("Please fix", repr(result))
        self.assertNotIn("Please fix", str(result.metadata))

    def test_repeated_negative_feedback_queues_memory_candidate(self) -> None:
        """FBL-02: repeated negative feedback queues a pending memory candidate."""
        review_store = InMemoryMemoryCandidateReviewStore()
        events = [
            _make_feedback_event("fb-neg-001", action="down", target="target-repeat"),
            _make_feedback_event("fb-neg-002", action="down", target="target-repeat"),
        ]

        result = ingest_feedback_callback_for_memory(
            wecom_callback_events=events,
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            session_id="session-001",
            user_id="user-001",
            policy=FeedbackLearningPolicy(repeated_negative_threshold=2),
            review_store=review_store,
        )

        self.assertEqual(len(result.queued_memory_candidate_ids), 1)
        candidate_id = result.queued_memory_candidate_ids[0]
        candidate = review_store.get(candidate_id)
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.proposed_action, "create_memory_candidate")
        self.assertTrue(candidate.requires_human_review)
        self.assertFalse(candidate.metadata.get("no_auto_modify", True))

    def test_route_mismatch_queues_routing_candidate_with_no_auto_modify(self) -> None:
        """Route/skill feedback queues a human-review-only routing candidate."""
        review_store = InMemoryMemoryCandidateReviewStore()
        event = _make_feedback_event(
            "fb-route-001",
            action="route_wrong",
            event_type="route_mismatch",
            labels=["route_mismatch"],
        )
        event["route_mismatch"] = True

        result = ingest_feedback_callback_for_memory(
            wecom_callback_events=[event],
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            session_id="session-001",
            user_id="user-001",
            review_store=review_store,
        )

        self.assertEqual(len(result.queued_routing_candidate_ids), 1)
        candidate_id = result.queued_routing_candidate_ids[0]
        candidate = review_store.get(candidate_id)
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.proposed_action, "review_route_or_skill_candidate")
        self.assertTrue(candidate.requires_human_review)
        self.assertTrue(candidate.metadata.get("no_auto_modify", False))

    def test_skill_candidate_feedback_queues_routing_candidate(self) -> None:
        """Skill candidate feedback queues a human-review-only routing candidate."""
        review_store = InMemoryMemoryCandidateReviewStore()
        event = _make_feedback_event(
            "fb-skill-001",
            action="down",
        )
        event["skill_candidate"] = {
            "detected": True,
            "requires_human_review": True,
            "metadata": {"no_auto_modify": True},
        }

        result = ingest_feedback_callback_for_memory(
            wecom_callback_events=[event],
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            session_id="session-001",
            user_id="user-001",
            review_store=review_store,
        )

        self.assertEqual(len(result.queued_routing_candidate_ids), 1)
        candidate_id = result.queued_routing_candidate_ids[0]
        candidate = review_store.get(candidate_id)
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.proposed_action, "review_route_or_skill_candidate")
        self.assertTrue(candidate.requires_human_review)
        self.assertTrue(candidate.metadata.get("no_auto_modify", False))

    def test_durable_candidate_store_persists_via_upsert_candidate(self) -> None:
        """Durable store upsert_candidate is used when available; no recall-visible upsert."""
        review_store = InMemoryMemoryCandidateReviewStore()
        durable = SQLiteMemoryStore(clock=lambda: FIXED_NOW)
        events = [
            _make_feedback_event("fb-dur-001", action="down", target="target-dur"),
            _make_feedback_event("fb-dur-002", action="down", target="target-dur"),
        ]

        result = ingest_feedback_callback_for_memory(
            wecom_callback_events=events,
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            session_id="session-001",
            user_id="user-001",
            policy=FeedbackLearningPolicy(repeated_negative_threshold=2),
            review_store=review_store,
            durable_candidate_store=durable,
        )

        self.assertEqual(len(result.persisted_candidate_ids), 1)
        candidate_id = result.persisted_candidate_ids[0]
        self.assertIsNotNone(durable.get_candidate(candidate_id))
        # Ensure no recall-visible record was created during callback ingestion.
        from platform_runtime import MemoryQuery
        recalled = durable.search(
            MemoryQuery(
                tenant_id="tenant-001",
                workspace_id="workspace-001",
                user_id="user-001",
                session_id="session-001",
                now=FIXED_NOW,
            )
        )
        self.assertEqual(len(recalled), 0)

    def test_raw_payload_key_is_rejected(self) -> None:
        """Privacy: exact raw_payload key is rejected through existing guards."""
        event = _make_feedback_event("fb-raw-001")
        event["raw_payload"] = "secret"

        with self.assertRaises(ValueError):
            ingest_feedback_callback_for_memory(
                wecom_callback_events=[event],
                tenant_id="tenant-001",
                workspace_id="workspace-001",
                session_id="session-001",
                user_id="user-001",
            )


class FeedbackMemoryReviewActionTests(unittest.TestCase):
    def test_approve_promotes_memory_candidate(self) -> None:
        """FBL-03: approve promotes a pending candidate to a recall-visible record."""
        memory_store = InMemoryMemoryStore(clock=lambda: FIXED_NOW)
        review_store = InMemoryMemoryCandidateReviewStore()
        events = [
            _make_feedback_event("fb-rev-001", action="down", target="target-rev"),
            _make_feedback_event("fb-rev-002", action="down", target="target-rev"),
        ]
        result = wire_feedback_to_memory(
            events=events,
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            session_id="session-001",
            user_id="user-001",
            policy=FeedbackLearningPolicy(repeated_negative_threshold=2),
            review_store=review_store,
        )
        candidate_id = result.queued_memory_candidate_ids[0]

        decision = apply_memory_candidate_review(
            candidate_id=candidate_id,
            action=MemoryCandidateReviewAction.approve,
            memory_store=memory_store,
            review_store=review_store,
            reviewer_id="reviewer-001",
            clock=lambda: FIXED_NOW,
        )

        self.assertEqual(decision.promotion_status, "promoted")
        self.assertIsNotNone(decision.promoted_memory_record)

    def test_reject_resolves_without_promotion(self) -> None:
        """FBL-03: reject resolves the candidate without creating a recall record."""
        memory_store = InMemoryMemoryStore(clock=lambda: FIXED_NOW)
        review_store = InMemoryMemoryCandidateReviewStore()
        events = [
            _make_feedback_event("fb-rej-001", action="down", target="target-rej"),
            _make_feedback_event("fb-rej-002", action="down", target="target-rej"),
        ]
        result = wire_feedback_to_memory(
            events=events,
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            session_id="session-001",
            user_id="user-001",
            policy=FeedbackLearningPolicy(repeated_negative_threshold=2),
            review_store=review_store,
        )
        candidate_id = result.queued_memory_candidate_ids[0]

        decision = apply_memory_candidate_review(
            candidate_id=candidate_id,
            action=MemoryCandidateReviewAction.reject,
            memory_store=memory_store,
            review_store=review_store,
            rejection_reason="not relevant",
            clock=lambda: FIXED_NOW,
        )

        self.assertEqual(decision.promotion_status, "rejected")
        self.assertIsNone(decision.promoted_memory_record)
        self.assertEqual(len(memory_store._records), 0)

    def test_defer_leaves_candidate_pending(self) -> None:
        """FBL-03: defer leaves the candidate in the pending queue."""
        memory_store = InMemoryMemoryStore(clock=lambda: FIXED_NOW)
        review_store = InMemoryMemoryCandidateReviewStore()
        events = [
            _make_feedback_event("fb-def-001", action="down", target="target-def"),
            _make_feedback_event("fb-def-002", action="down", target="target-def"),
        ]
        result = wire_feedback_to_memory(
            events=events,
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            session_id="session-001",
            user_id="user-001",
            policy=FeedbackLearningPolicy(repeated_negative_threshold=2),
            review_store=review_store,
        )
        candidate_id = result.queued_memory_candidate_ids[0]

        decision = apply_memory_candidate_review(
            candidate_id=candidate_id,
            action=MemoryCandidateReviewAction.defer,
            memory_store=memory_store,
            review_store=review_store,
            clock=lambda: FIXED_NOW,
        )

        self.assertEqual(decision.promotion_status, "deferred")
        self.assertIsNotNone(review_store.get_pending(tenant_id="tenant-001"))
        self.assertEqual(len(review_store.get_pending(tenant_id="tenant-001")), 1)

    def test_route_skill_candidate_can_only_be_deferred(self) -> None:
        """FBL-04: route/skill candidates cannot be approved, rejected, edited, or tombstoned."""
        memory_store = InMemoryMemoryStore(clock=lambda: FIXED_NOW)
        review_store = InMemoryMemoryCandidateReviewStore()
        event = _make_feedback_event(
            "fb-rs-001",
            action="route_wrong",
            event_type="route_mismatch",
            labels=["route_mismatch"],
        )
        event["route_mismatch"] = True
        wire_feedback_to_memory(
            events=[event],
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            session_id="session-001",
            user_id="user-001",
            review_store=review_store,
        )
        candidate_id = review_store.get_pending(tenant_id="tenant-001")[0].candidate_id

        for action in (
            MemoryCandidateReviewAction.approve,
            MemoryCandidateReviewAction.reject,
            MemoryCandidateReviewAction.edit,
            MemoryCandidateReviewAction.tombstone,
        ):
            with self.subTest(action=action.value):
                with self.assertRaises(ReviewDeciderError):
                    apply_memory_candidate_review(
                        candidate_id=candidate_id,
                        action=action,
                        memory_store=memory_store,
                        review_store=review_store,
                        clock=lambda: FIXED_NOW,
                    )


class FeedbackServicePublicExportTests(unittest.TestCase):
    def test_all_new_symbols_exported_from_package(self) -> None:
        """feedback_service.__init__ exports the new memory-wiring symbols."""
        from feedback_service import (
            FeedbackMemoryContextStore,
            FeedbackMemoryWiringResult,
            InMemoryFeedbackMemoryContextStore,
            apply_memory_candidate_review,
            ingest_feedback_callback_for_memory,
            wire_feedback_to_memory,
        )

        self.assertTrue(callable(ingest_feedback_callback_for_memory))
        self.assertTrue(callable(wire_feedback_to_memory))
        self.assertTrue(callable(apply_memory_candidate_review))
        self.assertTrue(callable(InMemoryFeedbackMemoryContextStore))


if __name__ == "__main__":
    unittest.main()
