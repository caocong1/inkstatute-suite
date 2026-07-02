from __future__ import annotations

import json
import unittest
from dataclasses import dataclass, field
from typing import Any

from platform_contract.enums import AsyncTaskState, InterruptStatus
from platform_contract.events import ContextBundle
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
from platform_runtime.context_assembler import ContextAssemblyResult

from wecom_service import WeComRuntimeIngress
from wecom_service.session_runtime import WeComSessionRuntimeAction


FIXED_NOW = "2026-07-02T13:00:00Z"


@dataclass(slots=True)
class RecordingRuntime:
    created: list[RunRequest] = field(default_factory=list)
    resumed: list[tuple[str, SessionScope, RunRequest, str | None]] = field(default_factory=list)
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
            metadata={"interrupt_id": interrupt_id},
        )


@dataclass(slots=True)
class RecordingFeedbackCorrectionProvider:
    refs: tuple[str, ...] = ("feedback://ingress/correction-001",)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def list_feedback_correction_refs(self, **kwargs: Any) -> tuple[str, ...]:
        self.calls.append(dict(kwargs))
        return self.refs


@dataclass(slots=True)
class RecordingMemoryOrchestrator:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def recall_and_assemble(self, **kwargs: Any) -> ContextAssemblyResult:
        self.calls.append(dict(kwargs))
        return ContextAssemblyResult(
            bundle=ContextBundle(
                context_bundle_id="context-bundle-ingress-001",
                tenant_id=kwargs["scope"].tenant_id,
                workspace_id=kwargs["scope"].workspace_id,
                session_id=kwargs["session_id"],
                created_at=FIXED_NOW,
                budget_tokens=2048,
                run_id=kwargs.get("run_id"),
                turn_id=kwargs["turn_id"],
                recent_turn_refs=list(kwargs.get("recent_turn_refs", ())),
                summary_ref="summary://ingress/session/v1",
                active_task_refs=[],
                artifact_refs=list(kwargs.get("artifact_refs", ())),
                memory_refs=["memory://ingress/approved-001"],
                raw_payload_refs=[],
                industry_context={},
                metadata={
                    "feedback_correction_refs": list(kwargs.get("feedback_correction_refs", ())),
                    "output_policy_ref": kwargs.get("output_policy_ref"),
                },
            ),
            estimated_tokens=96,
            dropped_sections={"memory_refs": 0},
            protected_sections=("current_turn",),
            metadata={
                "memory_use_evidence_status": "recorded",
                "memory_use_evidence_recorded_count": 1,
                "memory_use_evidence_privacy": "refs_ids_counts_statuses_only",
            },
        )


class WeComIngressMemoryRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_constructor_passes_memory_dependencies_to_session_runtime(self) -> None:
        runtime = RecordingRuntime()
        orchestrator = RecordingMemoryOrchestrator()
        provider = RecordingFeedbackCorrectionProvider()

        ingress = self.ingress(
            runtime,
            memory_orchestrator=orchestrator,
            feedback_correction_ref_provider=provider,
        )

        self.assertIs(ingress.session_runtime.memory_orchestrator, orchestrator)
        self.assertIs(ingress.session_runtime.feedback_correction_ref_provider, provider)

    async def test_sanitized_callback_continue_merges_memory_context_metadata(self) -> None:
        runtime = RecordingRuntime()
        orchestrator = RecordingMemoryOrchestrator()
        provider = RecordingFeedbackCorrectionProvider()
        ingress = self.ingress(
            runtime,
            memory_orchestrator=orchestrator,
            feedback_correction_ref_provider=provider,
            base_metadata={"raw_payload_refs": ("fixture://tenant/bootstrap",)},
        )

        outcome = await ingress.handle_callback(
            self.callback("msg-memory-continue-001", "继续处理刚才的问题"),
            received_at=FIXED_NOW,
            recent_session=self.recent_session(),
            metadata={
                "recent_turn_refs": ("turn://ingress/recent-001",),
                "artifact_refs": ("artifact://ingress/prior-docx",),
                "output_policy_ref": "output-policy://lawyer-assistant",
            },
        )

        self.assertEqual(outcome.action, WeComSessionRuntimeAction.CONTINUE_SESSION)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(len(orchestrator.calls), 1)
        self.assertEqual(orchestrator.calls[0]["feedback_correction_refs"], provider.refs)
        self.assertEqual(len(runtime.created), 1)
        metadata = runtime.created[0].metadata
        self.assertEqual(metadata["context_bundle_id"], "context-bundle-ingress-001")
        self.assertEqual(metadata["memory_refs"], ["memory://ingress/approved-001"])
        self.assertEqual(metadata["summary_ref"], "summary://ingress/session/v1")
        self.assertEqual(metadata["feedback_correction_refs"], ["feedback://ingress/correction-001"])
        self.assertEqual(metadata["artifact_refs"], ["artifact://ingress/prior-docx"])
        self.assertEqual(metadata["output_policy_ref"], "output-policy://lawyer-assistant")
        self.assertTrue(metadata["request_ref"].startswith("wecom://turn/"))
        self.assertIn("fixture://tenant/bootstrap", metadata["raw_payload_refs"])
        self.assertIn("fixture://wecom/callback/msg-memory-continue-001", metadata["raw_payload_refs"])
        self.assertEqual(metadata["memory_use_evidence_status"], "recorded")
        self.assert_refs_only(metadata)
        self.assert_refs_only(outcome.as_event())

    async def test_pending_clarification_callback_resumes_interrupt_and_skips_memory_recall(self) -> None:
        interrupt_store = InMemoryInterruptStore(clock=FakeRuntimeClock(start=FIXED_NOW), id_factory=FakeIdFactory())
        pending = interrupt_store.create_clarification(
            scope=self.scope,
            run_id="run-waiting-001",
            session_id="session-waiting-001",
            prompt_ref="prompt://clarify",
            resume_state_ref="runtime://resume-state",
            reason="backend_needs_clarification",
        )
        runtime = RecordingRuntime(interrupt_store=interrupt_store)
        orchestrator = RecordingMemoryOrchestrator()
        provider = RecordingFeedbackCorrectionProvider()
        ingress = self.ingress(
            runtime,
            interrupt_store=interrupt_store,
            memory_orchestrator=orchestrator,
            feedback_correction_ref_provider=provider,
        )

        outcome = await ingress.handle_callback(
            self.callback("msg-clarify-answer-001", "选择第二个方案"),
            received_at=FIXED_NOW,
            recent_session=self.recent_session(session_id="session-waiting-001", last_run_id="run-waiting-001"),
        )

        self.assertEqual(outcome.action, WeComSessionRuntimeAction.RESUME_INTERRUPT)
        self.assertEqual(runtime.created, [])
        self.assertEqual(len(runtime.resumed), 1)
        self.assertEqual(runtime.resumed[0][0], pending.event.interrupt_id)
        self.assertEqual(interrupt_store.get(pending.event.interrupt_id).event.status, InterruptStatus.RESOLVED)
        self.assertEqual(orchestrator.calls, [])
        self.assertEqual(provider.calls, [])

    async def test_unsafe_ingress_metadata_rejected_before_context_metadata_is_attached(self) -> None:
        runtime = RecordingRuntime()
        orchestrator = RecordingMemoryOrchestrator()
        provider = RecordingFeedbackCorrectionProvider()
        ingress = self.ingress(
            runtime,
            memory_orchestrator=orchestrator,
            feedback_correction_ref_provider=provider,
        )

        with self.assertRaisesRegex(ValueError, "unsafe WeCom ingress metadata key"):
            await ingress.handle_callback(
                self.callback("msg-unsafe-001", "继续"),
                received_at=FIXED_NOW,
                recent_session=self.recent_session(),
                metadata={"full_text": "synthetic callback body that must not enter metadata"},
            )

        self.assertEqual(orchestrator.calls, [])
        self.assertEqual(provider.calls, [])
        self.assertEqual(runtime.created, [])

    def ingress(
        self,
        runtime: RecordingRuntime,
        *,
        interrupt_store: InMemoryInterruptStore | None = None,
        memory_orchestrator: RecordingMemoryOrchestrator | None = None,
        feedback_correction_ref_provider: RecordingFeedbackCorrectionProvider | None = None,
        base_metadata: dict[str, object] | None = None,
    ) -> WeComRuntimeIngress:
        return WeComRuntimeIngress(
            runtime=runtime,
            solution=SolutionBinding(solution_id="solution-lawyer-assistant-001", version="1.0.0"),
            tenant_id=self.scope.tenant_id,
            workspace_id=self.scope.workspace_id,
            bot_instance_id=self.scope.bot_instance_id,
            interrupt_store=interrupt_store,
            memory_orchestrator=memory_orchestrator,
            feedback_correction_ref_provider=feedback_correction_ref_provider,
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

    def assert_refs_only(self, event: dict[str, Any]) -> None:
        forbidden = {
            "raw_payload",
            "full_text",
            "document_text",
            "customer_document_text",
            "case_facts",
            "callback_body",
        }
        seen_keys = set(_walk_keys(event))
        self.assertTrue(forbidden.isdisjoint(seen_keys), seen_keys & forbidden)
        self.assertNotIn("synthetic callback body", json.dumps(event, ensure_ascii=False))


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
