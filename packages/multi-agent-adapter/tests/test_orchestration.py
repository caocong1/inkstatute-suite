"""Tests for multi-agent orchestration: sequential, parallel, supervisor, cycle detection, max_handoffs, COW state."""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import replace

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
from platform_runtime import Run, RunHandle, RunRequest

from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_contract.events import AgentResult, AgentResultStatus, ReplyType
from platform_runtime import BootstrapStatus, RunEvent
from platform_runtime.fakes import FakeIdFactory, FakeRuntimeClock

from inkstatute_multi_agent_adapter import (
    MultiAgentCycleError,
    MultiAgentHandoffLimitError,
    MultiAgentOrchestrationConfig,
    MultiAgentOrchestrationMode,
    MultiAgentRoutingError,
    MultiAgentRuntimeAdapter,
    MultiAgentRuntimeAdapterConfig,
    SharedStateStore,
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
        metadata: dict = {
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
        run = self.runs[run_id]
        return replace(run, status=AsyncTaskState.CANCELLED)

    async def submit_approval(self, run_id: str, approval):
        return self.runs[run_id]

    async def collect_artifacts(self, run_id: str) -> list:
        return []


def _enabled_config(
    mode: MultiAgentOrchestrationMode = MultiAgentOrchestrationMode.SEQUENTIAL,
    **kwargs,
) -> MultiAgentRuntimeAdapterConfig:
    orch = MultiAgentOrchestrationConfig(mode=mode, **kwargs)
    return MultiAgentRuntimeAdapterConfig(enabled=True, orchestration=orch)


class TestSequentialOrchestration(unittest.TestCase):
    def test_single_agent_no_handoff(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a},
            config=_enabled_config(entry_agent_id="agent-a"),
        )
        handle = asyncio.run(adapter.submit_run(_make_request()))
        run = asyncio.run(adapter.get_run(handle.run_id))
        self.assertEqual(run.status, AsyncTaskState.SUCCEEDED)
        self.assertEqual(handle.metadata["handoff_chain"], ["agent-a"])
        self.assertEqual(len(handle.metadata["sub_run_ids"]), 1)

    def test_sequential_handoff_chain(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a", handoff_to="agent-b")
        b = _ScriptedAdapter(backend_id="agent-b", handoff_to="agent-c")
        c = _ScriptedAdapter(backend_id="agent-c")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a, "agent-b": b, "agent-c": c},
            config=_enabled_config(entry_agent_id="agent-a"),
        )
        handle = asyncio.run(adapter.submit_run(_make_request()))
        self.assertEqual(handle.metadata["handoff_chain"], ["agent-a", "agent-b", "agent-c"])
        self.assertEqual(len(handle.metadata["sub_run_ids"]), 3)
        run = asyncio.run(adapter.get_run(handle.run_id))
        self.assertEqual(run.status, AsyncTaskState.SUCCEEDED)

    def test_sequential_shared_state_propagation(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a", handoff_to="agent-b", shared_state_update={"step": 1})
        b = _ScriptedAdapter(backend_id="agent-b")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a, "agent-b": b},
            config=_enabled_config(entry_agent_id="agent-a"),
        )
        handle = asyncio.run(adapter.submit_run(_make_request()))
        run = asyncio.run(adapter.get_run(handle.run_id))
        # Agent B should have received the shared state committed by Agent A.
        self.assertEqual(run.metadata["shared_state"]["step"], 1)
        # Verify agent B actually received it in its request.
        b_run = b.runs[list(b.runs.keys())[0]]
        self.assertEqual(b_run.metadata["shared_state_received"]["step"], 1)

    def test_sequential_uses_solution_backend_id_when_no_entry(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a},
            config=_enabled_config(),
        )
        req = _make_request(backend_id="agent-a")
        handle = asyncio.run(adapter.submit_run(req))
        self.assertEqual(handle.metadata["handoff_chain"], ["agent-a"])


class TestMaxHandoffs(unittest.TestCase):
    def test_max_handoffs_exceeded_raises(self) -> None:
        # Create a cycle of 6 agents that would exceed max_handoffs=5.
        # agent-a -> agent-b -> ... -> agent-f -> agent-a (but cycle check catches first)
        # Instead, create a long chain that exceeds max_handoffs.
        adapters = {}
        ids = [f"agent-{c}" for c in "abcdefg"]
        for i, aid in enumerate(ids):
            next_id = ids[i + 1] if i + 1 < len(ids) else None
            adapters[aid] = _ScriptedAdapter(backend_id=aid, handoff_to=next_id)

        cfg = _enabled_config(entry_agent_id="agent-a", max_handoffs=5)
        adapter = MultiAgentRuntimeAdapter(sub_adapters=adapters, config=cfg)
        with self.assertRaises(MultiAgentHandoffLimitError) as ctx:
            asyncio.run(adapter.submit_run(_make_request()))
        self.assertIn("handoff limit", str(ctx.exception).lower())

    def test_max_handoffs_allows_exactly_limit(self) -> None:
        # 5 handoffs = 6 agents total (entry + 5 handoffs).
        ids = [f"agent-{c}" for c in "abcdef"]
        adapters = {}
        for i, aid in enumerate(ids):
            next_id = ids[i + 1] if i + 1 < len(ids) else None
            adapters[aid] = _ScriptedAdapter(backend_id=aid, handoff_to=next_id)

        cfg = _enabled_config(entry_agent_id="agent-a", max_handoffs=5)
        adapter = MultiAgentRuntimeAdapter(sub_adapters=adapters, config=cfg)
        handle = asyncio.run(adapter.submit_run(_make_request()))
        self.assertEqual(len(handle.metadata["handoff_chain"]), 6)


