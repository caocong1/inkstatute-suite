"""Tests for MultiAgentRuntimeAdapter basic BackendAdapter Protocol compliance."""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import replace

from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_contract.enums import AsyncTaskState
from platform_contract.events import (
    AgentResult,
    AgentResultStatus,
    AgentTurn,
    Channel,
    MessageType,
    ReplyType,
    SolutionBinding,
)
from platform_runtime import (
    Approval,
    ArtifactRecord,
    BootstrapStatus,
    Run,
    RunEvent,
    RunHandle,
    RunRequest,
)
from platform_runtime.fakes import FakeBackendAdapter, FakeIdFactory, FakeRuntimeClock

from inkstatute_multi_agent_adapter import (
    MultiAgentOrchestrationConfig,
    MultiAgentOrchestrationMode,
    MultiAgentRuntimeAdapter,
    MultiAgentRuntimeAdapterConfig,
)


def _make_turn(turn_id: str = "turn-001") -> AgentTurn:
    return AgentTurn(
        turn_id=turn_id,
        conversation_id="conv-001",
        channel=Channel.WEB,
        user_id="user-001",
        message_type=MessageType.TEXT,
        received_at="2026-07-06T00:00:00Z",
        content="Hello",
    )


def _make_request(
    backend_id: str = "agent-a",
    turn_id: str = "turn-001",
    tenant_id: str | None = "tenant-001",
    metadata: dict | None = None,
) -> RunRequest:
    return RunRequest(
        turn=_make_turn(turn_id),
        solution=SolutionBinding(
            solution_id="sol-001",
            backend_id=backend_id,
        ),
        tenant_id=tenant_id,
        metadata=metadata or {},
    )


class _ScriptedAdapter:
    """In-memory adapter with scripted handoff/delegate behavior for tests."""

    def __init__(
        self,
        *,
        backend_id: str,
        handoff_to: str | None = None,
        delegate_to: str | list[str] | None = None,
        shared_state_update: dict | None = None,
        clock: FakeRuntimeClock | None = None,
        id_factory: FakeIdFactory | None = None,
    ) -> None:
        self._backend_id = backend_id
        self._handoff_to = handoff_to
        self._delegate_to = delegate_to
        self._shared_state_update = shared_state_update or {}
        self._clock = clock or FakeRuntimeClock()
        self._id_factory = id_factory or FakeIdFactory()
        self.runs: dict[str, Run] = {}
        self.events: dict[str, list[RunEvent]] = {}
        self.artifacts: dict[str, list[ArtifactRecord]] = {}
        self.cancelled: list[str] = []
        self.approvals: list[tuple[str, Approval]] = []

    def backend_id(self) -> str:
        return self._backend_id

    def capabilities(self) -> AdapterCapabilitySet:
        return AdapterCapabilitySet(
            invocation_mode="run",
            artifact_return_support=True,
            no_channel_io=True,
            run_invocation_modes=["run"],
            stream_event_support=True,
            cancel_support=True,
            approval_support=True,
            parallel_task_support=True,
        )

    async def bootstrap_check(self) -> BootstrapStatus:
        return BootstrapStatus(
            ok=True,
            backend_id=self._backend_id,
            checked_at=self._clock.now(),
            metadata={"in_memory": True},
        )

    async def submit_run(self, req: RunRequest) -> RunHandle:
        run_id = f"{self._backend_id}-run-{self._id_factory.new_id('sub'):>05s}"
        backend_run_id = f"{self._backend_id}-backend-{run_id}"
        metadata = {
            "backend_run_id": backend_run_id,
            "backend_id": self._backend_id,
            "agent_id": req.metadata.get("agent_id") if req.metadata else None,
            "parent_run_id": req.metadata.get("parent_run_id") if req.metadata else None,
            "shared_state_received": dict(req.metadata.get("shared_state", {})) if req.metadata else {},
        }
        if self._handoff_to:
            metadata["handoff_to"] = self._handoff_to
        if self._delegate_to:
            metadata["delegate_to"] = self._delegate_to
        if self._shared_state_update:
            metadata["shared_state_update"] = dict(self._shared_state_update)
        run = Run(
            run_id=run_id,
            status=AsyncTaskState.SUCCEEDED,
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            result=AgentResult(
                result_id=f"result-{run_id}",
                turn_id=req.turn.turn_id,
                status=AgentResultStatus.SUCCESS,
                reply_type=ReplyType.TEXT,
                content=f"output from {self._backend_id}",
            ),
            metadata=metadata,
        )
        self.runs[run_id] = run
        self.events[run_id] = []
        self.artifacts[run_id] = [
            ArtifactRecord(
                artifact_id=f"art-{run_id}",
                kind="text",
                uri_ref=f"fixture://artifacts/{run_id}",
                name=f"{run_id}.txt",
            )
        ]
        return RunHandle(
            run_id=run_id,
            backend_run_id=backend_run_id,
            status=AsyncTaskState.SUCCEEDED,
            metadata={"event_count": 0},
        )

    async def get_run(self, run_id: str) -> Run:
        return self.runs[run_id]

    async def stream_events(self, run_id: str):
        for event in tuple(self.events.get(run_id, [])):
            yield event

    async def cancel_run(self, run_id: str) -> Run:
        self.cancelled.append(run_id)
        run = self.runs[run_id]
        updated = replace(run, status=AsyncTaskState.CANCELLED)
        self.runs[run_id] = updated
        return updated

    async def submit_approval(self, run_id: str, approval: Approval) -> Run:
        self.approvals.append((run_id, approval))
        return self.runs[run_id]

    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        return list(self.artifacts.get(run_id, []))


