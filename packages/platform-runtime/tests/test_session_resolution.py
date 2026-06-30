from __future__ import annotations

from dataclasses import replace
import unittest

from platform_runtime import (
    ActiveTaskSnapshot,
    InMemoryContractLogStore,
    InMemorySessionResolutionStore,
    PendingInterruptSnapshot,
    SessionResolutionAction,
    SessionResolutionPolicy,
    SessionScope,
    SessionSnapshot,
    resolve_session_turn,
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


def make_session(**overrides: object) -> SessionSnapshot:
    values = {
        "scope": make_scope(),
        "session_id": "session-001",
        "status": "active",
        "updated_at": "2026-07-01T07:59:00Z",
        "last_run_id": "run-001",
        "last_run_status": "running",
    }
    values.update(overrides)
    return SessionSnapshot(**values)


class SessionResolutionPolicyTests(unittest.TestCase):
    def test_recent_viable_session_continues_without_session_command(self) -> None:
        decision = resolve_session_turn(
            scope=make_scope(),
            text="继续刚才的问题，补充一个事实。",
            raw_payload_ref="fixture://payloads/turn-001",
            recent_session=make_session(),
            policy=SessionResolutionPolicy(default_idle_window_seconds=600),
            now=FIXED_NOW,
            id_factory=lambda prefix: f"{prefix}-001",
        )

        self.assertEqual(decision.action, SessionResolutionAction.CONTINUE_SESSION)
        self.assertEqual(decision.reason, "recent_viable_session")
        self.assertEqual(decision.session_id, "session-001")
        self.assertNotIn("继续刚才的问题", repr(decision.as_event()))

    def test_pending_interrupt_precedes_active_task_and_recent_session(self) -> None:
        decision = resolve_session_turn(
            scope=make_scope(),
            text="选择第二个方案。",
            raw_payload_ref="fixture://payloads/turn-002",
            recent_session=make_session(),
            active_task=ActiveTaskSnapshot(
                scope=make_scope(),
                task_id="task-001",
                run_id="run-active",
                session_id="session-active",
                status="running",
                updated_at="2026-07-01T07:58:00Z",
            ),
            pending_interrupt=PendingInterruptSnapshot(
                scope=make_scope(),
                interrupt_id="interrupt-001",
                run_id="run-interrupt",
                session_id="session-interrupt",
                status="waiting_for_user",
                created_at="2026-07-01T07:55:00Z",
                expires_at="2026-07-01T08:05:00Z",
                prompt_ref="fixture://prompts/interrupt-001",
                resume_state_ref="fixture://resume/interrupt-001",
            ),
            now=FIXED_NOW,
            id_factory=lambda prefix: f"{prefix}-002",
        )

        self.assertEqual(decision.action, SessionResolutionAction.RESUME_INTERRUPT)
        self.assertEqual(decision.reason, "pending_interrupt_precedence")
        self.assertEqual(decision.interrupt_id, "interrupt-001")
        self.assertEqual(decision.run_id, "run-interrupt")

    def test_active_task_precedes_recent_session_continuation(self) -> None:
        decision = resolve_session_turn(
            scope=make_scope(),
            text="处理到哪一步了？",
            raw_payload_ref="fixture://payloads/turn-003",
            recent_session=make_session(),
            active_task=ActiveTaskSnapshot(
                scope=make_scope(),
                task_id="task-001",
                run_id="run-active",
                session_id="session-active",
                status="running",
                updated_at="2026-07-01T07:58:00Z",
            ),
            now=FIXED_NOW,
            id_factory=lambda prefix: f"{prefix}-003",
        )

        self.assertEqual(decision.action, SessionResolutionAction.ACTIVE_TASK_FOLLOW_UP)
        self.assertEqual(decision.reason, "active_task_precedence")
        self.assertEqual(decision.task_id, "task-001")
        self.assertEqual(decision.session_id, "session-active")

    def test_new_task_stale_terminal_session_or_terminal_run_starts_new_session(self) -> None:
        scenarios = [
            ("新任务：帮我起草一份会议通知。", make_session(), "new_task_signal"),
            ("继续。", make_session(updated_at="2026-07-01T06:00:00Z"), "session_idle_window_expired"),
            ("继续。", make_session(status="closed"), "terminal_session_status"),
            ("继续。", make_session(last_run_status="succeeded"), "terminal_prior_run_status"),
        ]

        for index, (text, session, reason) in enumerate(scenarios, start=1):
            with self.subTest(reason=reason):
                decision = resolve_session_turn(
                    scope=make_scope(),
                    text=text,
                    raw_payload_ref=f"fixture://payloads/turn-new-{index}",
                    recent_session=session,
                    policy=SessionResolutionPolicy(default_idle_window_seconds=600),
                    now=FIXED_NOW,
                    id_factory=lambda prefix, i=index: f"{prefix}-{i:03d}",
                )

                self.assertEqual(decision.action, SessionResolutionAction.START_NEW_SESSION)
                self.assertEqual(decision.reason, reason)
                self.assertTrue(decision.session_id.startswith("session-"))

    def test_serialized_decision_is_reference_first_and_excludes_input_text(self) -> None:
        text = "客户说合同里有很长的具体事实，不应该进入决策记录。"

        decision = resolve_session_turn(
            scope=make_scope(),
            text=text,
            raw_payload_ref="fixture://payloads/turn-privacy",
            recent_session=make_session(),
            now=FIXED_NOW,
            id_factory=lambda prefix: f"{prefix}-privacy",
        )
        event = decision.as_event()

        self.assertEqual(event["event"], "session_resolution")
        self.assertEqual(event["text_length"], len(text))
        self.assertRegex(event["text_sha256_16"], r"^[0-9a-f]{16}$")
        self.assertEqual(event["raw_payload_ref"], "fixture://payloads/turn-privacy")
        self.assertEqual(event["action"], "continue_session")
        self.assertEqual(event["reason"], "recent_viable_session")
        self.assertNotIn("text", event)
        self.assertNotIn(text, repr(event))


class InMemorySessionResolutionStoreTests(unittest.TestCase):
    def test_scope_isolation_for_pending_interrupt_and_session_lookup(self) -> None:
        store = InMemorySessionResolutionStore(clock=lambda: FIXED_NOW)
        current_scope = make_scope()
        other_scope = make_scope(user_id="user-002")
        store.upsert_session(make_session(scope=other_scope, session_id="session-other"))
        store.upsert_pending_interrupt(
            PendingInterruptSnapshot(
                scope=other_scope,
                interrupt_id="interrupt-other",
                run_id="run-other",
                session_id="session-other",
                status="waiting_for_user",
                created_at=FIXED_NOW,
            )
        )

        self.assertIsNone(store.get_session(current_scope))
        self.assertIsNone(store.get_pending_interrupt(current_scope))

    def test_store_reads_are_copy_safe(self) -> None:
        store = InMemorySessionResolutionStore(clock=lambda: FIXED_NOW)
        scope = make_scope()
        store.upsert_session(make_session(scope=scope, metadata={"safe_ref": "fixture://sessions/1"}))

        returned = store.get_session(scope)
        self.assertIsNotNone(returned)
        returned.metadata["safe_ref"] = "mutated"

        self.assertEqual(store.get_session(scope).metadata["safe_ref"], "fixture://sessions/1")

    def test_decision_events_are_copy_safe_and_contract_log_append_is_optional(self) -> None:
        store = InMemorySessionResolutionStore(clock=lambda: FIXED_NOW)
        contract_log = InMemoryContractLogStore(clock=lambda: FIXED_NOW)
        decision = resolve_session_turn(
            scope=make_scope(),
            text="继续",
            raw_payload_ref="fixture://payloads/turn-record",
            recent_session=make_session(),
            now=FIXED_NOW,
            id_factory=lambda prefix: f"{prefix}-record",
        )

        event = store.record_decision(decision, contract_log_store=contract_log)
        event["metadata"]["privacy"] = "mutated"

        self.assertEqual(store.decision_events()[0]["metadata"]["privacy"], "no_raw_payload_or_legal_text_stored")
        self.assertEqual(contract_log.entries()[0].event_key, "session_resolution")
        self.assertEqual(contract_log.entries()[0].event["text_length"], 2)
        self.assertNotIn("继续", repr(contract_log.entries()[0].to_dict()))

    def test_store_resolve_uses_scoped_snapshots_without_raw_text_storage(self) -> None:
        store = InMemorySessionResolutionStore(clock=lambda: FIXED_NOW)
        scope = make_scope()
        store.upsert_session(make_session(scope=scope))

        decision = store.resolve(
            scope=scope,
            text="继续处理这个事项。",
            raw_payload_ref="fixture://payloads/store-resolve",
            id_factory=lambda prefix: f"{prefix}-store",
        )
        event = store.record_decision(decision)

        self.assertEqual(decision.action, SessionResolutionAction.CONTINUE_SESSION)
        self.assertEqual(event["scope"]["tenant_id"], "tenant-001")
        self.assertEqual(event["raw_payload_ref"], "fixture://payloads/store-resolve")
        self.assertNotIn("继续处理", repr(store.decision_events()))

    def test_rejects_or_excludes_forbidden_metadata_before_storage(self) -> None:
        store = InMemorySessionResolutionStore(clock=lambda: FIXED_NOW)
        scope = make_scope()

        with self.assertRaisesRegex(ValueError, "forbidden raw_payload"):
            store.upsert_session(make_session(scope=scope, metadata={"raw_payload": "secret"}))

        with self.assertRaisesRegex(ValueError, "full-text payload"):
            store.upsert_pending_interrupt(
                PendingInterruptSnapshot(
                    scope=scope,
                    interrupt_id="interrupt-001",
                    run_id="run-001",
                    session_id="session-001",
                    status="waiting_for_user",
                    created_at=FIXED_NOW,
                    metadata={"payload_text": "secret"},
                )
            )

        decision = resolve_session_turn(
            scope=scope,
            text="继续",
            recent_session=make_session(scope=scope),
            now=FIXED_NOW,
            id_factory=lambda prefix: f"{prefix}-privacy",
        )
        unsafe_decision = replace(decision, metadata={"full_text": "secret"})

        with self.assertRaisesRegex(ValueError, "full-text payload"):
            store.record_decision(unsafe_decision)


if __name__ == "__main__":
    unittest.main()