class TestCycleDetection(unittest.TestCase):
    def test_cycle_detected_raises(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a", handoff_to="agent-b")
        b = _ScriptedAdapter(backend_id="agent-b", handoff_to="agent-a")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a, "agent-b": b},
            config=_enabled_config(entry_agent_id="agent-a"),
        )
        with self.assertRaises(MultiAgentCycleError) as ctx:
            asyncio.run(adapter.submit_run(_make_request()))
        self.assertIn("cycle", str(ctx.exception).lower())
        self.assertIn("agent-a", str(ctx.exception))

    def test_three_agent_cycle_detected(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a", handoff_to="agent-b")
        b = _ScriptedAdapter(backend_id="agent-b", handoff_to="agent-c")
        c = _ScriptedAdapter(backend_id="agent-c", handoff_to="agent-a")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a, "agent-b": b, "agent-c": c},
            config=_enabled_config(entry_agent_id="agent-a"),
        )
        with self.assertRaises(MultiAgentCycleError) as ctx:
            asyncio.run(adapter.submit_run(_make_request()))
        self.assertIn("agent-a", str(ctx.exception))


class TestParallelOrchestration(unittest.TestCase):
    def test_parallel_fan_out_fan_in(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a")
        b = _ScriptedAdapter(backend_id="agent-b")
        c = _ScriptedAdapter(backend_id="agent-c")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a, "agent-b": b, "agent-c": c},
            config=_enabled_config(MultiAgentOrchestrationMode.PARALLEL),
        )
        handle = asyncio.run(adapter.submit_run(_make_request()))
        self.assertEqual(len(handle.metadata["sub_run_ids"]), 3)
        run = asyncio.run(adapter.get_run(handle.run_id))
        self.assertEqual(run.status, AsyncTaskState.SUCCEEDED)

    def test_parallel_agent_set_restriction(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a")
        b = _ScriptedAdapter(backend_id="agent-b")
        c = _ScriptedAdapter(backend_id="agent-c")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a, "agent-b": b, "agent-c": c},
            config=_enabled_config(
                MultiAgentOrchestrationMode.PARALLEL,
                agent_set=["agent-a", "agent-b"],
            ),
        )
        handle = asyncio.run(adapter.submit_run(_make_request()))
        self.assertEqual(len(handle.metadata["sub_run_ids"]), 2)

    def test_parallel_cow_isolation(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a", shared_state_update={"a_key": "a_val"})
        b = _ScriptedAdapter(backend_id="agent-b", shared_state_update={"b_key": "b_val"})
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a, "agent-b": b},
            config=_enabled_config(MultiAgentOrchestrationMode.PARALLEL),
        )
        handle = asyncio.run(adapter.submit_run(_make_request()))
        run = asyncio.run(adapter.get_run(handle.run_id))
        # Shared state should NOT contain either agent's update (COW, no commit in parallel).
        shared = run.metadata["shared_state"]
        self.assertNotIn("a_key", shared)
        self.assertNotIn("b_key", shared)

    def test_parallel_concurrency_semaphore(self) -> None:
        # With concurrency=1, agents run sequentially.
        a = _ScriptedAdapter(backend_id="agent-a")
        b = _ScriptedAdapter(backend_id="agent-b")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a, "agent-b": b},
            config=_enabled_config(
                MultiAgentOrchestrationMode.PARALLEL,
                parallel_concurrency=1,
            ),
        )
        handle = asyncio.run(adapter.submit_run(_make_request()))
        self.assertEqual(len(handle.metadata["sub_run_ids"]), 2)


