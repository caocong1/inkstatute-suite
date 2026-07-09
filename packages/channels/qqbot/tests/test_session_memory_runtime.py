"""Wave 0 unit tests for QQBotSessionRuntime memory (SESS-03)."""

from __future__ import annotations

import json
import unittest
from dataclasses import dataclass, field
from typing import Any

from platform_contract.enums import AsyncTaskState, Channel, MessageType
from platform_contract.events import AgentTurn, ContextBundle
from platform_runtime import (
    FakeIdFactory,
    FakeMemory,
    FakeRuntimeClock,
    InMemoryInterruptStore,
    MemoryRetainResult,
    MemoryUseEvidenceError,
    Run,
    RunRequest,
    SessionScope,
    SessionSnapshot,
    SolutionBinding,
)
from platform_runtime.context_assembler import ContextAssemblyResult

from inkstatute_channels_qqbot.session_runtime import (
    QQBotMemoryFailureMode,
    QQBotMemoryIntegrationPolicy,
    QQBotMemoryRetentionScope,
    QQBotSessionRuntime,
    QQBotSessionRuntimeAction,
)


FIXED_NOW = "2026-06-29T03:00:00Z"
OPENID = "openid-lawyer-001"


@dataclass(slots=True)
class RecordingRuntime:
    created: list[RunRequest] = field(default_factory=list)
    resumed: list[tuple[str, RunRequest]] = field(default_factory=list)
    interrupt_store: InMemoryInterruptStore | None = None

    async def create_run(self, req: RunRequest) -> Run:
        self.created.append(req)
        return Run(
            run_id=f"created-{len(self.created):03d}",
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
        self.resumed.append((interrupt_id, req))
        run_id = f"resumed-{len(self.resumed):03d}"
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
            metadata={"interrupt_id": interrupt_id},
        )


@dataclass(slots=True)
class RecordingMemoryOrchestrator:
    calls: list[dict[str, Any]] = field(default_factory=list)
    status: str = "recorded"

    def recall_and_assemble(self, **kwargs: Any) -> ContextAssemblyResult:
        self.calls.append(dict(kwargs))
        return ContextAssemblyResult(
            bundle=ContextBundle(
                context_bundle_id="context-bundle-session-001",
                tenant_id=kwargs["scope"].tenant_id,
                workspace_id=kwargs["scope"].workspace_id,
                session_id=kwargs["session_id"],
                created_at=FIXED_NOW,
                budget_tokens=2048,
                run_id=kwargs.get("run_id"),
                turn_id=kwargs["turn_id"],
                recent_turn_refs=list(kwargs.get("recent_turn_refs", ())),
                summary_ref="summary://session-001/v2",
                active_task_refs=[],
                artifact_refs=list(kwargs.get("artifact_refs", ())),
                memory_refs=["memory://approved-001", "memory://approved-002"],
                raw_payload_refs=[],
                industry_context={},
                metadata={
                    "feedback_correction_refs": list(kwargs.get("feedback_correction_refs", ())),
                    "output_policy_ref": kwargs.get("output_policy_ref"),
                    "estimated_tokens": 128,
                },
            ),
            estimated_tokens=128,
            dropped_sections={"memory_refs": 0},
            protected_sections=("current_turn", "output_policy"),
            metadata={
                "memory_use_evidence_status": self.status,
                "memory_use_evidence_recorded_count": 2,
                "memory_use_evidence_privacy": "refs_ids_counts_statuses_only",
            },
        )


class FailingMemoryOrchestrator:
    def recall_and_assemble(self, **_kwargs: Any) -> ContextAssemblyResult:
        raise MemoryUseEvidenceError(
            "memory_use_evidence_record_failed",
            memory_ids=("memory://approved-001",),
            failed_count=1,
            error_class="RuntimeError",
        )


@dataclass(slots=True)
class RecordingMemory:
    """Memory port that records arecall/aretain and returns controllable results."""

    recall_texts: tuple[str, ...] = ("User prefers concise summaries.",)
    retain_count: int = 1
    arecall_calls: list[Any] = field(default_factory=list)
    aretain_calls: list[Any] = field(default_factory=list)

    async def arecall(self, input: Any) -> Any:
        self.arecall_calls.append(input)

        @dataclass(slots=True)
        class _Recalled:
            memory_id: str
            text: str

        @dataclass(slots=True)
        class _Result:
            bank_id: str
            query: str
            memories: tuple[Any, ...]

        memories = tuple(
            _Recalled(memory_id=f"memory://recall/{index}", text=text)
            for index, text in enumerate(self.recall_texts)
        )
        return _Result(bank_id="default", query=input.query, memories=memories)

    async def aretain(self, input: Any) -> MemoryRetainResult:
        self.aretain_calls.append(input)
        return MemoryRetainResult(bank_id="default", retained_count=self.retain_count)

    async def areflect(self, input: Any) -> Any:
        raise NotImplementedError

    def capability_manifest(self) -> dict[str, Any]:
        return {"adapter_id": "recording-memory"}


