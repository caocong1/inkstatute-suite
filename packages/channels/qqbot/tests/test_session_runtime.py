"""Wave 0+ unit tests for QQBotSessionRuntime (SESS-01 / SESS-02)."""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field

from platform_contract.enums import AsyncTaskState, Channel, MessageType
from platform_contract.events import AgentTurn
from platform_runtime import (
    ActiveTaskSnapshot,
    FakeIdFactory,
    FakeRuntimeClock,
    InMemoryInterruptStore,
    Run,
    RunRequest,
    SessionScope,
    SessionSnapshot,
    SolutionBinding,
)

from inkstatute_channels_qqbot.session_runtime import (
    QQBotSessionRuntime,
    QQBotSessionRuntimeAction,
)

FIXED_NOW = "2026-06-29T03:00:00Z"
OPENID = "openid-lawyer-001"


@dataclass(slots=True)
class RecordingRuntime:
    calls: list[tuple[str, SessionScope, RunRequest, str | None]] = field(default_factory=list)
    created: list[RunRequest] = field(default_factory=list)
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
        self.calls.append((interrupt_id, scope, req, idempotency_key))
        run_id = f"resumed-{len(self.calls):03d}"
        if self.interrupt_store is not None:
            self.interrupt_store.resolve(
                interrupt_id=interrupt_id,
                scope=scope,
                turn_id=req.turn.turn_id,
                answer_text=req.turn.content,
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


class QQBotSessionRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_continue_session_calls_create_run(self) -> None:
        runtime = RecordingRuntime()
        helper = QQBotSessionRuntime(
            runtime=runtime,
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )

        outcome = await helper.handle_turn(
            turn=self.turn("turn-continue-001", "继续刚才的问题"),
            scope=self.scope,
            run_request=self.run_request("turn-continue-001", "继续刚才的问题"),
            recent_session=self.recent_session(),
            idempotency_key="idem-continue-001",
        )

        self.assertEqual(outcome.action, QQBotSessionRuntimeAction.CONTINUE_SESSION)
        self.assertEqual(outcome.run_id, "created-001")
        self.assertEqual(runtime.calls, [])
        self.assertEqual(len(runtime.created), 1)
        created = runtime.created[0]
        self.assertEqual(created.session_id, "session-recent-001")
        self.assertEqual(created.metadata["source"], "qqbot_session_runtime")
        self.assertEqual(created.metadata["session_resolution_action"], "continue_session")
        self.assertTrue(outcome.evidence["runtime_create_called"])

    async def test_start_new_session_calls_create_run(self) -> None:
        runtime = RecordingRuntime()
        helper = QQBotSessionRuntime(runtime=runtime, id_factory=FakeIdFactory())

        outcome = await helper.handle_turn(
            turn=self.turn("turn-start-001", "新任务：起草一个通知"),
            scope=self.scope,
            run_request=self.run_request("turn-start-001", "新任务：起草一个通知"),
            recent_session=None,
            idempotency_key="idem-start-001",
        )

        self.assertEqual(outcome.action, QQBotSessionRuntimeAction.START_NEW_SESSION)
        self.assertEqual(outcome.run_id, "created-001")
        self.assertEqual(runtime.calls, [])
        self.assertEqual(len(runtime.created), 1)
        self.assertEqual(runtime.created[0].session_id, outcome.decision.session_id)
        self.assertEqual(runtime.created[0].metadata["session_resolution_reason"], "no_recent_session")

    async def test_pending_interrupt_resume(self) -> None:
        interrupt_store = self.interrupt_store()
        pending = interrupt_store.create_clarification(
            scope=self.scope,
            run_id="run-waiting-001",
            session_id="session-waiting-001",
            prompt_ref="fixture://phase64/prompts/clarify-001",
            resume_state_ref="runtime://phase64/continuation-state/run-waiting-001",
            reason="backend_needs_clarification",
        )
        runtime = RecordingRuntime(interrupt_store=interrupt_store)
        helper = QQBotSessionRuntime(
            runtime=runtime,
            interrupt_store=interrupt_store,
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )

        outcome = await helper.handle_turn(
            turn=self.turn("turn-answer-001", "synthetic clarification answer"),
            scope=self.scope,
            run_request=self.run_request("turn-answer-001", "synthetic clarification answer"),
            idempotency_key="idem-answer-001",
        )

        self.assertEqual(outcome.action, QQBotSessionRuntimeAction.RESUME_INTERRUPT)
        self.assertEqual(outcome.decision.action.value, "resume_interrupt")
        self.assertEqual(outcome.decision.interrupt_id, pending.event.interrupt_id)
        self.assertEqual(outcome.run_id, "resumed-001")
        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(runtime.created, [])
        self.assertEqual(runtime.calls[0][0], pending.event.interrupt_id)
        self.assertTrue(outcome.evidence["resume_attempted"])

    async def test_duplicate_answer_ignored(self) -> None:
        interrupt_store = self.interrupt_store()
        interrupt_store.create_clarification(
            scope=self.scope,
            run_id="run-waiting-001",
            session_id="session-waiting-001",
            prompt_ref="fixture://phase64/prompts/clarify-001",
            resume_state_ref="runtime://phase64/continuation-state/run-waiting-001",
            reason="backend_needs_clarification",
        )
        runtime = RecordingRuntime(interrupt_store=interrupt_store)
        helper = QQBotSessionRuntime(
            runtime=runtime,
            interrupt_store=interrupt_store,
            id_factory=FakeIdFactory(),
        )
        kwargs = {
            "turn": self.turn("turn-answer-003", "synthetic answer"),
            "scope": self.scope,
            "run_request": self.run_request("turn-answer-003", "synthetic answer"),
            "idempotency_key": "idem-duplicate-001",
        }

        first = await helper.handle_turn(**kwargs)
        duplicate = await helper.handle_turn(**kwargs)

        self.assertEqual(first.action, QQBotSessionRuntimeAction.RESUME_INTERRUPT)
        self.assertEqual(duplicate.action, QQBotSessionRuntimeAction.DUPLICATE_ANSWER_IGNORED)
        self.assertEqual(duplicate.run_id, first.run_id)
        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(runtime.created, [])
        self.assertFalse(duplicate.evidence["resume_attempted"])
        self.assertFalse(duplicate.evidence["runtime_resume_called"])

    async def test_expired_interrupt(self) -> None:
        interrupt_store = self.interrupt_store()
        expired_scope = self.scope_for(conversation_id=f"qqbot:c2c:{OPENID}:{OPENID}")
        expired = interrupt_store.create_clarification(
            scope=expired_scope,
            run_id="run-expired-001",
            session_id="session-expired-001",
            prompt_ref="fixture://phase64/prompts/expired",
            resume_state_ref="runtime://phase64/continuation-state/expired",
            reason="backend_needs_clarification",
            expires_at="2026-06-29T02:00:00Z",
        )
        runtime = RecordingRuntime(interrupt_store=interrupt_store)
        helper = QQBotSessionRuntime(
            runtime=runtime,
            interrupt_store=interrupt_store,
            id_factory=FakeIdFactory(),
        )

        outcome = await helper.handle_turn(
            turn=self.turn("turn-expired", "synthetic answer", scope=expired_scope),
            scope=expired_scope,
            run_request=self.run_request("turn-expired", "synthetic answer", scope=expired_scope),
            now=FIXED_NOW,
        )

        self.assertEqual(outcome.action, QQBotSessionRuntimeAction.INTERRUPT_EXPIRED)
        self.assertFalse(outcome.evidence["resume_attempted"])
        self.assertEqual(runtime.calls, [])
        self.assertEqual(runtime.created, [])
        self.assertEqual(interrupt_store.get(expired.event.interrupt_id).event.status.value, "expired")

    async def test_active_task_follow_up_returns_outcome_without_create_run(self) -> None:
        runtime = RecordingRuntime()
        helper = QQBotSessionRuntime(
            runtime=runtime,
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )

        outcome = await helper.handle_turn(
            turn=self.turn("turn-followup-001", "现在进度怎么样了？"),
            scope=self.scope,
            run_request=self.run_request("turn-followup-001", "现在进度怎么样了？"),
            active_task=self.active_task(),
            recent_session=self.recent_session(),
        )

        self.assertEqual(outcome.action, QQBotSessionRuntimeAction.ACTIVE_TASK_FOLLOW_UP)
        self.assertEqual(runtime.calls, [])
        self.assertEqual(runtime.created, [])
        self.assertFalse(outcome.evidence["resume_attempted"])
        self.assertNotIn("active_task_route", outcome.evidence)

    async def test_mismatched_turn_scope_rejected(self) -> None:
        other_scope = self.scope_for(user_id="other-openid")
        runtime = RecordingRuntime()
        helper = QQBotSessionRuntime(runtime=runtime, id_factory=FakeIdFactory())

        with self.assertRaisesRegex(ValueError, "scope mismatch"):
            await helper.handle_turn(
                turn=self.turn("turn-mismatch", "synthetic answer", scope=self.scope),
                scope=other_scope,
                run_request=self.run_request("turn-mismatch", "synthetic answer", scope=self.scope),
            )

        self.assertEqual(runtime.calls, [])
        self.assertEqual(runtime.created, [])

    def interrupt_store(self) -> InMemoryInterruptStore:
        return InMemoryInterruptStore(clock=FakeRuntimeClock(start=FIXED_NOW), id_factory=FakeIdFactory())

    @property
    def scope(self) -> SessionScope:
        return self.scope_for()

    def scope_for(
        self,
        *,
        user_id: str = OPENID,
        conversation_id: str | None = None,
        scene: str = "c2c",
        scene_id: str | None = None,
    ) -> SessionScope:
        resolved_scene_id = scene_id or user_id
        resolved_conversation_id = conversation_id or f"qqbot:{scene}:{resolved_scene_id}:{user_id}"
        return SessionScope(
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            channel_id="qqbot",
            user_id=user_id,
            bot_instance_id="bot-001",
            conversation_id=resolved_conversation_id,
            thread_id=None,
        )

    def turn(self, turn_id: str, content: str, *, scope: SessionScope | None = None) -> AgentTurn:
        resolved_scope = scope or self.scope
        return AgentTurn(
            turn_id=turn_id,
            conversation_id=resolved_scope.conversation_id,
            channel=Channel.QQBOT,
            user_id=resolved_scope.user_id,
            message_type=MessageType.TEXT,
            received_at=FIXED_NOW,
            content=content,
            metadata={"raw_payload_ref": f"fixture://phase64/payloads/{turn_id}"},
        )

    def run_request(self, turn_id: str, content: str, *, scope: SessionScope | None = None) -> RunRequest:
        resolved_scope = scope or self.scope
        return RunRequest(
            turn=self.turn(turn_id, content, scope=resolved_scope),
            solution=SolutionBinding(solution_id="solution-lawyer-assistant-001", version="1.0.0"),
            tenant_id=resolved_scope.tenant_id,
            workspace_id=resolved_scope.workspace_id,
            bot_instance_id=resolved_scope.bot_instance_id,
            session_id="session-waiting-001",
            metadata={"request_ref": f"runtime://phase64/requests/{turn_id}"},
        )

    def recent_session(self, *, scope: SessionScope | None = None) -> SessionSnapshot:
        return self.session_snapshot(scope=scope, status="open", updated_at="2026-06-29T02:59:00Z", last_run_status="running")

    def session_snapshot(
        self,
        *,
        scope: SessionScope | None = None,
        status: str = "open",
        updated_at: str = "2026-06-29T02:59:00Z",
        last_run_status: str = "running",
    ) -> SessionSnapshot:
        resolved_scope = scope or self.scope
        return SessionSnapshot(
            scope=resolved_scope,
            session_id="session-recent-001",
            status=status,
            updated_at=updated_at,
            last_run_id="run-recent-001",
            last_run_status=last_run_status,
        )

    def active_task(self, *, scope: SessionScope | None = None) -> ActiveTaskSnapshot:
        resolved_scope = scope or self.scope
        return ActiveTaskSnapshot(
            scope=resolved_scope,
            task_id="task-active-001",
            status="running",
            updated_at=FIXED_NOW,
            run_id="run-active-001",
            session_id="session-active-001",
            metadata={"raw_payload_ref": "runtime://phase64/active-task"},
        )


class SceneIsolationTests(QQBotSessionRuntimeTests):
    async def test_scene_isolation_c2c_vs_group(self) -> None:
        interrupt_store = self.interrupt_store()
        c2c_scope = self.scope_for(scene="c2c", scene_id=OPENID, user_id=OPENID)
        group_scope = self.scope_for(scene="group", scene_id="group-openid-001", user_id=OPENID)
        self.assertTrue(c2c_scope.conversation_id.startswith("qqbot:c2c:"))
        self.assertTrue(group_scope.conversation_id.startswith("qqbot:group:"))
        self.assertNotEqual(c2c_scope.conversation_id, group_scope.conversation_id)

        pending = interrupt_store.create_clarification(
            scope=c2c_scope,
            run_id="run-c2c-waiting-001",
            session_id="session-c2c-waiting-001",
            prompt_ref="fixture://phase64/prompts/c2c-clarify",
            resume_state_ref="runtime://phase64/continuation-state/c2c",
            reason="backend_needs_clarification",
        )
        runtime = RecordingRuntime(interrupt_store=interrupt_store)
        helper = QQBotSessionRuntime(
            runtime=runtime,
            interrupt_store=interrupt_store,
            id_factory=FakeIdFactory(),
        )

        group_outcome = await helper.handle_turn(
            turn=self.turn("turn-group-001", "group answer should not resume c2c", scope=group_scope),
            scope=group_scope,
            run_request=self.run_request(
                "turn-group-001",
                "group answer should not resume c2c",
                scope=group_scope,
            ),
            recent_session=None,
        )

        self.assertNotEqual(group_outcome.action, QQBotSessionRuntimeAction.RESUME_INTERRUPT)
        self.assertEqual(group_outcome.action, QQBotSessionRuntimeAction.START_NEW_SESSION)
        self.assertEqual(runtime.calls, [])
        self.assertEqual(len(runtime.created), 1)
        self.assertIsNotNone(interrupt_store.pending_for_scope(c2c_scope))
        self.assertEqual(
            interrupt_store.get(pending.event.interrupt_id).event.status.value,
            "waiting_for_user",
        )

        c2c_outcome = await helper.handle_turn(
            turn=self.turn("turn-c2c-answer-001", "c2c clarification answer", scope=c2c_scope),
            scope=c2c_scope,
            run_request=self.run_request("turn-c2c-answer-001", "c2c clarification answer", scope=c2c_scope),
            idempotency_key="idem-c2c-answer-001",
        )

        self.assertEqual(c2c_outcome.action, QQBotSessionRuntimeAction.RESUME_INTERRUPT)
        self.assertEqual(c2c_outcome.decision.interrupt_id, pending.event.interrupt_id)
        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(runtime.calls[0][0], pending.event.interrupt_id)


if __name__ == "__main__":
    unittest.main()