class TestSupervisorOrchestration(unittest.TestCase):
    def test_supervisor_delegates_to_single_worker(self) -> None:
        sup = _ScriptedAdapter(backend_id="supervisor", delegate_to="worker-1")
        w1 = _ScriptedAdapter(backend_id="worker-1")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"supervisor": sup, "worker-1": w1},
            config=_enabled_config(
                MultiAgentOrchestrationMode.SUPERVISOR,
                supervisor_agent_id="supervisor",
            ),
        )
        handle = asyncio.run(adapter.submit_run(_make_request()))
        self.assertIn("supervisor", handle.metadata["handoff_chain"])
        self.assertIn("worker-1", handle.metadata["handoff_chain"])
        self.assertEqual(len(handle.metadata["sub_run_ids"]), 2)

    def test_supervisor_delegates_to_multiple_workers(self) -> None:
        sup = _ScriptedAdapter(backend_id="supervisor", delegate_to=["worker-1", "worker-2"])
        w1 = _ScriptedAdapter(backend_id="worker-1")
        w2 = _ScriptedAdapter(backend_id="worker-2")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"supervisor": sup, "worker-1": w1, "worker-2": w2},
            config=_enabled_config(
                MultiAgentOrchestrationMode.SUPERVISOR,
                supervisor_agent_id="supervisor",
            ),
        )
        handle = asyncio.run(adapter.submit_run(_make_request()))
        self.assertEqual(len(handle.metadata["sub_run_ids"]), 3)

    def test_supervisor_no_delegation(self) -> None:
        sup = _ScriptedAdapter(backend_id="supervisor")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"supervisor": sup},
            config=_enabled_config(
                MultiAgentOrchestrationMode.SUPERVISOR,
                supervisor_agent_id="supervisor",
            ),
        )
        handle = asyncio.run(adapter.submit_run(_make_request()))
        self.assertEqual(len(handle.metadata["sub_run_ids"]), 1)
        self.assertEqual(handle.metadata["handoff_chain"], ["supervisor"])

    def test_supervisor_shared_state_committed_to_workers(self) -> None:
        sup = _ScriptedAdapter(
            backend_id="supervisor",
            delegate_to="worker-1",
            shared_state_update={"task": "analyze"},
        )
        w1 = _ScriptedAdapter(backend_id="worker-1")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"supervisor": sup, "worker-1": w1},
            config=_enabled_config(
                MultiAgentOrchestrationMode.SUPERVISOR,
                supervisor_agent_id="supervisor",
            ),
        )
        handle = asyncio.run(adapter.submit_run(_make_request()))
        # Worker should have received the supervisor's committed shared state.
        w1_run = w1.runs[list(w1.runs.keys())[0]]
        self.assertEqual(w1_run.metadata["shared_state_received"]["task"], "analyze")


class TestSharedStateIsolationInOrchestration(unittest.TestCase):
    def test_sequential_cow_commit_between_agents(self) -> None:
        a = _ScriptedAdapter(
            backend_id="agent-a",
            handoff_to="agent-b",
            shared_state_update={"from_a": True},
        )
        b = _ScriptedAdapter(backend_id="agent-b")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a, "agent-b": b},
            config=_enabled_config(entry_agent_id="agent-a"),
        )
        handle = asyncio.run(adapter.submit_run(_make_request()))
        run = asyncio.run(adapter.get_run(handle.run_id))
        # Agent B received Agent A's committed state.
        self.assertTrue(run.metadata["shared_state"]["from_a"])

    def test_parallel_cow_writes_isolated(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a", shared_state_update={"a": 1})
        b = _ScriptedAdapter(backend_id="agent-b", shared_state_update={"b": 2})
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a, "agent-b": b},
            config=_enabled_config(MultiAgentOrchestrationMode.PARALLEL),
        )
        handle = asyncio.run(adapter.submit_run(_make_request()))
        run = asyncio.run(adapter.get_run(handle.run_id))
        shared = run.metadata["shared_state"]
        # Neither agent's write leaked into shared state.
        self.assertNotIn("a", shared)
        self.assertNotIn("b", shared)

    def test_initial_shared_state_from_request_metadata(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a},
            config=_enabled_config(entry_agent_id="agent-a"),
        )
        req = _make_request(metadata={"shared_state": {"init": True}})
        handle = asyncio.run(adapter.submit_run(req))
        run = asyncio.run(adapter.get_run(handle.run_id))
        self.assertTrue(run.metadata["shared_state"]["init"])
        # Agent A received the initial state.
        a_run = a.runs[list(a.runs.keys())[0]]
        self.assertTrue(a_run.metadata["shared_state_received"]["init"])


class TestEnabledModeErrorHandling(unittest.TestCase):
    def test_unknown_agent_in_handoff_raises_routing_error(self) -> None:
        a = _ScriptedAdapter(backend_id="agent-a", handoff_to="nonexistent")
        adapter = MultiAgentRuntimeAdapter(
            sub_adapters={"agent-a": a},
            config=_enabled_config(entry_agent_id="agent-a"),
        )
        from inkstatute_multi_agent_adapter import MultiAgentRoutingError
        with self.assertRaises(MultiAgentRoutingError):
            asyncio.run(adapter.submit_run(_make_request()))


if __name__ == "__main__":
    unittest.main()