class FailingMemory:
    async def arecall(self, input: Any) -> Any:
        raise RuntimeError("recall failed")

    async def aretain(self, input: Any) -> Any:
        raise RuntimeError("retain failed")

    async def areflect(self, input: Any) -> Any:
        raise RuntimeError("reflect failed")

    def capability_manifest(self) -> dict[str, Any]:
        return {}


class QQBotSessionMemoryRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_continue_merges_orchestrator_context_refs(self) -> None:
        runtime = RecordingRuntime()
        orchestrator = RecordingMemoryOrchestrator()
        helper = QQBotSessionRuntime(
            runtime=runtime,
            memory_orchestrator=orchestrator,
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )

        outcome = await helper.handle_turn(
            turn=self.turn("turn-continue-001", "继续刚才的问题"),
            scope=self.scope,
            run_request=self.run_request_with_metadata(
                "turn-continue-001",
                "继续刚才的问题",
                metadata={
                    "recent_turn_refs": ("turn://recent-001",),
                    "artifact_refs": ("artifact://prior-docx",),
                    "output_policy_ref": "output-policy://lawyer-assistant",
                },
            ),
            recent_session=self.recent_session(),
        )

        self.assertEqual(outcome.action, QQBotSessionRuntimeAction.CONTINUE_SESSION)
        self.assertEqual(len(orchestrator.calls), 1)
        self.assertEqual(orchestrator.calls[0]["session_id"], "session-recent-001")
        self.assertEqual(orchestrator.calls[0]["artifact_refs"], ("artifact://prior-docx",))
        self.assertEqual(orchestrator.calls[0]["output_policy_ref"], "output-policy://lawyer-assistant")
        self.assertEqual(orchestrator.calls[0]["current_turn_text"], "继续刚才的问题")
        self.assertEqual(len(runtime.created), 1)
        metadata = runtime.created[0].metadata
        self.assertEqual(metadata["context_bundle_id"], "context-bundle-session-001")
        self.assertEqual(metadata["memory_refs"], ["memory://approved-001", "memory://approved-002"])
        self.assertEqual(metadata["summary_ref"], "summary://session-001/v2")
        self.assertEqual(metadata["artifact_refs"], ["artifact://prior-docx"])
        self.assertEqual(metadata["output_policy_ref"], "output-policy://lawyer-assistant")
        self.assertEqual(metadata["memory_use_evidence_status"], "recorded")
        self.assert_refs_only_metadata(metadata)

    async def test_resume_duplicate_expired_active_bypass_memory(self) -> None:
        interrupt_store = InMemoryInterruptStore(
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )
        pending = interrupt_store.create_clarification(
            scope=self.scope,
            run_id="run-waiting-001",
            session_id="session-waiting-001",
            prompt_ref="prompt://clarify",
            resume_state_ref="runtime://resume-state",
            reason="backend_needs_clarification",
        )
        expired_scope = self.scope_for(user_id="expired-openid")
        interrupt_store.create_clarification(
            scope=expired_scope,
            run_id="run-expired-001",
            session_id="session-expired-001",
            prompt_ref="prompt://expired",
            resume_state_ref="runtime://expired",
            reason="backend_needs_clarification",
            expires_at="2026-06-29T02:00:00Z",
        )
        runtime = RecordingRuntime(interrupt_store=interrupt_store)
        orchestrator = RecordingMemoryOrchestrator()
        memory = RecordingMemory()
        helper = QQBotSessionRuntime(
            runtime=runtime,
            interrupt_store=interrupt_store,
            memory_orchestrator=orchestrator,
            memory=memory,
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )

        resumed = await helper.handle_turn(
            turn=self.turn("turn-answer-001", "synthetic answer"),
            scope=self.scope,
            run_request=self.run_request("turn-answer-001", "synthetic answer"),
            idempotency_key="idem-answer-001",
        )
        duplicate = await helper.handle_turn(
            turn=self.turn("turn-answer-001", "synthetic answer"),
            scope=self.scope,
            run_request=self.run_request("turn-answer-001", "synthetic answer"),
            idempotency_key="idem-answer-001",
        )
        expired = await helper.handle_turn(
            turn=self.turn("turn-expired-001", "synthetic expired", scope=expired_scope),
            scope=expired_scope,
            run_request=self.run_request("turn-expired-001", "synthetic expired", scope=expired_scope),
            now=FIXED_NOW,
        )
        active = await helper.handle_turn(
            turn=self.turn("turn-active-001", "进度怎么样了？"),
            scope=self.scope,
            run_request=self.run_request("turn-active-001", "进度怎么样了？"),
            active_task={
                "task_id": "task-active-001",
                "status": "running",
                "run_id": "run-active-001",
                "session_id": "session-active-001",
            },
            recent_session=self.recent_session(),
        )

        self.assertEqual(resumed.action, QQBotSessionRuntimeAction.RESUME_INTERRUPT)
        self.assertEqual(resumed.decision.interrupt_id, pending.event.interrupt_id)
        self.assertEqual(duplicate.action, QQBotSessionRuntimeAction.DUPLICATE_ANSWER_IGNORED)
        self.assertEqual(expired.action, QQBotSessionRuntimeAction.INTERRUPT_EXPIRED)
        self.assertEqual(active.action, QQBotSessionRuntimeAction.ACTIVE_TASK_FOLLOW_UP)
        self.assertEqual(orchestrator.calls, [])
        self.assertEqual(memory.arecall_calls, [])
        self.assertEqual(runtime.created, [])

    async def test_failing_orchestrator_still_create_run(self) -> None:
        runtime = RecordingRuntime()
        helper = QQBotSessionRuntime(
            runtime=runtime,
            memory_orchestrator=FailingMemoryOrchestrator(),
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )

        outcome = await helper.handle_turn(
            turn=self.turn("turn-continue-fail", "继续"),
            scope=self.scope,
            run_request=self.run_request("turn-continue-fail", "继续"),
            recent_session=self.recent_session(),
        )

        self.assertEqual(outcome.action, QQBotSessionRuntimeAction.CONTINUE_SESSION)
        self.assertEqual(len(runtime.created), 1)
        metadata = runtime.created[0].metadata
        self.assertEqual(metadata["memory_orchestrator_status"], "degraded")
        self.assert_refs_only_metadata(metadata)

    async def test_failing_memory_recall_still_create_run(self) -> None:
        runtime = RecordingRuntime()
        helper = QQBotSessionRuntime(
            runtime=runtime,
            memory=FailingMemory(),
            memory_policy=QQBotMemoryIntegrationPolicy(failure_mode=QQBotMemoryFailureMode.FAIL_OPEN),
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )

        outcome = await helper.handle_turn(
            turn=self.turn("turn-recall-fail", "继续"),
            scope=self.scope,
            run_request=self.run_request("turn-recall-fail", "继续"),
            recent_session=self.recent_session(),
        )

        self.assertEqual(outcome.action, QQBotSessionRuntimeAction.CONTINUE_SESSION)
        self.assertEqual(len(runtime.created), 1)
        metadata = runtime.created[0].metadata
        self.assertIn("memory_recall_summary", metadata)
        self.assertEqual(metadata["memory_recall_summary"]["recalled_count"], 0)

    async def test_fail_closed_policy_opt_in(self) -> None:
        runtime = RecordingRuntime()
        helper = QQBotSessionRuntime(
            runtime=runtime,
            memory_orchestrator=FailingMemoryOrchestrator(),
            memory_policy=QQBotMemoryIntegrationPolicy(failure_mode=QQBotMemoryFailureMode.FAIL_CLOSED),
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )

        with self.assertRaises(MemoryUseEvidenceError):
            await helper.handle_turn(
                turn=self.turn("turn-fail-closed", "继续"),
                scope=self.scope,
                run_request=self.run_request("turn-fail-closed", "继续"),
                recent_session=self.recent_session(),
            )

        self.assertEqual(runtime.created, [])

    async def test_finalize_memory_retain_fail_open(self) -> None:
        runtime = RecordingRuntime()
        helper = QQBotSessionRuntime(
            runtime=runtime,
            memory=FailingMemory(),
            memory_policy=QQBotMemoryIntegrationPolicy(failure_mode=QQBotMemoryFailureMode.FAIL_OPEN),
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )
        outcome = await helper.handle_turn(
            turn=self.turn("turn-finalize-fail", "继续"),
            scope=self.scope,
            run_request=self.run_request("turn-finalize-fail", "继续"),
            recent_session=self.recent_session(),
        )

        retained = await helper.finalize_memory(
            outcome=outcome,
            scope=self.scope,
            user_turn_text="继续",
            agent_reply_text="这是一条律师助手回复。",
        )
        self.assertEqual(retained, 0)
        self.assertNotIn("agent_reply_text", outcome.evidence)
        self.assertNotIn("user_turn_text", outcome.evidence)

    async def test_finalize_memory_success_counts(self) -> None:
        runtime = RecordingRuntime()
        memory = RecordingMemory(retain_count=1)
        helper = QQBotSessionRuntime(
            runtime=runtime,
            memory=memory,
            memory_policy=QQBotMemoryIntegrationPolicy(
                retention_scope=QQBotMemoryRetentionScope.BOTH,
            ),
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )
        outcome = await helper.handle_turn(
            turn=self.turn("turn-finalize-ok", "Please summarize the contract points"),
            scope=self.scope,
            run_request=self.run_request("turn-finalize-ok", "Please summarize the contract points"),
            recent_session=self.recent_session(),
        )

        retained = await helper.finalize_memory(
            outcome=outcome,
            scope=self.scope,
            user_turn_text="Please summarize the contract points",
            agent_reply_text="The contract points include payment terms and breach liability.",
        )
        self.assertEqual(retained, 2)
        self.assertEqual(len(memory.aretain_calls), 2)
        self.assertNotIn("full_text", outcome.evidence)
        self.assertNotIn("agent_reply_text", outcome.evidence)

    async def test_created_metadata_has_no_forbidden_full_text_keys(self) -> None:
        runtime = RecordingRuntime()
        helper = QQBotSessionRuntime(
            runtime=runtime,
            memory_orchestrator=RecordingMemoryOrchestrator(status="degraded"),
            memory=FakeMemory(),
            clock=FakeRuntimeClock(start=FIXED_NOW),
            id_factory=FakeIdFactory(),
        )

        await helper.handle_turn(
            turn=self.turn("turn-safe-json", "继续"),
            scope=self.scope,
            run_request=self.run_request_with_metadata(
                "turn-safe-json",
                "继续",
                metadata={"artifact_refs": ("artifact://safe",), "output_policy_ref": "output-policy://safe"},
            ),
            recent_session=self.recent_session(),
        )

        metadata = runtime.created[0].metadata
        self.assertEqual(json.loads(json.dumps(metadata, ensure_ascii=False, sort_keys=True)), metadata)
        self.assertEqual(metadata["memory_use_evidence_status"], "degraded")
        self.assert_refs_only_metadata(metadata)

    @property
    def scope(self) -> SessionScope:
        return self.scope_for()

    def scope_for(self, *, user_id: str = OPENID) -> SessionScope:
        return SessionScope(
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            channel_id="qqbot",
            user_id=user_id,
            bot_instance_id="bot-001",
            conversation_id=f"qqbot:c2c:{user_id}:{user_id}",
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
            session_id="session-request-001",
            metadata={"request_ref": f"runtime://phase64/requests/{turn_id}"},
        )

    def run_request_with_metadata(
        self,
        turn_id: str,
        content: str,
        *,
        scope: SessionScope | None = None,
        metadata: dict[str, object] | None = None,
    ) -> RunRequest:
        base = self.run_request(turn_id, content, scope=scope)
        return RunRequest(
            turn=base.turn,
            solution=base.solution,
            tenant_id=base.tenant_id,
            workspace_id=base.workspace_id,
            bot_instance_id=base.bot_instance_id,
            session_id=base.session_id,
            metadata={**base.metadata, **dict(metadata or {})},
        )

    def recent_session(self) -> SessionSnapshot:
        return SessionSnapshot(
            scope=self.scope,
            session_id="session-recent-001",
            status="open",
            updated_at="2026-06-29T02:59:00Z",
            last_run_id="run-recent-001",
            last_run_status="running",
        )

    def assert_refs_only_metadata(self, metadata: dict[str, Any]) -> None:
        forbidden = {
            "raw_payload",
            "full_text",
            "document_text",
            "customer_document_text",
            "case_facts",
            "callback_body",
        }
        seen_keys = set(_walk_keys(metadata))
        self.assertTrue(forbidden.isdisjoint(seen_keys), seen_keys & forbidden)
        dumped = json.dumps(metadata, ensure_ascii=False)
        self.assertNotIn("synthetic answer body", dumped)
        self.assertNotIn("律师助手回复", dumped)


def _walk_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        keys: list[str] = []
        for key, nested in value.items():
            keys.append(str(key))
            keys.extend(_walk_keys(nested))
        return keys
    if isinstance(value, list):
        keys = []
        for item in value:
            keys.extend(_walk_keys(item))
        return keys
    return []


if __name__ == "__main__":
    unittest.main()