class TestMultiAgentAdapterBasics(unittest.TestCase):
    """Basic adapter identity and capability tests."""

    def test_backend_id_returns_adapter_id(self) -> None:
        adapter = MultiAgentRuntimeAdapter(sub_adapters={})
        self.assertEqual(adapter.backend_id(), "multi-agent-runtime")

    def test_backend_id_custom_adapter_id(self) -> None:
        cfg = MultiAgentRuntimeAdapterConfig(adapter_id="custom-ma")
        adapter = MultiAgentRuntimeAdapter(sub_adapters={}, config=cfg)
        self.assertEqual(adapter.backend_id(), "custom-ma")

    def test_capabilities_merges_sub_adapters(self) -> None:
        a = FakeBackendAdapter(backend_id="agent-a")
        b = FakeBackendAdapter(backend_id="agent-b")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a, "agent-b": b},
        )
        caps = adapter.capabilities()
        self.assertTrue(caps.artifact_return_support)
        self.assertTrue(caps.stream_event_support)

    def test_bootstrap_check_aggregates(self) -> None:
        a = FakeBackendAdapter(backend_id="agent-a")
        adapter = MultiAgentRuntimeAdapter(sub_adapters={"agent-a": a})
        status = asyncio.run(adapter.bootstrap_check())
        self.assertTrue(status.ok)
        self.assertEqual(status.backend_id, "multi-agent-runtime")
        self.assertEqual(status.metadata["sub_adapter_count"], 1)

    def test_bootstrap_check_no_sub_adapters(self) -> None:
        adapter = MultiAgentRuntimeAdapter(sub_adapters={})
        status = asyncio.run(adapter.bootstrap_check())
        self.assertFalse(status.ok)
        self.assertIn("no_sub_adapters_configured", status.issues)


class TestPassThroughMode(unittest.TestCase):
    """When enabled=False (default), adapter is transparent pass-through."""

    def test_passthrough_delegates_to_matching_sub_adapter(self) -> None:
        a = FakeBackendAdapter(backend_id="agent-a")
        b = FakeBackendAdapter(backend_id="agent-b")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a, "agent-b": b},
        )
        req = _make_request(backend_id="agent-a")
        handle = asyncio.run(adapter.submit_run(req))
        self.assertEqual(len(a.submitted_requests), 1)
        self.assertEqual(len(b.submitted_requests), 0)
        # get_run delegates to sub-adapter.
        run = asyncio.run(adapter.get_run(handle.run_id))
        self.assertEqual(run.run_id, handle.run_id)

    def test_passthrough_none_backend_id_raises(self) -> None:
        a = FakeBackendAdapter(backend_id="agent-a")
        adapter = MultiAgentRuntimeAdapter(sub_adapters={"agent-a": a})
        req = _make_request(backend_id="agent-a")
        req = replace(req, solution=replace(req.solution, backend_id=None))
        with self.assertRaises(KeyError):
            asyncio.run(adapter.submit_run(req))

    def test_passthrough_unknown_backend_id_raises(self) -> None:
        a = FakeBackendAdapter(backend_id="agent-a")
        adapter = MultiAgentRuntimeAdapter(sub_adapters={"agent-a": a})
        req = _make_request(backend_id="unknown")
        with self.assertRaises(KeyError):
            asyncio.run(adapter.submit_run(req))

    def test_passthrough_stream_events_delegates(self) -> None:
        a = FakeBackendAdapter(backend_id="agent-a")
        adapter = MultiAgentRuntimeAdapter(sub_adapters={"agent-a": a})
        req = _make_request(backend_id="agent-a")
        handle = asyncio.run(adapter.submit_run(req))

        async def _collect():
            return [e async for e in adapter.stream_events(handle.run_id)]

        events = asyncio.run(_collect())
        self.assertTrue(len(events) > 0)

    def test_passthrough_cancel_delegates(self) -> None:
        a = FakeBackendAdapter(backend_id="agent-a")
        adapter = MultiAgentRuntimeAdapter(sub_adapters={"agent-a": a})
        req = _make_request(backend_id="agent-a")
        handle = asyncio.run(adapter.submit_run(req))
        run = asyncio.run(adapter.cancel_run(handle.run_id))
        self.assertEqual(run.status, AsyncTaskState.CANCELLED)
        self.assertIn(handle.run_id, a.cancelled_run_ids)

    def test_passthrough_submit_approval_delegates(self) -> None:
        a = FakeBackendAdapter(backend_id="agent-a")
        adapter = MultiAgentRuntimeAdapter(sub_adapters={"agent-a": a})
        req = _make_request(backend_id="agent-a")
        handle = asyncio.run(adapter.submit_run(req))
        approval = Approval(approval_id="ap-001", decision="approved")
        asyncio.run(adapter.submit_approval(handle.run_id, approval))
        self.assertEqual(len(a.submitted_approvals), 1)

    def test_passthrough_collect_artifacts_delegates(self) -> None:
        a = FakeBackendAdapter(backend_id="agent-a")
        adapter = MultiAgentRuntimeAdapter(sub_adapters={"agent-a": a})
        req = _make_request(backend_id="agent-a")
        handle = asyncio.run(adapter.submit_run(req))
        arts = asyncio.run(adapter.collect_artifacts(handle.run_id))
        self.assertTrue(len(arts) > 0)

    def test_passthrough_unknown_run_raises(self) -> None:
        a = FakeBackendAdapter(backend_id="agent-a")
        adapter = MultiAgentRuntimeAdapter(sub_adapters={"agent-a": a})
        with self.assertRaises(KeyError):
            asyncio.run(adapter.get_run("unknown-run"))


