"""Wave 0+ unit tests for QQBotRuntimeIngress (SESS-01 / SESS-02)."""

from __future__ import annotations

import json
import unittest
from dataclasses import dataclass, field
from pathlib import Path

from platform_contract.enums import AsyncTaskState
from platform_runtime import (
    FakeIdFactory,
    FakeRuntimeClock,
    InMemoryInterruptStore,
    Run,
    RunRequest,
    SessionScope,
    SessionSnapshot,
    SolutionBinding,
)

from inkstatute_channels_qqbot.ingress_runtime import QQBotRuntimeIngress
from inkstatute_channels_qqbot.session_runtime import QQBotSessionRuntimeAction

FIXED_NOW = "2026-07-09T03:00:00Z"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
C2C_OPENID = "FIXTURE_USER_OPENID_C2C_001"
GROUP_OPENID = "FIXTURE_GROUP_OPENID_001"
MEMBER_OPENID = "FIXTURE_MEMBER_OPENID_001"
C2C_CONVERSATION_ID = f"qqbot:c2c:{C2C_OPENID}:{C2C_OPENID}"
GROUP_CONVERSATION_ID = f"qqbot:group:{GROUP_OPENID}:{MEMBER_OPENID}"


@dataclass(slots=True)
class RecordingRuntime:
    created: list[RunRequest] = field(default_factory=list)
    resumed: list[tuple[str, SessionScope, RunRequest, str | None]] = field(default_factory=list)
    interrupt_store: InMemoryInterruptStore | None = None

    async def create_run(self, req: RunRequest) -> Run:
        self.created.append(req)
        run_id = f"created-{len(self.created):03d}"
        return Run(
            run_id=run_id,
            status=AsyncTaskState.RUNNING,
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            metadata={"session_id": req.session_id},
        )

    async def resume_interrupt(
        self,
        *,
        interrupt_id: str,
        scope: SessionScope,
        req: RunRequest,
        idempotency_key: str | None = None,
    ) -> Run:
        self.resumed.append((interrupt_id, scope, req, idempotency_key))
        run_id = f"resumed-{len(self.resumed):03d}"
        if self.interrupt_store is not None:
            self.interrupt_store.resolve(
                interrupt_id=interrupt_id,
                scope=scope,
                turn_id=req.turn.turn_id,
                answer_text=req.turn.content or "",
                idempotency_key=idempotency_key,
                metadata={
                    "backend_resume_submitted": True,
                    "resumed_backend_run_id": run_id,
                },
            )
        return Run(
            run_id=run_id,
            status=AsyncTaskState.RUNNING,
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            metadata={"interrupt_id": interrupt_id, "session_id": req.session_id},
        )


class QQBotIngressRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_c2c_callback_wires_to_create_run(self) -> None:
        runtime = RecordingRuntime()
        ingress = self.ingress(runtime)

        outcome = await ingress.handle_callback(
            self.envelope("qqbot_c2c_message.json"),
            received_at=FIXED_NOW,
            recent_session=self.recent_session(scope=self.c2c_scope),
        )

        self.assertIn(
            outcome.action,
            {
                QQBotSessionRuntimeAction.CONTINUE_SESSION,
                QQBotSessionRuntimeAction.START_NEW_SESSION,
            },
        )
        self.assertEqual(runtime.resumed, [])
        self.assertEqual(len(runtime.created), 1)
        created = runtime.created[0]
        self.assertEqual(created.turn.channel.value if hasattr(created.turn.channel, "value") else created.turn.channel, "qqbot")
        self.assertTrue(created.turn.conversation_id.startswith("qqbot:c2c:"))
        self.assertEqual(created.turn.conversation_id, C2C_CONVERSATION_ID)
        self.assertEqual(created.turn.user_id, C2C_OPENID)
        self.assertEqual(created.metadata.get("source"), "qqbot_ingress_runtime")

    async def test_group_callback_wires_scene_id(self) -> None:
        runtime = RecordingRuntime()
        ingress = self.ingress(runtime)

        outcome = await ingress.handle_callback(
            self.envelope("qqbot_group_at_message.json"),
            received_at=FIXED_NOW,
        )

        self.assertIn(
            outcome.action,
            {
                QQBotSessionRuntimeAction.CONTINUE_SESSION,
                QQBotSessionRuntimeAction.START_NEW_SESSION,
            },
        )
        self.assertEqual(len(runtime.created), 1)
        created = runtime.created[0]
        self.assertTrue(created.turn.conversation_id.startswith("qqbot:group:"))
        self.assertEqual(created.turn.conversation_id, GROUP_CONVERSATION_ID)
        self.assertEqual(created.turn.user_id, MEMBER_OPENID)
        self.assertEqual(created.metadata.get("source"), "qqbot_ingress_runtime")

    async def test_pending_interrupt_resume_via_ingress(self) -> None:
        interrupt_store = InMemoryInterruptStore(
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )
        pending = interrupt_store.create_clarification(
            scope=self.c2c_scope,
            run_id="run-waiting-001",
            session_id="session-waiting-001",
            prompt_ref="fixture://phase64/prompts/clarify-001",
            resume_state_ref="runtime://phase64/continuation-state/run-waiting-001",
            reason="backend_needs_clarification",
        )
        runtime = RecordingRuntime(interrupt_store=interrupt_store)
        ingress = self.ingress(runtime, interrupt_store=interrupt_store)

        outcome = await ingress.handle_callback(
            self.envelope("qqbot_c2c_message.json"),
            received_at=FIXED_NOW,
            recent_session=self.recent_session(
                scope=self.c2c_scope,
                session_id="session-waiting-001",
                last_run_id="run-waiting-001",
            ),
        )

        self.assertEqual(outcome.action, QQBotSessionRuntimeAction.RESUME_INTERRUPT)
        self.assertEqual(outcome.run_id, "resumed-001")
        self.assertEqual(runtime.created, [])
        self.assertEqual(len(runtime.resumed), 1)
        self.assertEqual(runtime.resumed[0][0], pending.event.interrupt_id)
        self.assertEqual(runtime.resumed[0][1].conversation_id, C2C_CONVERSATION_ID)

    async def test_interaction_skipped(self) -> None:
        runtime = RecordingRuntime()
        ingress = self.ingress(runtime)

        outcome = await ingress.handle_callback(
            self.envelope("qqbot_interaction_create.json"),
            received_at=FIXED_NOW,
        )

        self.assertEqual(outcome.action, QQBotSessionRuntimeAction.SKIPPED_NON_MESSAGE)
        self.assertIsNone(outcome.run_id)
        self.assertEqual(runtime.created, [])
        self.assertEqual(runtime.resumed, [])
        self.assertEqual(outcome.evidence.get("ingress_status"), "skipped_non_message")
        self.assertIn("interaction", str(outcome.evidence.get("category", "")).lower())

    async def test_validation_challenge_skipped(self) -> None:
        runtime = RecordingRuntime()
        ingress = self.ingress(runtime)

        outcome = await ingress.handle_callback(
            self.envelope("qqbot_validation_challenge.json"),
            received_at=FIXED_NOW,
        )

        self.assertEqual(outcome.action, QQBotSessionRuntimeAction.SKIPPED_NON_MESSAGE)
        self.assertIsNone(outcome.run_id)
        self.assertEqual(runtime.created, [])
        self.assertEqual(runtime.resumed, [])
        self.assertEqual(outcome.evidence.get("ingress_status"), "skipped_non_message")
        self.assertIn("validation", str(outcome.evidence.get("category", "")).lower())

    async def test_run_metadata_source_and_privacy(self) -> None:
        runtime = RecordingRuntime()
        ingress = self.ingress(
            runtime,
            base_metadata={"raw_payload_refs": ("fixture://tenant/bootstrap",)},
        )

        outcome = await ingress.handle_callback(
            self.envelope("qqbot_c2c_message.json", raw_payload_ref="fixture://qqbot/callback/c2c-001"),
            received_at=FIXED_NOW,
            metadata={
                "recent_turn_refs": ("fixture://turns/recent-001",),
                "privacy": "no_raw_payload_or_legal_text_stored",
            },
        )

        self.assertIn(
            outcome.action,
            {
                QQBotSessionRuntimeAction.CONTINUE_SESSION,
                QQBotSessionRuntimeAction.START_NEW_SESSION,
            },
        )
        self.assertEqual(len(runtime.created), 1)
        created = runtime.created[0]
        self.assertEqual(created.metadata["source"], "qqbot_ingress_runtime")
        self.assertIn("privacy", created.metadata)
        self.assertIn("no_raw", str(created.metadata["privacy"]))
        self.assertIn("current_turn_ref", created.metadata)
        self.assertIn("raw_payload_refs", created.metadata)
        for forbidden in (
            "raw_payload",
            "full_text",
            "raw_text",
            "document_text",
            "case_facts",
            "customer_document_text",
            "payload_text",
        ):
            self.assertNotIn(forbidden, created.metadata)

    def ingress(
        self,
        runtime: RecordingRuntime,
        *,
        interrupt_store: InMemoryInterruptStore | None = None,
        base_metadata: dict[str, object] | None = None,
    ) -> QQBotRuntimeIngress:
        return QQBotRuntimeIngress(
            runtime=runtime,
            solution=SolutionBinding(solution_id="solution-lawyer-assistant-001", version="1.0.0"),
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            bot_instance_id="bot-001",
            interrupt_store=interrupt_store,
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
            base_metadata=base_metadata,
        )

    @property
    def c2c_scope(self) -> SessionScope:
        return SessionScope(
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            channel_id="qqbot",
            user_id=C2C_OPENID,
            bot_instance_id="bot-001",
            conversation_id=C2C_CONVERSATION_ID,
            thread_id=None,
        )

    def recent_session(
        self,
        *,
        scope: SessionScope,
        session_id: str = "session-recent-001",
        last_run_id: str = "run-recent-001",
    ) -> SessionSnapshot:
        return SessionSnapshot(
            scope=scope,
            session_id=session_id,
            status="open",
            updated_at=FIXED_NOW,
            last_run_id=last_run_id,
            last_run_status="running",
        )

    def envelope(self, fixture_name: str, *, raw_payload_ref: str | None = None) -> dict[str, object]:
        payload = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
        envelope = dict(payload["envelope"])
        if raw_payload_ref is not None:
            envelope["raw_payload_ref"] = raw_payload_ref
        elif "raw_payload_ref" not in envelope:
            envelope["raw_payload_ref"] = f"fixture://qqbot/{fixture_name}"
        return envelope


if __name__ == "__main__":
    unittest.main()
