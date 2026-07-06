"""Phase 49 integration tests: end-to-end session memory wiring."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from platform_contract.enums import (
    AgentResultStatus,
    AsyncTaskState,
    Channel,
    InterruptStatus,
    MessageType,
)
from platform_contract.events import AgentTurn, MemoryRecord, OutputConstraints

from platform_runtime import (
    DefaultRunRuntime,
    InMemoryInterruptStore,
    InMemoryMemoryStore,
    MemoryOrchestrator,
    MemoryOrchestratorPolicy,
    RunRequest,
    RuntimeFeatureFlags,
    SessionScope,
    SolutionBinding,
)
from platform_runtime.fakes import FakeBackendAdapter, FakeIdFactory, FakeRuntimeClock


FIXED_NOW = "2026-07-06T12:00:00Z"


def make_scope(
    *,
    tenant_id: str = "tenant-001",
    workspace_id: str = "workspace-001",
    user_id: str = "user-001",
) -> SessionScope:
    return SessionScope(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        channel_id="web",
        user_id=user_id,
        bot_instance_id="",
        conversation_id="conversation-001",
    )


def make_run_request(
    *,
    turn_id: str = "turn-001",
    content: str = "synthetic request for memory recall",
    metadata: dict[str, object] | None = None,
    tenant_id: str = "tenant-001",
    workspace_id: str = "workspace-001",
    user_id: str = "user-001",
    session_id: str = "session-001",
    output_constraints: OutputConstraints | None = None,
) -> RunRequest:
    return RunRequest(
        turn=AgentTurn(
            turn_id=turn_id,
            conversation_id="conversation-001",
            channel=Channel.WEB,
            user_id=user_id,
            message_type=MessageType.TEXT,
            received_at=FIXED_NOW,
            content=content,
            metadata={"raw_payload_ref": f"fixture://payloads/{turn_id}"},
        ),
        solution=SolutionBinding(solution_id="solution-001", version="1.0.0"),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        session_id=session_id,
        output_constraints=output_constraints,
        metadata=dict(metadata or {}),
    )


def make_memory(
    memory_id: str,
    *,
    tenant_id: str = "tenant-001",
    workspace_id: str = "workspace-001",
    user_id: str = "user-001",
    confidence: float = 0.8,
) -> MemoryRecord:
    return MemoryRecord(
        memory_id=memory_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        scope="session",
        status="active",
        sensitivity="internal",
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
        source_refs=[f"fixture://phase49/memory/{memory_id}"],
        summary=f"Synthetic summary for {memory_id}.",
        subject="citation",
        related_user_id=user_id,
        session_id="session-001",
        raw_payload_ref=f"fixture://phase49/memory/{memory_id}/raw",
        confidence=confidence,
    )


class SessionMemoryIntegrationTests(unittest.IsolatedAsyncioTestCase):
    """End-to-end integration tests for Phase 49 session memory wiring."""

    async def test_full_session_memory_flow_injects_memory_refs(self) -> None:
        """Full flow: runtime → MemoryOrchestrator → ContextBundle with memory_refs → backend."""
        store = InMemoryMemoryStore()
        store.upsert(make_memory("mem-int-001"))
        store.upsert(make_memory("mem-int-002"))

        orchestrator = MemoryOrchestrator(
            memory_store=store,
            policy=MemoryOrchestratorPolicy(max_memory_refs=8),
            clock=lambda: FIXED_NOW,
        )

        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                session_memory_enabled=True,
            ),
            memory_orchestrator=orchestrator,
        )

        await runtime.create_run(make_run_request())

        self.assertEqual(len(backend.submitted_requests), 1)
        submitted = backend.submitted_requests[0]

        # ContextBundle is present in metadata
        self.assertIn("context_bundle", submitted.metadata)
        context_bundle = submitted.metadata["context_bundle"]

        # Memory refs are injected
        self.assertIn("memory_refs", context_bundle)
        memory_refs = context_bundle["memory_refs"]
        self.assertGreater(len(memory_refs), 0)
        self.assertIn("mem-int-001", memory_refs)
        self.assertIn("mem-int-002", memory_refs)

        # Context bundle has correct tenant scope
        self.assertEqual(context_bundle["tenant_id"], "tenant-001")
        self.assertEqual(context_bundle["workspace_id"], "workspace-001")

        # Context bundle ID is present
        self.assertIn("context_bundle_id", submitted.metadata)
        self.assertEqual(submitted.metadata["context_bundle_id"], context_bundle["context_bundle_id"])

    async def test_session_memory_disabled_no_context_bundle_injected(self) -> None:
        """When session_memory_enabled=False, no context_bundle in submitted request (v1.6 behavior)."""
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(run_runtime_enabled=True),
        )

        await runtime.create_run(make_run_request())

        submitted = backend.submitted_requests[0]
        self.assertNotIn("context_bundle", submitted.metadata)
        self.assertNotIn("context_bundle_id", submitted.metadata)

    async def test_session_memory_resume_interrupt_injects_memory_refs(self) -> None:
        """resume_interrupt with session_memory_enabled=True also injects memory_refs."""
        clock = FakeRuntimeClock(start=FIXED_NOW)
        id_factory = FakeIdFactory()
        store = InMemoryMemoryStore()
        store.upsert(make_memory("mem-resume-001"))

        orchestrator = MemoryOrchestrator(
            memory_store=store,
            clock=lambda: FIXED_NOW,
        )

        backend = FakeBackendAdapter(
            clock=clock,
            id_factory=id_factory,
            clarification_result={
                "prompt_ref": "fixture://prompts/clarify-001",
                "resume_state_ref": "fixture://resume/run-paused-001",
            },
        )
        interrupt_store = InMemoryInterruptStore(clock=clock, id_factory=id_factory)

        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                session_memory_enabled=True,
            ),
            memory_orchestrator=orchestrator,
            interrupt_store=interrupt_store,
            clock=clock,
            id_factory=id_factory,
        )

        # Create a run that produces a clarification interrupt
        run = await runtime.create_run(make_run_request())
        self.assertEqual(run.status, AsyncTaskState.WAITING_FOR_USER)

        # Get the pending interrupt
        pending = interrupt_store.pending_for_scope(make_scope())
        self.assertIsNotNone(pending)

        # Resume the interrupt
        resumed = await runtime.resume_interrupt(
            interrupt_id=pending.event.interrupt_id,
            scope=make_scope(),
            req=make_run_request(turn_id="turn-answer-001", content="answer text"),
            idempotency_key="idem-001",
        )

        # The resumed request should have context_bundle with memory_refs
        submitted = backend.submitted_requests[-1]
        self.assertIn("context_bundle", submitted.metadata)
        context_bundle = submitted.metadata["context_bundle"]
        self.assertIn("memory_refs", context_bundle)
        self.assertIn("mem-resume-001", context_bundle["memory_refs"])

    async def test_session_memory_isolation_wrong_tenant_no_leak(self) -> None:
        """Memories from a different tenant are not recalled (isolation)."""
        store = InMemoryMemoryStore()
        store.upsert(make_memory("mem-tenant-001", tenant_id="tenant-001"))
        store.upsert(make_memory("mem-tenant-002", tenant_id="tenant-002"))

        orchestrator = MemoryOrchestrator(
            memory_store=store,
            clock=lambda: FIXED_NOW,
        )

        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                session_memory_enabled=True,
            ),
            memory_orchestrator=orchestrator,
        )

        await runtime.create_run(make_run_request(tenant_id="tenant-001"))

        submitted = backend.submitted_requests[0]
        memory_refs = submitted.metadata["context_bundle"]["memory_refs"]
        self.assertIn("mem-tenant-001", memory_refs)
        self.assertNotIn("mem-tenant-002", memory_refs)

    async def test_session_memory_empty_store_produces_empty_memory_refs(self) -> None:
        """When memory store has no matching memories, memory_refs is empty but context_bundle exists."""
        store = InMemoryMemoryStore()
        orchestrator = MemoryOrchestrator(
            memory_store=store,
            clock=lambda: FIXED_NOW,
        )

        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                session_memory_enabled=True,
            ),
            memory_orchestrator=orchestrator,
        )

        await runtime.create_run(make_run_request())

        submitted = backend.submitted_requests[0]
        self.assertIn("context_bundle", submitted.metadata)
        self.assertEqual(submitted.metadata["context_bundle"]["memory_refs"], [])


class NoAdapterImportsMemoryProviderTests(unittest.TestCase):
    """Verify no adapter source file imports HindsightMemory or hindsight_client."""

    def test_no_adapter_imports_memory_provider(self) -> None:
        """Grep all adapter source files for hindsight/HindsightMemory imports — must find none."""
        repo_root = Path(__file__).resolve().parents[3]
        adapter_dirs = [
            repo_root / "packages" / "backends" / "codex" / "src",
            repo_root / "packages" / "backends" / "provider_model" / "src",
            repo_root / "packages" / "backends" / "hermes" / "src",
        ]

        for adapter_dir in adapter_dirs:
            result = subprocess.run(
                ["grep", "-ri", "hindsight", str(adapter_dir)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                1,
                f"Found 'hindsight' import in {adapter_dir}:\n{result.stdout}",
            )

            result = subprocess.run(
                ["grep", "-ri", "HindsightMemory", str(adapter_dir)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                1,
                f"Found 'HindsightMemory' import in {adapter_dir}:\n{result.stdout}",
            )


if __name__ == "__main__":
    unittest.main()