class TestEnabledModeRouting(unittest.TestCase):
    """When enabled=True, parent run routing works."""

    def test_enabled_submit_returns_parent_run_id(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a")
        cfg = MultiAgentRuntimeAdapterConfig(
            enabled=True,
            orchestration=MultiAgentOrchestrationConfig(
                mode=MultiAgentOrchestrationMode.SEQUENTIAL,
                entry_agent_id="agent-a",
            ),
        )
        adapter = MultiAgentRuntimeAdapter(sub_adapters={"agent-a": a}, config=cfg)
        req = _make_request(backend_id="agent-a")
        handle = asyncio.run(adapter.submit_run(req))
        self.assertTrue(handle.run_id.startswith("ma-"))
        self.assertTrue(handle.metadata["multi_agent_enabled"])

    def test_enabled_get_run_returns_parent_run(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a")
        cfg = MultiAgentRuntimeAdapterConfig(
            enabled=True,
            orchestration=MultiAgentOrchestrationConfig(
                mode=MultiAgentOrchestrationMode.SEQUENTIAL,
                entry_agent_id="agent-a",
            ),
        )
        adapter = MultiAgentRuntimeAdapter(sub_adapters={"agent-a": a}, config=cfg)
        req = _make_request(backend_id="agent-a")
        handle = asyncio.run(adapter.submit_run(req))
        run = asyncio.run(adapter.get_run(handle.run_id))
        self.assertEqual(run.run_id, handle.run_id)
        self.assertTrue(run.metadata["multi_agent"])

    def test_enabled_stream_events_yields_parent_events(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a")
        cfg = MultiAgentRuntimeAdapterConfig(
            enabled=True,
            orchestration=MultiAgentOrchestrationConfig(
                mode=MultiAgentOrchestrationMode.SEQUENTIAL,
                entry_agent_id="agent-a",
            ),
        )
        adapter = MultiAgentRuntimeAdapter(sub_adapters={"agent-a": a}, config=cfg)
        req = _make_request(backend_id="agent-a")
        handle = asyncio.run(adapter.submit_run(req))

        async def _collect():
            return [e async for e in adapter.stream_events(handle.run_id)]

        events = asyncio.run(_collect())
        self.assertTrue(len(events) > 0)
        self.assertTrue(all(e.run_id == handle.run_id for e in events))

    def test_enabled_collect_artifacts_aggregates(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a")
        cfg = MultiAgentRuntimeAdapterConfig(
            enabled=True,
            orchestration=MultiAgentOrchestrationConfig(
                mode=MultiAgentOrchestrationMode.SEQUENTIAL,
                entry_agent_id="agent-a",
            ),
        )
        adapter = MultiAgentRuntimeAdapter(sub_adapters={"agent-a": a}, config=cfg)
        req = _make_request(backend_id="agent-a")
        handle = asyncio.run(adapter.submit_run(req))
        arts = asyncio.run(adapter.collect_artifacts(handle.run_id))
        self.assertTrue(len(arts) >= 1)

    def test_enabled_cancel_cancels_sub_runs(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a")
        cfg = MultiAgentRuntimeAdapterConfig(
            enabled=True,
            orchestration=MultiAgentOrchestrationConfig(
                mode=MultiAgentOrchestrationMode.SEQUENTIAL,
                entry_agent_id="agent-a",
            ),
        )
        adapter = MultiAgentRuntimeAdapter(sub_adapters={"agent-a": a}, config=cfg)
        req = _make_request(backend_id="agent-a")
        handle = asyncio.run(adapter.submit_run(req))
        run = asyncio.run(adapter.cancel_run(handle.run_id))
        self.assertEqual(run.status, AsyncTaskState.CANCELLED)
        self.assertTrue(len(a.cancelled) > 0)


if __name__ == "__main__":
    unittest.main()
