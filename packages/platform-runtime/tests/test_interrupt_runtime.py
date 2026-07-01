from __future__ import annotations

import unittest

from platform_contract.enums import AgentResultStatus, AsyncTaskState, Channel, InterruptStatus, MessageType
from platform_contract.events import AgentTurn

from platform_runtime import (
    DefaultRunRuntime,
    FakeBackendAdapter,
    FakeIdFactory,
    FakeRuntimeClock,
    InMemoryContractLogStore,
    RuntimeFeatureFlags,
    RunRequest,
    SessionScope,
    SolutionBinding,
)
from platform_runtime.interrupts import (
    InMemoryInterruptStore,
    InterruptLifecycleAction,
)


FIXED_NOW = "2026-06-29T03:00:00Z"


class FlakyResumeBackend(FakeBackendAdapter):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.resume_failures_remaining = 1

    async def submit_run(self, req: RunRequest):
        if "interrupt_id" in req.metadata and self.resume_failures_remaining > 0:
            self.resume_failures_remaining -= 1
            self.submitted_requests.append(req)
            raise RuntimeError("backend resume unavailable")
        return await super().submit_run(req)


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


def make_run_request(*, turn_id: str = "turn-001", content: str = "synthetic request") -> RunRequest:
    return RunRequest(
        turn=AgentTurn(
            turn_id=turn_id,
            conversation_id="conversation-001",
            channel=Channel.WECOM,
            user_id="user-001",
            message_type=MessageType.TEXT,
            received_at=FIXED_NOW,
            content=content,
            metadata={"raw_payload_ref": f"fixture://payloads/{turn_id}", "thread_id": "thread-001"},
        ),
        solution=SolutionBinding(solution_id="solution-001", version="1.0.0"),
        tenant_id="tenant-001",
        workspace_id="workspace-001",
        bot_instance_id="bot-001",
        session_id="session-001",
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


class DefaultRunRuntimeInterruptTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_run_records_waiting_interrupt_from_clarification_result(self) -> None:
        clock = FakeRuntimeClock(start=FIXED_NOW)
        id_factory = FakeIdFactory()
        backend = FakeBackendAdapter(
            clock=clock,
            id_factory=id_factory,
            clarification_result={
                "prompt_ref": "fixture://prompts/clarify-001",
                "resume_state_ref": "fixture://resume/run-001",
                "expected_response_schema_ref": "fixture://schemas/clarify-answer",
                "question_kind": "freeform",
            },
        )
        interrupt_store = InMemoryInterruptStore(clock=clock, id_factory=id_factory)
        contract_log = InMemoryContractLogStore(clock=clock.now)
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(run_runtime_enabled=True, contract_log_enabled=True),
            contract_log_store=contract_log,
            interrupt_store=interrupt_store,
            clock=clock,
            id_factory=id_factory,
        )

        run = await runtime.create_run(make_run_request())

        self.assertEqual(run.status, AsyncTaskState.WAITING_FOR_USER)
        self.assertIsNotNone(run.result)
        self.assertEqual(run.result.status, AgentResultStatus.NEEDS_CLARIFICATION)
        pending = interrupt_store.pending_for_scope(make_scope())
        self.assertIsNotNone(pending)
        self.assertEqual(pending.event.prompt_ref, "fixture://prompts/clarify-001")
        self.assertEqual(pending.event.resume_state_ref, "fixture://resume/run-001")
        self.assertEqual(pending.event.expected_response_schema_ref, "fixture://schemas/clarify-answer")
        self.assertEqual(pending.event.metadata["question_kind"], "freeform")
        self.assertIn("run_interrupt", [entry.event_key for entry in contract_log.entries()])
        self.assertNotIn("synthetic request", repr([entry.to_dict() for entry in contract_log.entries()]))

    async def test_resume_interrupt_submits_backend_handoff_with_sanitized_metadata(self) -> None:
        clock = FakeRuntimeClock(start=FIXED_NOW)
        id_factory = FakeIdFactory()
        backend = FakeBackendAdapter(clock=clock, id_factory=id_factory)
        interrupt_store = InMemoryInterruptStore(clock=clock, id_factory=id_factory)
        record = interrupt_store.create_clarification(
            scope=make_scope(),
            run_id="run-paused-001",
            session_id="session-001",
            prompt_ref="fixture://prompts/clarify-001",
            resume_state_ref="fixture://resume/run-paused-001",
            reason="backend_needs_clarification",
        )
        contract_log = InMemoryContractLogStore(clock=clock.now)
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(run_runtime_enabled=True, contract_log_enabled=True),
            contract_log_store=contract_log,
            interrupt_store=interrupt_store,
            clock=clock,
            id_factory=id_factory,
        )

        run = await runtime.resume_interrupt(
            interrupt_id=record.event.interrupt_id,
            scope=make_scope(),
            req=make_run_request(turn_id="turn-answer-001", content="sensitive answer text"),
            idempotency_key="idem-001",
        )
        submitted = backend.submitted_requests[-1]

        self.assertEqual(run.run_id, "run-001")
        self.assertEqual(submitted.metadata["interrupt_id"], record.event.interrupt_id)
        self.assertEqual(submitted.metadata["resume_state_ref"], "fixture://resume/run-paused-001")
        self.assertEqual(submitted.metadata["resuming_run_id"], "run-paused-001")
        self.assertEqual(submitted.metadata["resolved_idempotency_key"], "idem-001")
        self.assertEqual(submitted.metadata["answer_text_length"], len("sensitive answer text"))
        self.assertRegex(submitted.metadata["answer_text_sha256_16"], r"^[0-9a-f]{16}$")
        resolved = interrupt_store.get(record.event.interrupt_id)
        self.assertEqual(resolved.event.status, InterruptStatus.RESOLVED)
        self.assertTrue(resolved.event.metadata["backend_resume_submitted"])
        self.assertEqual(resolved.event.metadata["resumed_backend_run_id"], run.run_id)
        self.assertNotIn("sensitive answer text", repr([entry.to_dict() for entry in contract_log.entries()]))

    async def test_resume_interrupt_keeps_interrupt_waiting_when_backend_submit_fails(self) -> None:
        clock = FakeRuntimeClock(start=FIXED_NOW)
        id_factory = FakeIdFactory()
        backend = FlakyResumeBackend(clock=clock, id_factory=id_factory)
        interrupt_store = InMemoryInterruptStore(clock=clock, id_factory=id_factory)
        record = interrupt_store.create_clarification(
            scope=make_scope(),
            run_id="run-paused-001",
            session_id="session-001",
            prompt_ref="fixture://prompts/clarify-001",
            resume_state_ref="fixture://resume/run-paused-001",
            reason="backend_needs_clarification",
        )
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(run_runtime_enabled=True),
            interrupt_store=interrupt_store,
            clock=clock,
            id_factory=id_factory,
        )

        with self.assertRaisesRegex(RuntimeError, "backend resume unavailable"):
            await runtime.resume_interrupt(
                interrupt_id=record.event.interrupt_id,
                scope=make_scope(),
                req=make_run_request(turn_id="turn-answer-001", content="sensitive answer text"),
                idempotency_key="idem-001",
            )

        waiting = interrupt_store.get(record.event.interrupt_id)
        self.assertEqual(waiting.event.status, InterruptStatus.WAITING_FOR_USER)
        self.assertIsNone(waiting.event.resolved_turn_id)
        self.assertEqual(interrupt_store.pending_for_scope(make_scope()).event.interrupt_id, record.event.interrupt_id)

        retried = await runtime.resume_interrupt(
            interrupt_id=record.event.interrupt_id,
            scope=make_scope(),
            req=make_run_request(turn_id="turn-answer-001", content="sensitive answer text"),
            idempotency_key="idem-001",
        )

        self.assertEqual(retried.run_id, "run-001")
        self.assertEqual(len(backend.submitted_requests), 2)
        self.assertEqual(interrupt_store.get(record.event.interrupt_id).event.status, InterruptStatus.RESOLVED)

    async def test_duplicate_resume_idempotency_does_not_call_backend_twice(self) -> None:
        clock = FakeRuntimeClock(start=FIXED_NOW)
        id_factory = FakeIdFactory()
        backend = FakeBackendAdapter(clock=clock, id_factory=id_factory)
        interrupt_store = InMemoryInterruptStore(clock=clock, id_factory=id_factory)
        record = interrupt_store.create_clarification(
            scope=make_scope(),
            run_id="run-paused-001",
            session_id="session-001",
            prompt_ref="fixture://prompts/clarify-001",
            resume_state_ref="fixture://resume/run-paused-001",
            reason="backend_needs_clarification",
        )
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(run_runtime_enabled=True),
            interrupt_store=interrupt_store,
            clock=clock,
            id_factory=id_factory,
        )

        first = await runtime.resume_interrupt(
            interrupt_id=record.event.interrupt_id,
            scope=make_scope(),
            req=make_run_request(turn_id="turn-answer-001", content="sensitive answer text"),
            idempotency_key="idem-001",
        )
        duplicate = await runtime.resume_interrupt(
            interrupt_id=record.event.interrupt_id,
            scope=make_scope(),
            req=make_run_request(turn_id="turn-answer-001", content="sensitive answer text"),
            idempotency_key="idem-001",
        )

        self.assertEqual(first.run_id, duplicate.run_id)
        self.assertEqual(len(backend.submitted_requests), 1)


if __name__ == "__main__":
    unittest.main()
