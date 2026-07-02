"""Tests for Phase 22: MemoryOrchestrator recall, isolation, and ContextBundle assembly."""

from __future__ import annotations

import inspect
import unittest

from platform_contract.events import MemoryRecord
from platform_runtime import (
    ContextAssembler,
    ContextAssemblyPolicy,
    DefaultRunRuntime,
    InMemoryMemoryStore,
    InMemoryRollingSummaryStore,
    MemoryOrchestrator,
    MemoryOrchestratorPolicy,
    MemoryQuery,
    MemoryStorePolicy,
    OrchestratorIsolationError,
    RollingSummaryProducer,
    SQLiteMemoryStore,
    SessionScope,
)


FIXED_NOW = "2026-07-02T12:00:00+00:00"

SCOPE = SessionScope(
    tenant_id="tenant-phase22",
    workspace_id="workspace-phase22",
    channel_id="channel-phase22",
    user_id="user-phase22",
    bot_instance_id="bot-phase22",
    conversation_id="conv-phase22",
)


def make_memory(memory_id: str, *, tenant_id: str = "tenant-phase22", confidence: float = 0.8) -> MemoryRecord:
    return MemoryRecord(
        memory_id=memory_id,
        tenant_id=tenant_id,
        workspace_id="workspace-phase22",
        scope="session",
        status="active",
        sensitivity="internal",
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
        source_refs=[f"fixture://phase22/memory/{memory_id}"],
        summary=f"Synthetic summary for {memory_id}.",
        subject="citation",
        related_user_id="user-phase22",
        session_id="session-phase22-001",
        raw_payload_ref=f"fixture://phase22/memory/{memory_id}/raw",
        confidence=confidence,
    )


def make_orchestrator(**kwargs: object) -> MemoryOrchestrator:
    store = InMemoryMemoryStore()
    return MemoryOrchestrator(memory_store=store, clock=lambda: FIXED_NOW, **kwargs)  # type: ignore[arg-type]


class MemoryOrchestratorRecallTests(unittest.TestCase):
    def test_recall_returns_context_bundle_with_memory_refs(self) -> None:
        """REC-01/02: recall_and_assemble returns a ContextBundle with memory refs."""
        store = InMemoryMemoryStore()
        store.upsert(make_memory("mem-001"))
        store.upsert(make_memory("mem-002"))

        orchestrator = MemoryOrchestrator(memory_store=store, clock=lambda: FIXED_NOW)
        result = orchestrator.recall_and_assemble(
            scope=SCOPE,
            session_id="session-phase22-001",
            turn_id="turn-phase22-001",
            current_turn_ref="turn://turn-phase22-001",
        )

        self.assertIsNotNone(result.bundle)
        self.assertGreater(len(result.bundle.memory_refs), 0)
        self.assertIn("mem-001", result.bundle.memory_refs)

    def test_recall_with_no_memories_returns_empty_memory_refs(self) -> None:
        """REC-01: when no memories match, bundle has empty memory_refs."""
        orchestrator = make_orchestrator()
        result = orchestrator.recall_and_assemble(
            scope=SCOPE,
            session_id="session-phase22-001",
            turn_id="turn-phase22-001",
            current_turn_ref="turn://turn-phase22-001",
        )

        self.assertEqual(result.bundle.memory_refs, [])

    def test_rolling_summary_ref_included_in_bundle_when_available(self) -> None:
        """REC-02: when summary_store has a summary, bundle.summary_ref is set."""
        store = InMemoryMemoryStore()
        summary_store = InMemoryRollingSummaryStore()
        producer = RollingSummaryProducer(clock=lambda: FIXED_NOW)
        summary = producer.produce(
            scope=SCOPE,
            session_id="session-phase22-001",
            summary_ref="summary://phase22/session-phase22-001/v1",
            source_refs=("turn://turn-phase22-001",),
        )
        summary_store.upsert(summary)

        orchestrator = MemoryOrchestrator(
            memory_store=store,
            summary_store=summary_store,
            clock=lambda: FIXED_NOW,
        )
        result = orchestrator.recall_and_assemble(
            scope=SCOPE,
            session_id="session-phase22-001",
            turn_id="turn-phase22-001",
            current_turn_ref="turn://turn-phase22-001",
        )

        self.assertEqual(result.bundle.summary_ref, "summary://phase22/session-phase22-001/v1")

    def test_no_summary_store_produces_bundle_without_summary_ref(self) -> None:
        """REC-02: when no summary_store is injected, bundle.summary_ref is None."""
        orchestrator = make_orchestrator()
        result = orchestrator.recall_and_assemble(
            scope=SCOPE,
            session_id="session-phase22-001",
            turn_id="turn-phase22-001",
            current_turn_ref="turn://turn-phase22-001",
        )

        self.assertIsNone(result.bundle.summary_ref)

    def test_policy_max_memory_refs_limits_recalled_refs(self) -> None:
        """REC-01: policy.max_memory_refs limits how many memory refs are injected."""
        store = InMemoryMemoryStore()
        for i in range(10):
            store.upsert(make_memory(f"mem-{i:03d}", confidence=0.9 - i * 0.05))

        orchestrator = MemoryOrchestrator(
            memory_store=store,
            policy=MemoryOrchestratorPolicy(max_memory_refs=3),
            clock=lambda: FIXED_NOW,
        )
        result = orchestrator.recall_and_assemble(
            scope=SCOPE,
            session_id="session-phase22-001",
            turn_id="turn-phase22-001",
            current_turn_ref="turn://turn-phase22-001",
        )

        self.assertLessEqual(len(result.bundle.memory_refs), 3)


