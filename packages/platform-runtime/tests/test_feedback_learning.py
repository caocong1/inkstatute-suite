from __future__ import annotations

import unittest

from platform_runtime import (
    ContextAssembler,
    ContextAssemblyInput,
    ContextAssemblyPolicy,
    FeedbackLearningInput,
    FeedbackLearningPolicy,
    MemoryPrivacyError,
    SessionScope,
)


FIXED_NOW = "2026-07-01T08:00:00Z"


def make_scope() -> SessionScope:
    return SessionScope(
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        channel_id="wecom",
        user_id="user-001",
        bot_instance_id="bot-001",
        conversation_id="conversation-001",
    )


def make_feedback(feedback_id: str, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "feedback_id": feedback_id,
        "turn_id": "turn-001",
        "conversation_id": "conversation-001",
        "user_id": "user-001",
        "source": "card_button",
        "event_type": "correction",
        "status": "pending",
        "created_at": FIXED_NOW,
        "feedback_target": "target-001",
        "action": "down",
        "message": "Please use the user's preferred citation format.",
        "raw_payload_ref": f"fixture://feedback/{feedback_id}",
        "labels": ["citation_error"],
        "metadata": {"idempotency_key": f"feedback:{feedback_id}"},
    }
    values.update(overrides)
    return values


def make_learning_input(*feedback_events: dict[str, object], **overrides: object) -> FeedbackLearningInput:
    values = {
        "tenant_id": "tenant-001",
        "workspace_id": "workspace-001",
        "session_id": "session-001",
        "user_id": "user-001",
        "feedback_events": tuple(feedback_events),
        "context_bundle_id": "context-bundle-001",
        "run_id": "run-001",
        "turn_id": "turn-001",
        "selected_memory_ids": ("memory-001",),
        "now": FIXED_NOW,
    }
    values.update(overrides)
    return FeedbackLearningInput(**values)


class FeedbackLearningPolicyTests(unittest.TestCase):
    def test_safe_corrections_become_context_refs_without_raw_message_storage(self) -> None:
        result = FeedbackLearningPolicy().learn(make_learning_input(make_feedback("feedback-001")))

        self.assertEqual(result.feedback_correction_refs, ("feedback://feedback-001/correction",))
        self.assertIn("message_sha256_16", result.metadata["feedback_events"][0])
        self.assertIn("message_length", result.metadata["feedback_events"][0])
        self.assertNotIn("Please use", repr(result))

    def test_context_assembler_accepts_feedback_corrections_and_memory_refs(self) -> None:
        scope = make_scope()
        result = FeedbackLearningPolicy().learn(make_learning_input(make_feedback("feedback-context")))
        context = ContextAssembler(
            policy=ContextAssemblyPolicy(budget_tokens=2048),
            clock=lambda: FIXED_NOW,
            id_factory=lambda prefix: f"{prefix}-001",
        ).assemble(
            ContextAssemblyInput(
                scope=scope,
                session_id="session-001",
                turn_id="turn-001",
                current_turn_ref="fixture://turns/current",
                feedback_correction_refs=result.feedback_correction_refs,
                memory_refs=tuple(f"memory://{use.memory_id}" for use in result.memory_uses),
                metadata={"input_ref": "fixture://context-input/phase17"},
            )
        )

        event = context.as_event()
        self.assertEqual(event["metadata"]["feedback_correction_refs"], ["feedback://feedback-context/correction"])
        self.assertEqual(event["memory_refs"], ["memory://memory-001"])

    def test_repeated_negative_feedback_creates_pending_memory_candidate(self) -> None:
        feedback = [
            make_feedback("feedback-repeat-1", feedback_target="target-repeat"),
            make_feedback("feedback-repeat-2", feedback_target="target-repeat"),
        ]

        result = FeedbackLearningPolicy(repeated_negative_threshold=2).learn(make_learning_input(*feedback))

        self.assertEqual(len(result.memory_candidates), 1)
        candidate = result.memory_candidates[0]
        self.assertEqual(candidate.status, "pending")
        self.assertEqual(candidate.proposed_action, "create_memory_candidate")
        self.assertEqual(candidate.confidence, 0.7)
        self.assertTrue(candidate.requires_human_review)
        self.assertEqual(candidate.metadata["feedback_count"], 2)
        self.assertFalse(candidate.metadata["no_auto_modify"])

    def test_repeated_negative_threshold_blocks_single_click_candidate(self) -> None:
        result = FeedbackLearningPolicy(repeated_negative_threshold=2).learn(
            make_learning_input(make_feedback("feedback-single"))
        )

        self.assertEqual(result.memory_candidates, ())

    def test_route_mismatch_and_skill_candidate_are_human_review_no_auto_modify(self) -> None:
        route = make_feedback(
            "feedback-route",
            event_type="route_mismatch",
            route_mismatch=True,
            action="route_wrong",
        )
        skill = make_feedback(
            "feedback-skill",
            event_type="skill_candidate",
            skill_candidate={
                "detected": True,
                "source": "route_mismatch",
                "requires_human_review": True,
                "metadata": {"no_auto_modify": True},
            },
        )

        result = FeedbackLearningPolicy().learn(make_learning_input(route, skill))

        self.assertEqual(len(result.routing_candidates), 2)
        for candidate in result.routing_candidates:
            self.assertEqual(candidate.status, "pending")
            self.assertTrue(candidate.requires_human_review)
            self.assertTrue(candidate.metadata["no_auto_modify"])
            self.assertEqual(candidate.proposed_action, "review_route_or_skill_candidate")

    def test_feedback_events_reject_raw_payload_fields(self) -> None:
        with self.assertRaisesRegex(MemoryPrivacyError, "raw_payload"):
            FeedbackLearningPolicy().learn(
                make_learning_input(make_feedback("feedback-unsafe", raw_payload={"body": "unsafe"}))
            )


if __name__ == "__main__":
    unittest.main()
