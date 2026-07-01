from __future__ import annotations

from dataclasses import replace
import unittest

from platform_runtime import (
    ActiveTaskSnapshot,
    ContextAssemblyInput,
    InMemoryRollingSummaryStore,
    PendingInterruptSnapshot,
    RollingSummaryRecord,
    SessionScope,
)


FIXED_NOW = "2026-07-01T08:00:00Z"


def make_scope(
    *,
    tenant_id: str = "tenant-001",
    workspace_id: str = "workspace-001",
    channel_id: str = "wecom",
    user_id: str = "user-001",
    bot_instance_id: str = "bot-001",
    conversation_id: str = "conversation-001",
) -> SessionScope:
    return SessionScope(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        channel_id=channel_id,
        user_id=user_id,
        bot_instance_id=bot_instance_id,
        conversation_id=conversation_id,
    )


def make_summary(**overrides: object) -> RollingSummaryRecord:
    values = {
        "scope": make_scope(),
        "session_id": "session-001",
        "summary_ref": "fixture://summaries/session-001",
        "task_intent_refs": ("fixture://intent/001",),
        "user_constraint_refs": ("fixture://constraints/001",),
        "unanswered_question_refs": ("fixture://questions/001",),
        "artifact_refs": ("fixture://artifacts/001",),
        "outcome_refs": ("fixture://outcomes/001",),
        "text_sha256_16": "0123456789abcdef",
        "text_length": 128,
        "created_at": FIXED_NOW,
        "updated_at": FIXED_NOW,
        "metadata": {"source_ref": "fixture://summary-metadata/001"},
    }
    values.update(overrides)
    return RollingSummaryRecord(**values)


class ContextAssemblyContractTests(unittest.TestCase):
    def test_input_accepts_short_term_context_sources_without_backend_or_channel(self) -> None:
        scope = make_scope()
        input_record = ContextAssemblyInput(
            scope=scope,
            session_id="session-001",
            turn_id="turn-001",
            current_turn_ref="fixture://turns/current",
            current_turn_text="客户补充了新的事实。",
            current_turn_raw_payload_ref="fixture://payloads/current",
            recent_turn_refs=("fixture://turns/001", "fixture://turns/002"),
            active_task=ActiveTaskSnapshot(
                scope=scope,
                task_id="task-001",
                run_id="run-active",
                session_id="session-001",
                status="running",
                updated_at=FIXED_NOW,
            ),
            artifact_refs=("fixture://artifacts/draft.docx",),
            feedback_correction_refs=("fixture://feedback/correction-001",),
            pending_interrupt=PendingInterruptSnapshot(
                scope=scope,
                interrupt_id="interrupt-001",
                run_id="run-interrupt",
                session_id="session-001",
                status="waiting_for_user",
                created_at=FIXED_NOW,
                prompt_ref="fixture://prompts/interrupt-001",
                resume_state_ref="fixture://resume/interrupt-001",
            ),
            rolling_summary=make_summary(scope=scope),
            memory_refs=("fixture://short-term-memory/001",),
            output_constraints_ref="fixture://output-constraints/001",
            metadata={"input_ref": "fixture://context-input/001"},
        )

        self.assertEqual(input_record.scope, scope)
        self.assertEqual(input_record.current_turn_ref, "fixture://turns/current")
        self.assertEqual(input_record.recent_turn_refs, ("fixture://turns/001", "fixture://turns/002"))
        self.assertEqual(input_record.active_task.task_id, "task-001")
        self.assertEqual(input_record.pending_interrupt.interrupt_id, "interrupt-001")
        self.assertEqual(input_record.rolling_summary.summary_ref, "fixture://summaries/session-001")
        self.assertEqual(input_record.feedback_correction_refs, ("fixture://feedback/correction-001",))

    def test_rolling_summary_event_is_reference_first_and_excludes_summary_full_text(self) -> None:
        summary_text = "这是不能进入事件的完整摘要文本。"
        summary = make_summary(metadata={"summary_text_ref": "fixture://summaries/text-ref"})

        event = summary.as_event()

        self.assertEqual(event["event"], "rolling_summary")
        self.assertEqual(event["summary_ref"], "fixture://summaries/session-001")
        self.assertEqual(event["task_intent_refs"], ["fixture://intent/001"])
        self.assertEqual(event["user_constraint_refs"], ["fixture://constraints/001"])
        self.assertEqual(event["unanswered_question_refs"], ["fixture://questions/001"])
        self.assertEqual(event["artifact_refs"], ["fixture://artifacts/001"])
        self.assertEqual(event["outcome_refs"], ["fixture://outcomes/001"])
        self.assertEqual(event["text_sha256_16"], "0123456789abcdef")
        self.assertEqual(event["text_length"], 128)
        self.assertEqual(event["scope"]["tenant_id"], "tenant-001")
        self.assertNotIn("summary_text", event)
        self.assertNotIn(summary_text, repr(event))

    def test_forbidden_full_text_metadata_is_rejected_before_storage_or_serialization(self) -> None:
        forbidden_keys = [
            "raw_payload",
            "raw_text",
            "payload_text",
            "full_text",
            "document_text",
            "customer_document_text",
            "case_facts",
        ]

        for key in forbidden_keys:
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "forbidden"):
                    make_summary(metadata={key: "sensitive text"}).as_event()

        store = InMemoryRollingSummaryStore(clock=lambda: FIXED_NOW)
        with self.assertRaisesRegex(ValueError, "full-text payload"):
            store.upsert(make_summary(metadata={"payload_text": "sensitive text"}))


class InMemoryRollingSummaryStoreTests(unittest.TestCase):
    def test_store_is_scoped_and_never_returns_another_user_summary(self) -> None:
        store = InMemoryRollingSummaryStore(clock=lambda: FIXED_NOW)
        current_scope = make_scope()
        other_scope = make_scope(user_id="user-002")

        store.upsert(make_summary(scope=other_scope, session_id="session-other", summary_ref="fixture://summaries/other"))

        self.assertIsNone(store.get(current_scope, "session-other"))
        self.assertEqual(store.list_for_scope(current_scope), ())

    def test_store_reads_are_copy_safe(self) -> None:
        store = InMemoryRollingSummaryStore(clock=lambda: FIXED_NOW)
        scope = make_scope()
        store.upsert(make_summary(scope=scope))

        returned = store.get(scope, "session-001")
        self.assertIsNotNone(returned)
        mutated = replace(returned, metadata={"source_ref": "mutated"})

        self.assertEqual(mutated.metadata["source_ref"], "mutated")
        self.assertEqual(store.get(scope, "session-001").metadata["source_ref"], "fixture://summary-metadata/001")


if __name__ == "__main__":
    unittest.main()
