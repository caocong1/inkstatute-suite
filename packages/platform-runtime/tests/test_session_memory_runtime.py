"""Tests for Phase 49: Session memory wiring in DefaultRunRuntime."""

from __future__ import annotations

import unittest

from platform_contract.enums import Channel, MessageType
from platform_contract.events import AgentTurn, MemoryRecord, OutputConstraints

from platform_runtime import (
    ContextAssembler,
    ContextAssemblyPolicy,
    DefaultRunRuntime,
    InMemoryMemoryStore,
    MemoryOrchestrator,
    MemoryOrchestratorPolicy,
    RunRequest,
    RunRuntimeStateError,
    RuntimeFeatureDisabledError,
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
        bot_instance_id="bot-001",
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


class SessionMemoryFeatureFlagTests(unittest.TestCase):
    def test_session_memory_disabled_by_default(self) -> None:
        flags = RuntimeFeatureFlags()
        self.assertFalse(flags.session_memory_enabled)

    def test_session_memory_can_be_enabled(self) -> None:
        flags = RuntimeFeatureFlags(session_memory_enabled=True)
        self.assertTrue(flags.session_memory_enabled)

    def test_session_memory_require_enabled_raises_when_false(self) -> None:
        flags = RuntimeFeatureFlags()
        with self.assertRaises(RuntimeFeatureDisabledError):
            flags.require_enabled("session_memory_enabled")


class SessionMemoryRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_session_memory_enabled_requires_memory_orchestrator(self) -> None:
        """When session_memory_enabled=True and no memory_orchestrator, create_run raises."""
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                session_memory_enabled=True,
            ),
        )

        with self.assertRaisesRegex(
            RunRuntimeStateError,
            "session_memory_enabled requires memory_orchestrator",
        ):
            await runtime.create_run(make_run_request())

        self.assertEqual(backend.submitted_requests, [])

    async def test_session_memory_enabled_injects_memory_refs_into_context_bundle(self) -> None:
        """With memory_orchestrator injected, create_run produces ContextBundle with memory_refs."""
        store = InMemoryMemoryStore()
        store.upsert(make_memory("mem-001"))
        store.upsert(make_memory("mem-002"))

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
        self.assertIn("context_bundle", submitted.metadata)
        context_bundle = submitted.metadata["context_bundle"]
        self.assertIn("memory_refs", context_bundle)
        memory_refs = context_bundle["memory_refs"]
        self.assertGreater(len(memory_refs), 0)
        self.assertIn("mem-001", memory_refs)
        self.assertIn("mem-002", memory_refs)

    async def test_session_memory_disabled_no_context_bundle(self) -> None:
        """When session_memory_enabled=False and context_assembly_enabled=False, no context_bundle."""
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(run_runtime_enabled=True),
        )

        await runtime.create_run(make_run_request())

        self.assertEqual(len(backend.submitted_requests), 1)
        submitted = backend.submitted_requests[0]
        self.assertNotIn("context_bundle", submitted.metadata)

    async def test_session_memory_recall_before_submit(self) -> None:
        """Memory recall happens before backend.submit_run — memory_refs in submitted request."""
        store = InMemoryMemoryStore()
        store.upsert(make_memory("mem-priority-001"))

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
        self.assertIn("mem-priority-001", submitted.metadata["context_bundle"]["memory_refs"])

    async def test_session_memory_does_not_break_context_assembly_path(self) -> None:
        """When session_memory_enabled=False and context_assembly_enabled=True, existing path works."""
        clock = FakeRuntimeClock(start=FIXED_NOW)
        id_factory = FakeIdFactory()
        backend = FakeBackendAdapter(clock=clock, id_factory=id_factory)

        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                context_assembly_enabled=True,
            ),
            context_assembler=ContextAssembler(
                policy=ContextAssemblyPolicy(budget_tokens=512),
                clock=clock,
                id_factory=id_factory,
            ),
            clock=clock,
            id_factory=id_factory,
        )

        await runtime.create_run(make_run_request())

        submitted = backend.submitted_requests[0]
        self.assertIn("context_bundle", submitted.metadata)
        # No memory_refs when using bare ContextAssembler (no memory store)
        self.assertEqual(submitted.metadata["context_bundle"]["memory_refs"], [])

    async def test_session_memory_isolation_wrong_tenant_no_leak(self) -> None:
        """Memories from a different tenant are not recalled."""
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

    async def test_session_memory_with_contract_log(self) -> None:
        """When contract_log_enabled and session_memory_enabled, context_bundle is logged."""
        from platform_runtime import InMemoryContractLogStore

        store = InMemoryMemoryStore()
        store.upsert(make_memory("mem-log-001"))

        orchestrator = MemoryOrchestrator(
            memory_store=store,
            clock=lambda: FIXED_NOW,
        )

        contract_log = InMemoryContractLogStore()
        backend = FakeBackendAdapter()
        runtime = DefaultRunRuntime(
            backend=backend,
            feature_flags=RuntimeFeatureFlags(
                run_runtime_enabled=True,
                session_memory_enabled=True,
                contract_log_enabled=True,
            ),
            memory_orchestrator=orchestrator,
            contract_log_store=contract_log,
        )

        await runtime.create_run(make_run_request())

        entries = contract_log.entries()
        context_bundle_entries = tuple(e for e in entries if e.event_key == "context_bundle")
        self.assertGreater(len(context_bundle_entries), 0)


if __name__ == "__main__":
    unittest.main()
