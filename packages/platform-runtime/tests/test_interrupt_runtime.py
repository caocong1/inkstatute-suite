from __future__ import annotations

import unittest

from platform_contract.enums import InterruptStatus

from platform_runtime import FakeIdFactory, FakeRuntimeClock, SessionScope
from platform_runtime.interrupts import (
    InMemoryInterruptStore,
    InterruptLifecycleAction,
)


FIXED_NOW = "2026-06-29T03:00:00Z"


def make_scope(*, user_id: str = "user-001") -> SessionScope:
    return SessionScope(
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        channel_id="wecom",
        user_id=user_id,
        bot_instance_id="bot-001",
        conversation_id="conversation-001",
        thread_id="thread-001",
    )


class InMemoryInterruptStoreTests(unittest.TestCase):
    def test_create_clarification_interrupt_persists_waiting_run_interrupt(self) -> None:
        store = InMemoryInterruptStore(clock=FakeRuntimeClock(start=FIXED_NOW), id_factory=FakeIdFactory())

        record = store.create_clarification(
            scope=make_scope(),
            run_id="run-001",
            session_id="session-001",
            prompt_ref="fixture://prompts/clarify-001",
            resume_state_ref="fixture://resume/run-001",
            reason="backend_needs_clarification",
        )

        self.assertEqual(record.event.status, InterruptStatus.WAITING_FOR_USER)
        self.assertEqual(record.event.run_id, "run-001")
        self.assertEqual(record.event.session_id, "session-001")
        self.assertEqual(record.event.prompt_ref, "fixture://prompts/clarify-001")
        self.assertEqual(record.event.resume_state_ref, "fixture://resume/run-001")
        self.assertEqual(store.pending_for_scope(make_scope()).event.interrupt_id, "interrupt-001")
        self.assertIsNone(store.pending_for_scope(make_scope(user_id="user-002")))

    def test_interrupt_metadata_keeps_question_refs_without_prompt_text(self) -> None:
        store = InMemoryInterruptStore(clock=FakeRuntimeClock(start=FIXED_NOW), id_factory=FakeIdFactory())

        record = store.create_clarification(
            scope=make_scope(),
            run_id="run-001",
            session_id="session-001",
            prompt_ref="fixture://prompts/clarify-001",
            resume_state_ref="fixture://resume/run-001",
            expected_response_schema_ref="fixture://schemas/freeform-or-choice",
            reason="backend_needs_clarification",
            metadata={
                "question_kind": "multiple_choice",
                "choice_refs": ["fixture://choices/a", "fixture://choices/b"],
            },
        )

        event = record.as_event()
        self.assertEqual(event["expected_response_schema_ref"], "fixture://schemas/freeform-or-choice")
        self.assertEqual(event["metadata"]["question_kind"], "multiple_choice")
        self.assertEqual(event["metadata"]["choice_refs"], ["fixture://choices/a", "fixture://choices/b"])
        self.assertNotIn("which option", repr(event).lower())
        self.assertNotIn("answer text", repr(event).lower())

    def test_duplicate_answer_is_ignored_without_second_mutation(self) -> None:
        store = InMemoryInterruptStore(clock=FakeRuntimeClock(start=FIXED_NOW), id_factory=FakeIdFactory())
        record = store.create_clarification(
            scope=make_scope(),
            run_id="run-001",
            session_id="session-001",
            prompt_ref="fixture://prompts/clarify-001",
            resume_state_ref="fixture://resume/run-001",
            reason="backend_needs_clarification",
        )

        first = store.resolve(
            interrupt_id=record.event.interrupt_id,
            scope=make_scope(),
            turn_id="turn-answer-001",
            answer_text="sensitive answer text",
            idempotency_key="idem-001",
        )
        duplicate = store.resolve(
            interrupt_id=record.event.interrupt_id,
            scope=make_scope(),
            turn_id="turn-answer-001",
            answer_text="sensitive answer text",
            idempotency_key="idem-001",
        )

        self.assertEqual(first.action, InterruptLifecycleAction.RESOLVED)
        self.assertEqual(duplicate.action, InterruptLifecycleAction.DUPLICATE_ANSWER_IGNORED)
        self.assertEqual(first.interrupt.event.resolved_turn_id, "turn-answer-001")
        self.assertEqual(duplicate.interrupt.event.resolved_turn_id, "turn-answer-001")
        self.assertEqual(first.interrupt.event.resolved_at, duplicate.interrupt.event.resolved_at)
        self.assertNotIn("sensitive answer text", repr(store.records()))

    def test_timeout_and_cancel_are_deterministic_and_privacy_safe(self) -> None:
        store = InMemoryInterruptStore(clock=FakeRuntimeClock(start=FIXED_NOW), id_factory=FakeIdFactory())
        expiring = store.create_clarification(
            scope=make_scope(),
            run_id="run-001",
            session_id="session-001",
            prompt_ref="fixture://prompts/clarify-001",
            resume_state_ref="fixture://resume/run-001",
            reason="backend_needs_clarification",
            expires_at="2026-06-29T03:05:00Z",
        )
        cancelled = store.create_clarification(
            scope=make_scope(user_id="user-002"),
            run_id="run-002",
            session_id="session-002",
            prompt_ref="fixture://prompts/clarify-002",
            resume_state_ref="fixture://resume/run-002",
            reason="backend_needs_clarification",
        )

        expired_decisions = store.expire_due(now="2026-06-29T03:06:00Z")
        cancel_decision = store.cancel(
            interrupt_id=cancelled.event.interrupt_id,
            scope=make_scope(user_id="user-002"),
            reason="user_cancelled",
        )
        expired_resume = store.resolve(
            interrupt_id=expiring.event.interrupt_id,
            scope=make_scope(),
            turn_id="turn-answer-002",
            answer_text="sensitive answer text",
        )

        self.assertEqual([decision.action for decision in expired_decisions], [InterruptLifecycleAction.EXPIRED])
        self.assertEqual(cancel_decision.action, InterruptLifecycleAction.CANCELLED)
        self.assertEqual(expired_resume.action, InterruptLifecycleAction.EXPIRED)
        self.assertEqual(store.get(expiring.event.interrupt_id).event.status, InterruptStatus.EXPIRED)
        self.assertEqual(store.get(cancelled.event.interrupt_id).event.status, InterruptStatus.CANCELLED)
        self.assertNotIn("sensitive answer text", repr(store.records()))


if __name__ == "__main__":
    unittest.main()