class MemoryOrchestratorIsolationTests(unittest.TestCase):
    def test_isolation_error_on_mismatched_tenant(self) -> None:
        """REC-03: OrchestratorIsolationError raised when scope tenant_id mismatches."""
        store = InMemoryMemoryStore()
        orchestrator = MemoryOrchestrator(memory_store=store, clock=lambda: FIXED_NOW)

        wrong_scope = SessionScope(
            tenant_id="DIFFERENT-TENANT",
            workspace_id="workspace-phase22",
            channel_id="channel-phase22",
            user_id="user-phase22",
            bot_instance_id="bot-phase22",
            conversation_id="conv-phase22",
        )

        # The query is built from scope fields, so passing the wrong scope should
        # be caught. We monkey-patch the query construction indirectly by using
        # the private helper directly for clarity.
        from platform_runtime.memory_orchestrator import _check_isolation
        from platform_runtime import MemoryQuery

        mismatched_query = MemoryQuery(
            tenant_id="DIFFERENT-TENANT",
            workspace_id="WRONG-WORKSPACE",
            now=FIXED_NOW,
        )
        with self.assertRaises(OrchestratorIsolationError):
            _check_isolation(mismatched_query, SCOPE)

    def test_isolation_passes_for_matching_scope(self) -> None:
        """REC-03: no error when query scope matches session scope."""
        from platform_runtime.memory_orchestrator import _check_isolation
        from platform_runtime import MemoryQuery

        query = MemoryQuery(
            tenant_id=SCOPE.tenant_id,
            workspace_id=SCOPE.workspace_id,
            now=FIXED_NOW,
        )
        # Should not raise
        _check_isolation(query, SCOPE)


