from __future__ import annotations

import json
import unittest
from dataclasses import dataclass, field

from platform_contract.enums import AsyncTaskState, Channel, InterruptStatus, MessageType
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

from wecom_service.active_task_router import ActiveTaskRoute, AdapterTaskCapabilities
from wecom_service.session_runtime import (
    WeComSessionRuntime,
    WeComSessionRuntimeAction,
    build_clarification_delivery,
)


FIXED_NOW = "2026-06-29T03:00:00Z"


@dataclass(slots=True)
class RecordingRuntime:
    calls: list[tuple[str, SessionScope, RunRequest, str | None]] = field(default_factory=list)
    interrupt_store: InMemoryInterruptStore | None = None

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


class WeComSessionRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_pending_interrupt_resume_uses_next_wecom_answer_without_command(self) -> None:
        interrupt_store = self.interrupt_store()
        pending = interrupt_store.create_clarification(
            scope=self.scope,
            run_id="run-waiting-001",
            session_id="session-waiting-001",
            prompt_ref="fixture://phase15/prompts/clarify-001",
            resume_state_ref="runtime://phase15/continuation-state/run-waiting-001",
            reason="backend_needs_clarification",
        )
        runtime = RecordingRuntime()
        helper = WeComSessionRuntime(
            runtime=runtime,
            interrupt_store=interrupt_store,
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )

        outcome = await helper.handle_turn(
            turn=self.turn("turn-answer-001", "synthetic clarification answer"),
            scope=self.scope,
            run_request=self.run_request("turn-answer-001", "synthetic clarification answer"),
            active_task=self.active_task(),
            idempotency_key="idem-answer-001",
        )

        self.assertEqual(outcome.action, WeComSessionRuntimeAction.RESUME_INTERRUPT)
        self.assertEqual(outcome.decision.action.value, "resume_interrupt")
        self.assertEqual(outcome.decision.interrupt_id, pending.event.interrupt_id)
        self.assertEqual(outcome.run_id, "resumed-001")
        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(runtime.calls[0][0], pending.event.interrupt_id)
        self.assertFalse(outcome.evidence["session_command_required"])
        self.assertEqual(outcome.evidence["ordinary_user_command_surface"], "none")
        self.assertNotIn("/resume", json.dumps(outcome.as_event(), ensure_ascii=False))

    async def test_cross_user_pending_interrupt_does_not_resume(self) -> None:
        interrupt_store = self.interrupt_store()
        interrupt_store.create_clarification(
            scope=self.scope_for(user_id="other-user"),
            run_id="run-other-001",
            session_id="session-other-001",
            prompt_ref="fixture://phase15/prompts/other",
            resume_state_ref="runtime://phase15/continuation-state/other",
            reason="backend_needs_clarification",
        )
        runtime = RecordingRuntime(interrupt_store=interrupt_store)
        helper = WeComSessionRuntime(runtime=runtime, interrupt_store=interrupt_store, id_factory=FakeIdFactory())

        outcome = await helper.handle_turn(
            turn=self.turn("turn-answer-002", "synthetic answer"),
            scope=self.scope,
            run_request=self.run_request("turn-answer-002", "synthetic answer"),
            recent_session=None,
        )

        self.assertEqual(outcome.action, WeComSessionRuntimeAction.START_NEW_SESSION)
        self.assertEqual(runtime.calls, [])
        self.assertEqual(outcome.evidence["scope_isolation"], "tenant_workspace_channel_user_bot_session_thread")

    async def test_mismatched_turn_and_scope_is_rejected_before_resume(self) -> None:
        interrupt_store = self.interrupt_store()
        other_scope = self.scope_for(user_id="other-user")
        interrupt_store.create_clarification(
            scope=other_scope,
            run_id="run-other-001",
            session_id="session-other-001",
            prompt_ref="fixture://phase15/prompts/other",
            resume_state_ref="runtime://phase15/continuation-state/other",
            reason="backend_needs_clarification",
        )
        runtime = RecordingRuntime(interrupt_store=interrupt_store)
        helper = WeComSessionRuntime(runtime=runtime, interrupt_store=interrupt_store, id_factory=FakeIdFactory())

        with self.assertRaisesRegex(ValueError, "scope mismatch"):
            await helper.handle_turn(
                turn=self.turn("turn-mismatch", "synthetic answer", scope=self.scope),
                scope=other_scope,
                run_request=self.run_request("turn-mismatch", "synthetic answer", scope=self.scope),
            )

        self.assertEqual(runtime.calls, [])

    async def test_active_task_precedence_routes_fast_control_plane(self) -> None:
        runtime = RecordingRuntime()
        helper = WeComSessionRuntime(runtime=runtime, id_factory=FakeIdFactory())

        outcome = await helper.handle_turn(
            turn=self.turn("turn-followup-001", "现在进度怎么样了？"),
            scope=self.scope,
            run_request=self.run_request("turn-followup-001", "现在进度怎么样了？"),
            active_task=self.active_task(),
            capabilities=AdapterTaskCapabilities(supports_parallel_tasks=False),
            recent_session=self.recent_session(),
        )

        self.assertEqual(outcome.action, WeComSessionRuntimeAction.ACTIVE_TASK_FOLLOW_UP)
        self.assertEqual(outcome.active_task_route.route, ActiveTaskRoute.STATUS_REQUEST)
        self.assertEqual(outcome.active_task_route.reason, "status_query_answered_by_fast_control_plane")
        self.assertEqual(runtime.calls, [])
        self.assertEqual(outcome.evidence["active_task_route"], "status_request")

    async def test_stale_terminal_and_new_task_start_new_session(self) -> None:
        helper = WeComSessionRuntime(runtime=RecordingRuntime(), id_factory=FakeIdFactory())
        cases = (
            (
                "stale",
                self.turn("turn-stale", "synthetic continuation"),
                self.session_snapshot(updated_at="2026-06-29T01:00:00Z", status="open", last_run_status="running"),
                "session_idle_window_expired",
            ),
            (
                "terminal_session",
                self.turn("turn-terminal-session", "synthetic continuation"),
                self.session_snapshot(status="closed", last_run_status="running"),
                "terminal_session_status",
            ),
            (
                "terminal_run",
                self.turn("turn-terminal-run", "synthetic continuation"),
                self.session_snapshot(status="open", last_run_status="succeeded"),
                "terminal_prior_run_status",
            ),
            (
                "new_task_signal",
                self.turn("turn-new-task", "另外再帮我做一个新任务"),
                self.recent_session(),
                "new_task_signal",
            ),
        )

        for name, turn, session, reason in cases:
            with self.subTest(name=name):
                outcome = await helper.handle_turn(
                    turn=turn,
                    scope=self.scope,
                    run_request=self.run_request(turn.turn_id, turn.content or ""),
                    recent_session=session,
                    now=FIXED_NOW,
                )

                self.assertEqual(outcome.action, WeComSessionRuntimeAction.START_NEW_SESSION)
                self.assertEqual(outcome.decision.reason, reason)
                self.assertEqual(outcome.evidence["decision_action"], "start_new_session")

    async def test_duplicate_timeout_and_cancel_behavior_is_idempotent(self) -> None:
        interrupt_store = self.interrupt_store()
        active = interrupt_store.create_clarification(
            scope=self.scope,
            run_id="run-waiting-001",
            session_id="session-waiting-001",
            prompt_ref="fixture://phase15/prompts/clarify-001",
            resume_state_ref="runtime://phase15/continuation-state/run-waiting-001",
            reason="backend_needs_clarification",
        )
        expired_scope = self.scope_for(user_id="expired-user")
        expired = interrupt_store.create_clarification(
            scope=expired_scope,
            run_id="run-expired-001",
            session_id="session-expired-001",
            prompt_ref="fixture://phase15/prompts/expired",
            resume_state_ref="runtime://phase15/continuation-state/expired",
            reason="backend_needs_clarification",
            expires_at="2026-06-29T02:00:00Z",
        )
        cancelled_scope = self.scope_for(user_id="cancelled-user")
        cancelled = interrupt_store.create_clarification(
            scope=cancelled_scope,
            run_id="run-cancelled-001",
            session_id="session-cancelled-001",
            prompt_ref="fixture://phase15/prompts/cancelled",
            resume_state_ref="runtime://phase15/continuation-state/cancelled",
            reason="backend_needs_clarification",
        )
        interrupt_store.cancel(interrupt_id=cancelled.event.interrupt_id, scope=cancelled_scope)
        runtime = RecordingRuntime(interrupt_store=interrupt_store)
        helper = WeComSessionRuntime(runtime=runtime, interrupt_store=interrupt_store, id_factory=FakeIdFactory())

        first = await helper.handle_turn(
            turn=self.turn("turn-answer-003", "synthetic answer"),
            scope=self.scope,
            run_request=self.run_request("turn-answer-003", "synthetic answer"),
            idempotency_key="idem-duplicate-001",
        )
        duplicate = await helper.handle_turn(
            turn=self.turn("turn-answer-003", "synthetic answer"),
            scope=self.scope,
            run_request=self.run_request("turn-answer-003", "synthetic answer"),
            idempotency_key="idem-duplicate-001",
        )
        timeout = await helper.handle_turn(
            turn=self.turn("turn-expired", "synthetic answer", scope=expired_scope),
            scope=expired_scope,
            run_request=self.run_request("turn-expired", "synthetic answer", scope=expired_scope),
            now=FIXED_NOW,
        )
        cancelled_outcome = await helper.handle_turn(
            turn=self.turn("turn-cancelled", "synthetic answer", scope=cancelled_scope),
            scope=cancelled_scope,
            run_request=self.run_request("turn-cancelled", "synthetic answer", scope=cancelled_scope),
            now=FIXED_NOW,
        )

        self.assertEqual(first.action, WeComSessionRuntimeAction.RESUME_INTERRUPT)
        self.assertEqual(duplicate.action, WeComSessionRuntimeAction.DUPLICATE_ANSWER_IGNORED)
        self.assertTrue(duplicate.evidence["duplicate"])
        self.assertFalse(duplicate.evidence["resume_attempted"])
        self.assertFalse(duplicate.evidence["runtime_resume_called"])
        self.assertEqual(len(runtime.calls), 1)
        self.assertEqual(interrupt_store.get(active.event.interrupt_id).event.status, InterruptStatus.RESOLVED)
        self.assertEqual(timeout.action, WeComSessionRuntimeAction.INTERRUPT_EXPIRED)
        self.assertEqual(interrupt_store.get(expired.event.interrupt_id).event.status, InterruptStatus.EXPIRED)
        self.assertEqual(cancelled_outcome.action, WeComSessionRuntimeAction.START_NEW_SESSION)
        self.assertEqual(interrupt_store.get(cancelled.event.interrupt_id).event.status, InterruptStatus.CANCELLED)

    async def test_duplicate_answer_after_helper_restart_uses_interrupt_store_metadata(self) -> None:
        interrupt_store = self.interrupt_store()
        active = interrupt_store.create_clarification(
            scope=self.scope,
            run_id="run-waiting-001",
            session_id="session-waiting-001",
            prompt_ref="fixture://phase15/prompts/clarify-001",
            resume_state_ref="runtime://phase15/continuation-state/run-waiting-001",
            reason="backend_needs_clarification",
        )
        first_runtime = RecordingRuntime(interrupt_store=interrupt_store)
        first_helper = WeComSessionRuntime(runtime=first_runtime, interrupt_store=interrupt_store, id_factory=FakeIdFactory())
        first = await first_helper.handle_turn(
            turn=self.turn("turn-answer-retry", "synthetic answer"),
            scope=self.scope,
            run_request=self.run_request("turn-answer-retry", "synthetic answer"),
            idempotency_key="idem-retry-001",
        )

        second_runtime = RecordingRuntime(interrupt_store=interrupt_store)
        restarted_helper = WeComSessionRuntime(
            runtime=second_runtime,
            interrupt_store=interrupt_store,
            id_factory=FakeIdFactory(),
        )
        duplicate = await restarted_helper.handle_turn(
            turn=self.turn("turn-answer-retry", "synthetic answer"),
            scope=self.scope,
            run_request=self.run_request("turn-answer-retry", "synthetic answer"),
            idempotency_key="idem-retry-001",
        )

        self.assertEqual(first.action, WeComSessionRuntimeAction.RESUME_INTERRUPT)
        self.assertEqual(duplicate.action, WeComSessionRuntimeAction.DUPLICATE_ANSWER_IGNORED)
        self.assertEqual(duplicate.run_id, first.run_id)
        self.assertEqual(duplicate.evidence["interrupt_id"], active.event.interrupt_id)
        self.assertFalse(duplicate.evidence["resume_attempted"])
        self.assertFalse(duplicate.evidence["runtime_resume_called"])
        self.assertEqual(len(first_runtime.calls), 1)
        self.assertEqual(second_runtime.calls, [])

    def test_clarification_delivery_uses_send_envelope_and_output_policy(self) -> None:
        allowed = build_clarification_delivery(to_user="lawyer-001", text="请补充一个非敏感的确认选项。")
        rewritten = build_clarification_delivery(to_user="lawyer-001", text="gateway restarted and online")
        blocked = build_clarification_delivery(to_user="lawyer-001", text="/help debug profile path /home/operator")

        self.assertEqual(allowed["msgtype"], "text")
        self.assertEqual(allowed["policy"]["action"], "allow")
        self.assertEqual(rewritten["msgtype"], "text")
        self.assertEqual(rewritten["policy"]["action"], "rewrite")
        self.assertTrue(rewritten["text"]["content"])
        self.assertEqual(blocked["policy"]["action"], "block")
        self.assertNotIn("msgtype", blocked)
        self.assertNotIn("gateway restarted", json.dumps(rewritten, ensure_ascii=False).lower())
        self.assertNotIn("/home/operator", json.dumps(blocked, ensure_ascii=False))

    def interrupt_store(self) -> InMemoryInterruptStore:
        return InMemoryInterruptStore(clock=FakeRuntimeClock(start=FIXED_NOW), id_factory=FakeIdFactory())

    @property
    def scope(self) -> SessionScope:
        return self.scope_for()

    def scope_for(self, *, user_id: str = "user-001") -> SessionScope:
        return SessionScope(
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            channel_id="wecom",
            user_id=user_id,
            bot_instance_id="bot-001",
            conversation_id=f"conversation-{user_id}",
            thread_id="thread-001",
        )

    def turn(self, turn_id: str, content: str, *, scope: SessionScope | None = None) -> AgentTurn:
        resolved_scope = scope or self.scope
        return AgentTurn(
            turn_id=turn_id,
            conversation_id=resolved_scope.conversation_id,
            channel=Channel.WECOM,
            user_id=resolved_scope.user_id,
            message_type=MessageType.TEXT,
            received_at=FIXED_NOW,
            content=content,
            metadata={"raw_payload_ref": f"fixture://phase15/payloads/{turn_id}", "thread_id": resolved_scope.thread_id},
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
            metadata={"request_ref": f"runtime://phase15/requests/{turn_id}"},
        )

    def recent_session(self) -> SessionSnapshot:
        return self.session_snapshot(status="open", updated_at="2026-06-29T02:59:00Z", last_run_status="running")

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
            metadata={"raw_payload_ref": "runtime://phase15/active-task"},
        )


if __name__ == "__main__":
    unittest.main()
