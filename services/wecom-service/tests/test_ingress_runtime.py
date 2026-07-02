from __future__ import annotations

import unittest
from dataclasses import dataclass, field

from platform_contract.enums import AsyncTaskState, InterruptStatus
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

from wecom_service import WeComRuntimeIngress
from wecom_service.session_runtime import WeComSessionRuntimeAction


FIXED_NOW = "2026-07-02T01:00:00Z"


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


class WeComRuntimeIngressTests(unittest.IsolatedAsyncioTestCase):
    async def test_sanitized_callback_continue_reaches_runtime_create_run_with_context_refs(self) -> None:
        runtime = RecordingRuntime()
        ingress = self.ingress(runtime, base_metadata={"raw_payload_refs": ("fixture://tenant/bootstrap",)})

        outcome = await ingress.handle_callback(
            self.callback("msg-continue-001", "继续处理刚才的问题"),
            received_at=FIXED_NOW,
            recent_session=self.recent_session(),
            metadata={
                "recent_turn_refs": ("fixture://turns/recent-001",),
                "memory_refs": ("fixture://memory/approved-001",),
                "feedback_correction_refs": ("fixture://feedback/correction-001",),
                "artifact_refs": ("fixture://artifacts/prior.docx",),
                "output_constraints_ref": "fixture://output-constraints/lawyer-assistant",
                "output_policy_ref": "fixture://output-policy/lawyer-assistant",
            },
        )

        self.assertEqual(outcome.action, WeComSessionRuntimeAction.CONTINUE_SESSION)
        self.assertEqual(outcome.run_id, "created-001")
        self.assertEqual(runtime.resumed, [])
        self.assertEqual(len(runtime.created), 1)
        created = runtime.created[0]
        self.assertEqual(created.turn.content, "继续处理刚才的问题")
        self.assertEqual(created.session_id, "session-recent-001")
        self.assertEqual(created.metadata["source"], "wecom_session_runtime")
        self.assertEqual(created.metadata["session_resolution_action"], "continue_session")
        self.assertEqual(created.metadata["recent_turn_refs"], ["fixture://turns/recent-001"])
        self.assertEqual(created.metadata["memory_refs"], ["fixture://memory/approved-001"])
        self.assertEqual(created.metadata["feedback_correction_refs"], ["fixture://feedback/correction-001"])
        self.assertEqual(created.metadata["artifact_refs"], ["fixture://artifacts/prior.docx"])
        self.assertEqual(created.metadata["output_policy_ref"], "fixture://output-policy/lawyer-assistant")
        self.assertIn("fixture://tenant/bootstrap", created.metadata["raw_payload_refs"])
        self.assertIn("fixture://wecom/callback/msg-continue-001", created.metadata["raw_payload_refs"])

    async def test_sanitized_callback_without_recent_session_starts_new_runtime_run(self) -> None:
        runtime = RecordingRuntime()
        ingress = self.ingress(runtime)

        outcome = await ingress.handle_callback(
            self.callback("msg-new-001", "帮我起草一个新的会议通知"),
            received_at=FIXED_NOW,
        )

        self.assertEqual(outcome.action, WeComSessionRuntimeAction.START_NEW_SESSION)
        self.assertEqual(outcome.run_id, "created-001")
        self.assertEqual(runtime.resumed, [])
        self.assertEqual(len(runtime.created), 1)
        self.assertEqual(runtime.created[0].session_id, outcome.decision.session_id)
        self.assertEqual(runtime.created[0].metadata["session_resolution_reason"], "no_recent_session")

    async def test_pending_clarification_callback_uses_resume_interrupt_not_create_run(self) -> None:
        interrupt_store = InMemoryInterruptStore(clock=FakeRuntimeClock(start=FIXED_NOW), id_factory=FakeIdFactory())
        pending = interrupt_store.create_clarification(
            scope=self.scope,
            run_id="run-waiting-001",
            session_id="session-waiting-001",
            prompt_ref="fixture://prompts/clarify-001",
            resume_state_ref="fixture://resume/run-waiting-001",
            reason="backend_needs_clarification",
        )
        runtime = RecordingRuntime(interrupt_store=interrupt_store)
        ingress = self.ingress(runtime, interrupt_store=interrupt_store)

        outcome = await ingress.handle_callback(
            self.callback("msg-answer-001", "选择第二个方案"),
            received_at=FIXED_NOW,
            recent_session=self.recent_session(session_id="session-waiting-001", last_run_id="run-waiting-001"),
        )

        self.assertEqual(outcome.action, WeComSessionRuntimeAction.RESUME_INTERRUPT)
        self.assertEqual(outcome.run_id, "resumed-001")
        self.assertEqual(runtime.created, [])
        self.assertEqual(len(runtime.resumed), 1)
        self.assertEqual(runtime.resumed[0][0], pending.event.interrupt_id)
        self.assertEqual(interrupt_store.get(pending.event.interrupt_id).event.status, InterruptStatus.RESOLVED)

    def ingress(
        self,
        runtime: RecordingRuntime,
        *,
        interrupt_store: InMemoryInterruptStore | None = None,
        base_metadata: dict[str, object] | None = None,
    ) -> WeComRuntimeIngress:
        return WeComRuntimeIngress(
            runtime=runtime,
            solution=SolutionBinding(solution_id="solution-lawyer-assistant-001", version="1.0.0"),
            tenant_id=self.scope.tenant_id,
            workspace_id=self.scope.workspace_id,
            bot_instance_id=self.scope.bot_instance_id,
            interrupt_store=interrupt_store,
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
            default_thread_id=self.scope.thread_id,
            base_metadata=base_metadata,
        )

    @property
    def scope(self) -> SessionScope:
        return SessionScope(
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            channel_id="wecom",
            user_id="user-001",
            bot_instance_id="bot-001",
            conversation_id="conversation-001",
            thread_id="thread-001",
        )

    def recent_session(
        self,
        *,
        session_id: str = "session-recent-001",
        last_run_id: str = "run-recent-001",
    ) -> SessionSnapshot:
        return SessionSnapshot(
            scope=self.scope,
            session_id=session_id,
            status="open",
            updated_at=FIXED_NOW,
            last_run_id=last_run_id,
            last_run_status="running",
        )

    def callback(self, message_id: str, content: str) -> dict[str, object]:
        return {
            "MsgId": message_id,
            "FromUserName": self.scope.user_id,
            "ChatId": self.scope.conversation_id,
            "MsgType": "text",
            "Content": content,
            "CreateTime": "1782963600",
            "RawPayloadRef": f"fixture://wecom/callback/{message_id}",
            "thread_id": self.scope.thread_id,
        }


if __name__ == "__main__":
    unittest.main()