class MemoryOrchestratorMemoryUseTests(unittest.TestCase):
    def test_memory_use_recorded_in_sqlite_store(self) -> None:
        """REC-04: MemoryUse evidence is recorded for each selected memory."""
        store = SQLiteMemoryStore()
        store.upsert(make_memory("mem-rec-001"))

        orchestrator = MemoryOrchestrator(
            memory_store=store,
            policy=MemoryOrchestratorPolicy(record_memory_use=True),
            clock=lambda: FIXED_NOW,
        )
        result = orchestrator.recall_and_assemble(
            scope=SCOPE,
            session_id="session-phase22-001",
            turn_id="turn-phase22-001",
            current_turn_ref="turn://turn-phase22-001",
            run_id="run-phase22-001",
        )

        uses = store.list_memory_uses(MemoryQuery(
            tenant_id="tenant-phase22",
            workspace_id="workspace-phase22",
            now=FIXED_NOW,
        ))
        self.assertGreater(len(uses), 0)
        use = uses[0]
        self.assertEqual(use.memory_id, "mem-rec-001")
        self.assertEqual(use.purpose, "context_assembly")
        store.close()

    def test_memory_use_has_no_raw_text_fields(self) -> None:
        """REC-04: MemoryUse records contain no raw text — only refs, IDs, scores."""
        store = SQLiteMemoryStore()
        store.upsert(make_memory("mem-rec-002"))

        orchestrator = MemoryOrchestrator(
            memory_store=store,
            policy=MemoryOrchestratorPolicy(record_memory_use=True),
            clock=lambda: FIXED_NOW,
        )
        orchestrator.recall_and_assemble(
            scope=SCOPE,
            session_id="session-phase22-001",
            turn_id="turn-phase22-001",
            current_turn_ref="turn://turn-phase22-001",
        )

        uses = store.list_memory_uses(MemoryQuery(
            tenant_id="tenant-phase22",
            workspace_id="workspace-phase22",
            now=FIXED_NOW,
        ))
        self.assertGreater(len(uses), 0)
        for use in uses:
            # source_refs must be refs, not raw text
            for ref in use.source_refs:
                self.assertIn("://", ref, f"source_ref must be a URI, got {ref!r}")
            # No raw text fields expected
            self.assertIsNone(getattr(use, "raw_text", None))
            self.assertIsNone(getattr(use, "full_text", None))
        store.close()

    def test_memory_use_recording_skipped_for_in_memory_store(self) -> None:
        """REC-04: InMemoryMemoryStore has no record_memory_use; orchestrator continues silently."""
        store = InMemoryMemoryStore()
        store.upsert(make_memory("mem-in-memory-001"))

        orchestrator = MemoryOrchestrator(
            memory_store=store,
            policy=MemoryOrchestratorPolicy(record_memory_use=True),
            clock=lambda: FIXED_NOW,
        )
        # Must not raise even though InMemoryMemoryStore lacks record_memory_use
        result = orchestrator.recall_and_assemble(
            scope=SCOPE,
            session_id="session-phase22-001",
            turn_id="turn-phase22-001",
            current_turn_ref="turn://turn-phase22-001",
        )
        self.assertIsNotNone(result.bundle)


class MemoryOrchestratorContractTests(unittest.TestCase):
    def test_run_runtime_constructor_has_no_memory_orchestrator_parameter(self) -> None:
        """REC-05: DefaultRunRuntime.__init__ must not gain a memory_orchestrator parameter."""
        signature = inspect.signature(DefaultRunRuntime.__init__)

        self.assertNotIn("memory_orchestrator", signature.parameters)
        self.assertNotIn("memory_store", signature.parameters)
        self.assertNotIn("recall_orchestrator", signature.parameters)

    def test_orchestrator_is_standalone_and_does_not_require_run_runtime(self) -> None:
        """REC-05: MemoryOrchestrator can be constructed without any RunRuntime."""
        store = InMemoryMemoryStore()
        orchestrator = MemoryOrchestrator(memory_store=store)
        self.assertIsNotNone(orchestrator)

    def test_budget_pressure_trim_occurs_within_assembler(self) -> None:
        """ContextAssembler trims when bundle exceeds budget — orchestrator does not bypass this."""
        store = InMemoryMemoryStore()
        for i in range(10):
            store.upsert(make_memory(f"mem-budget-{i:02d}"))

        # Budget tight enough to force trimming of memory refs (protected context ~65 tokens).
        tiny_assembler = ContextAssembler(policy=ContextAssemblyPolicy(budget_tokens=128))
        orchestrator = MemoryOrchestrator(
            memory_store=store,
            context_assembler=tiny_assembler,
            policy=MemoryOrchestratorPolicy(max_memory_refs=10),
            clock=lambda: FIXED_NOW,
        )
        result = orchestrator.recall_and_assemble(
            scope=SCOPE,
            session_id="session-phase22-001",
            turn_id="turn-phase22-001",
            current_turn_ref="turn://turn-phase22-001",
        )

        # Budget trim may have reduced memory_refs below the 10 requested
        self.assertIsNotNone(result.bundle)
        self.assertLessEqual(result.estimated_tokens, 128)


if __name__ == "__main__":
    unittest.main()
