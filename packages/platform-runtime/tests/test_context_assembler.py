from __future__ import annotations

from dataclasses import replace
import unittest

from platform_runtime import (
    ActiveTaskSnapshot,
    ContextAssembler,
    ContextAssemblyBudgetError,
    ContextAssemblyInput,
    ContextAssemblyPolicy,
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


def make_context_input(**overrides: object) -> ContextAssemblyInput:
    scope = overrides.get("scope", make_scope())
    values = {
        "scope": scope,
        "session_id": "session-001",
        "turn_id": "turn-001",
        "current_turn_ref": "fixture://turns/current",
        "current_turn_text": "客户补充了不能进入上下文事件的具体事实。",
        "current_turn_raw_payload_ref": "fixture://payloads/current",
        "run_id": "run-001",
        "recent_turn_refs": tuple(f"fixture://turns/recent-{index:03d}" for index in range(10)),
        "active_task": ActiveTaskSnapshot(
            scope=scope,
            task_id="task-001",
            run_id="run-active",
            session_id="session-001",
            status="running",
            updated_at=FIXED_NOW,
            metadata={"state_ref": "fixture://tasks/task-001"},
        ),
        "active_task_refs": ("fixture://tasks/task-001",),
        "artifact_refs": tuple(f"fixture://artifacts/{index:03d}" for index in range(6)),
        "feedback_correction_refs": tuple(f"fixture://feedback/correction-{index:03d}" for index in range(4)),
        "pending_interrupt": PendingInterruptSnapshot(
            scope=scope,
            interrupt_id="interrupt-001",
            run_id="run-interrupt",
            session_id="session-001",
            status="waiting_for_user",
            created_at=FIXED_NOW,
            prompt_ref="fixture://prompts/interrupt-001",
            resume_state_ref="fixture://resume/interrupt-001",
        ),
        "rolling_summary": make_summary(scope=scope),
        "memory_refs": tuple(f"fixture://memory/{index:03d}" for index in range(5)),
        "output_constraints_ref": "fixture://output-constraints/001",
        "output_policy_ref": "fixture://output-policy/001",
        "raw_payload_refs": ("fixture://payloads/attachment-001",),
        "industry_context": {"industry_ref": "fixture://industry/context-001"},
        "metadata": {"input_ref": "fixture://context-input/001"},
    }
    values.update(overrides)
    return ContextAssemblyInput(**values)


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
        with self.assertRaisesRegex(ValueError, "forbidden payload_text"):
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


class ContextAssemblerBudgetTests(unittest.TestCase):
    def test_assemble_returns_schema_shaped_context_bundle_with_all_sources(self) -> None:
        assembler = ContextAssembler(
            policy=ContextAssemblyPolicy(budget_tokens=4096, max_recent_turn_refs=6),
            clock=lambda: FIXED_NOW,
            id_factory=lambda prefix: f"{prefix}-001",
        )

        result = assembler.assemble(make_context_input())
        event = result.as_event()
        bundle = result.bundle

        self.assertEqual(bundle.context_bundle_id, "context-bundle-001")
        self.assertEqual(bundle.tenant_id, "tenant-001")
        self.assertEqual(bundle.workspace_id, "workspace-001")
        self.assertEqual(bundle.session_id, "session-001")
        self.assertEqual(bundle.turn_id, "turn-001")
        self.assertEqual(bundle.run_id, "run-001")
        self.assertEqual(bundle.summary_ref, "fixture://summaries/session-001")
        self.assertEqual(bundle.interrupt_id, "interrupt-001")
        self.assertEqual(bundle.trim_strategy, "protected_then_feedback_memory_recent_artifact")
        self.assertEqual(bundle.recent_turn_refs, [f"fixture://turns/recent-{index:03d}" for index in range(6)])
        self.assertIn("fixture://tasks/task-001", bundle.active_task_refs)
        self.assertEqual(len(bundle.artifact_refs), 6)
        self.assertIn("fixture://memory/000", bundle.memory_refs)
        self.assertIn("fixture://payloads/current", bundle.raw_payload_refs)
        self.assertEqual(bundle.industry_context["industry_ref"], "fixture://industry/context-001")
        self.assertEqual(event["metadata"]["current_turn_ref"], "fixture://turns/current")
        self.assertEqual(event["metadata"]["feedback_correction_refs"], [f"fixture://feedback/correction-{index:03d}" for index in range(4)])

    def test_long_conversation_is_bounded_and_records_dropped_sections(self) -> None:
        input_record = make_context_input(
            recent_turn_refs=tuple(f"fixture://turns/recent-{index:03d}" for index in range(80)),
            artifact_refs=tuple(f"fixture://artifacts/{index:03d}" for index in range(20)),
            feedback_correction_refs=tuple(f"fixture://feedback/correction-{index:03d}" for index in range(12)),
            memory_refs=tuple(f"fixture://memory/{index:03d}" for index in range(20)),
        )
        policy = ContextAssemblyPolicy(
            budget_tokens=220,
            max_recent_turn_refs=12,
            max_artifact_refs=10,
            max_feedback_correction_refs=5,
            max_memory_refs=8,
        )

        result = ContextAssembler(policy=policy, clock=lambda: FIXED_NOW, id_factory=lambda prefix: f"{prefix}-trim").assemble(input_record)

        self.assertLess(len(result.bundle.recent_turn_refs), len(input_record.recent_turn_refs))
        self.assertLessEqual(len(result.bundle.recent_turn_refs), policy.max_recent_turn_refs)
        self.assertLessEqual(len(result.bundle.artifact_refs), policy.max_artifact_refs)
        self.assertLessEqual(result.estimated_tokens, policy.budget_tokens)
        self.assertGreater(result.dropped_sections["recent_turn_refs"], 0)
        self.assertGreater(result.dropped_sections["artifact_refs"], 0)
        self.assertNotIn("recent-079", repr(result.as_event()))

    def test_protected_sections_survive_trimming(self) -> None:
        policy = ContextAssemblyPolicy(
            budget_tokens=185,
            max_recent_turn_refs=20,
            max_artifact_refs=20,
            max_feedback_correction_refs=10,
            max_memory_refs=20,
        )

        result = ContextAssembler(policy=policy, clock=lambda: FIXED_NOW, id_factory=lambda prefix: f"{prefix}-protected").assemble(
            make_context_input(recent_turn_refs=tuple(f"fixture://turns/recent-{index:03d}" for index in range(60)))
        )
        event = result.as_event()

        self.assertEqual(result.bundle.turn_id, "turn-001")
        self.assertEqual(result.bundle.interrupt_id, "interrupt-001")
        self.assertEqual(event["metadata"]["pending_clarification_ref"], "fixture://prompts/interrupt-001")
        self.assertEqual(event["metadata"]["resume_state_ref"], "fixture://resume/interrupt-001")
        self.assertEqual(event["metadata"]["output_constraints_ref"], "fixture://output-constraints/001")
        self.assertEqual(event["metadata"]["output_policy_ref"], "fixture://output-policy/001")
        self.assertEqual(event["metadata"]["current_turn_ref"], "fixture://turns/current")
        self.assertEqual(event["metadata"]["current_turn_text_length"], len("客户补充了不能进入上下文事件的具体事实。"))
        self.assertIn("current_turn", result.protected_sections)
        self.assertIn("pending_clarification", result.protected_sections)
        self.assertIn("output_policy", result.protected_sections)

    def test_impossible_budget_fails_closed_before_bundle_creation(self) -> None:
        with self.assertRaises(ContextAssemblyBudgetError):
            ContextAssembler(
                policy=ContextAssemblyPolicy(budget_tokens=8),
                clock=lambda: FIXED_NOW,
                id_factory=lambda prefix: f"{prefix}-too-small",
            ).assemble(make_context_input())

    def test_assembly_is_deterministic_and_serialization_excludes_raw_text(self) -> None:
        input_record = make_context_input()
        policy = ContextAssemblyPolicy(budget_tokens=260, max_recent_turn_refs=8)
        assembler = ContextAssembler(policy=policy, clock=lambda: FIXED_NOW, id_factory=lambda prefix: f"{prefix}-det")

        first = assembler.assemble(input_record).as_event()
        second = assembler.assemble(input_record).as_event()

        self.assertEqual(first, second)
        self.assertNotIn(input_record.current_turn_text, repr(first))
        self.assertNotIn("这是不能进入事件的完整摘要文本", repr(first))
        self.assertRegex(first["metadata"]["current_turn_text_sha256_16"], r"^[0-9a-f]{16}$")


if __name__ == "__main__":
    unittest.main()
