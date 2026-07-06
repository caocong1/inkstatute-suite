"""MultiAgentRuntimeAdapter — composite BackendAdapter wrapping multiple sub-adapters.

The adapter implements the frozen 9-method ``BackendAdapter`` Protocol via
structural subtyping (no explicit inheritance).  It wraps a
``dict[str, Any]`` of sub-adapters keyed by ``backend_id`` (agent_id) and
delegates ``submit_run`` by ``solution.backend_id``.

When ``config.enabled`` is ``False`` (default), the adapter is transparent —
``submit_run`` delegates directly to the matching sub-adapter with no
orchestration, cycle detection, or shared state management.

When ``config.enabled`` is ``True``, the adapter orchestrates sub-agents in
sequential, parallel, or supervisor mode with:
- ``max_handoffs=5`` enforcement (over-limit raises ``MultiAgentHandoffLimitError``)
- Cycle detection via visited-set (cycle raises ``MultiAgentCycleError``)
- Copy-on-write shared state scoped to ``parent_run_id``
- ``asyncio.Semaphore`` bounding parallel fan-out concurrency
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_contract.enums import AsyncTaskState

from platform_runtime import (
    Approval,
    ArtifactRecord,
    BootstrapStatus,
    Run,
    RunEvent,
    RunHandle,
    RunRequest,
)

from .config import MultiAgentOrchestrationMode, MultiAgentRuntimeAdapterConfig
from .errors import (
    MultiAgentCycleError,
    MultiAgentHandoffLimitError,
    MultiAgentRoutingError,
)
from .shared_state import SharedStateStore


# ---------------------------------------------------------------------------
# Internal records
# ---------------------------------------------------------------------------


@dataclass
class _ParentRunRecord:
    """Tracks a multi-agent parent run and its sub-runs."""

    parent_run_id: str
    sub_run_ids: list[str] = field(default_factory=list)
    sub_run_to_agent: dict[str, str] = field(default_factory=dict)
    handoff_chain: list[str] = field(default_factory=list)
    shared_state_key: str = ""
    final_run: Run | None = None
    status: AsyncTaskState | str = AsyncTaskState.QUEUED
    events: list[RunEvent] = field(default_factory=list)
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    req: RunRequest | None = None
    cancelled: bool = False


# ---------------------------------------------------------------------------
# MultiAgentRuntimeAdapter
# ---------------------------------------------------------------------------


class MultiAgentRuntimeAdapter:
    """Composite BackendAdapter wrapping multiple sub-adapters with orchestration.

    Sub-adapters are injected as a ``dict[str, Any]`` keyed by ``backend_id``
    (agent_id).  The adapter does NOT import backend packages directly — it
    only depends on ``platform_contract`` and ``platform_runtime``, preserving
    the ``dependencies = []`` invariant.
    """

    def __init__(
        self,
        *,
        sub_adapters: dict[str, Any],
        config: MultiAgentRuntimeAdapterConfig | None = None,
        clock: Any | None = None,
    ) -> None:
        self.config = config or MultiAgentRuntimeAdapterConfig()
        self._sub_adapters = dict(sub_adapters)
        self._clock = clock or _SystemClock()
        self._run_to_adapter: dict[str, str] = {}
        self._run_requests: dict[str, RunRequest] = {}
        self._parent_records: dict[str, _ParentRunRecord] = {}
        self._shared_store = SharedStateStore()
        self._next_parent_id = 1

    # ------------------------------------------------------------------
    # BackendAdapter Protocol — 9 methods
    # ------------------------------------------------------------------

    def backend_id(self) -> str:
        return self.config.adapter_id

    def capabilities(self) -> AdapterCapabilitySet:
        return _merge_capabilities(self._sub_adapters)

    async def bootstrap_check(self) -> BootstrapStatus:
        issues: list[str] = []
        all_ok = True
        for adapter in self._sub_adapters.values():
            status = await adapter.bootstrap_check()
            if not status.ok:
                all_ok = False
            issues.extend(status.issues)
        if not self._sub_adapters:
            all_ok = False
            issues.append("no_sub_adapters_configured")
        return BootstrapStatus(
            ok=all_ok,
            backend_id=self.config.adapter_id,
            checked_at=self._clock.now(),
            issues=issues,
            metadata={
                "sub_adapter_count": len(self._sub_adapters),
                "sub_adapter_ids": list(self._sub_adapters.keys()),
                "enabled": self.config.enabled,
                "orchestration_mode": _mode_value(self.config.orchestration.mode),
            },
        )

    async def submit_run(self, req: RunRequest) -> RunHandle:
        if self.config.enabled:
            return await self._submit_run_enabled(req)
        return await self._submit_run_passthrough(req)

    async def get_run(self, run_id: str) -> Run:
        if run_id in self._parent_records:
            return self._parent_run(run_id)
        adapter = self._resolve_adapter(run_id)
        return await adapter.get_run(run_id)

    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]:
        if run_id in self._parent_records:
            for event in tuple(self._parent_records[run_id].events):
                yield event
            return
        adapter = self._resolve_adapter(run_id)
        async for event in adapter.stream_events(run_id):
            yield event

    async def cancel_run(self, run_id: str) -> Run:
        if run_id in self._parent_records:
            return await self._cancel_parent_run(run_id)
        adapter = self._resolve_adapter(run_id)
        return await adapter.cancel_run(run_id)

    async def submit_approval(self, run_id: str, approval: Approval) -> Run:
        adapter = self._resolve_adapter(run_id)
        return await adapter.submit_approval(run_id, approval)

    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        if run_id in self._parent_records:
            return list(self._parent_records[run_id].artifacts)
        adapter = self._resolve_adapter(run_id)
        return await adapter.collect_artifacts(run_id)

    # ------------------------------------------------------------------
    # Pass-through mode (disabled)
    # ------------------------------------------------------------------

    async def _submit_run_passthrough(self, req: RunRequest) -> RunHandle:
        """Transparent delegation — no orchestration."""
        backend_id = req.solution.backend_id
        if backend_id is None:
            raise KeyError("solution.backend_id is None; cannot route to sub-adapter")
        adapter = self._sub_adapters.get(backend_id)
        if adapter is None:
            raise KeyError(
                f"no sub-adapter registered for backend_id={backend_id!r}; "
                f"available: {list(self._sub_adapters.keys())}"
            )
        handle = await adapter.submit_run(req)
        self._run_to_adapter[handle.run_id] = backend_id
        self._run_requests[handle.run_id] = req
        return handle

    # ------------------------------------------------------------------
    # Enabled mode — orchestration
    # ------------------------------------------------------------------

    async def _submit_run_enabled(self, req: RunRequest) -> RunHandle:
        """Enabled mode with sequential/parallel/supervisor orchestration."""
        parent_run_id = f"ma-{self._next_parent_id:04d}"
        self._next_parent_id += 1

        initial_state = {}
        if req.metadata:
            initial_state = dict(req.metadata.get("shared_state", {}))

        self._shared_store.init(parent_run_id, initial_state)

        record = _ParentRunRecord(
            parent_run_id=parent_run_id,
            shared_state_key=parent_run_id,
            status=AsyncTaskState.RUNNING,
            req=req,
        )
        self._parent_records[parent_run_id] = record

        mode = _mode_value(self.config.orchestration.mode)
        try:
            if mode == MultiAgentOrchestrationMode.SEQUENTIAL.value:
                await self._orchestrate_sequential(req, parent_run_id, record)
            elif mode == MultiAgentOrchestrationMode.PARALLEL.value:
                await self._orchestrate_parallel(req, parent_run_id, record)
            elif mode == MultiAgentOrchestrationMode.SUPERVISOR.value:
                await self._orchestrate_supervisor(req, parent_run_id, record)
            else:
                raise ValueError(f"unknown orchestration mode: {mode!r}")
        except (MultiAgentHandoffLimitError, MultiAgentCycleError, MultiAgentRoutingError):
            record.status = AsyncTaskState.FAILED
            self._append_parent_event(
                record,
                "state_changed",
                status=AsyncTaskState.FAILED,
                payload={"error": "orchestration_failed"},
            )
            raise

        final_run = record.final_run
        status = AsyncTaskState.SUCCEEDED
        if final_run is not None:
            status = final_run.status
        record.status = status

        return RunHandle(
            run_id=parent_run_id,
            backend_run_id=None,
            status=AsyncTaskState.RUNNING,
            metadata={
                "multi_agent_enabled": True,
                "orchestration_mode": mode,
                "sub_run_count": len(record.sub_run_ids),
                "handoff_chain": list(record.handoff_chain),
                "sub_run_ids": list(record.sub_run_ids),
            },
        )

    # ------------------------------------------------------------------
    # Sequential orchestration
    # ------------------------------------------------------------------

    async def _orchestrate_sequential(
        self,
        req: RunRequest,
        parent_run_id: str,
        record: _ParentRunRecord,
    ) -> None:
        orch = self.config.orchestration
        current_agent = orch.entry_agent_id or req.solution.backend_id
        if current_agent is None:
            raise MultiAgentRoutingError("no entry_agent_id and solution.backend_id is None")

        visited: list[str] = [current_agent]
        record.handoff_chain = list(visited)
        handoff_count = 0

        while True:
            adapter = self._sub_adapters.get(current_agent)
            if adapter is None:
                raise MultiAgentRoutingError(
                    f"no sub-adapter registered for agent_id={current_agent!r}; "
                    f"available: {list(self._sub_adapters.keys())}"
                )

            snapshot = self._shared_store.snapshot(parent_run_id)
            sub_req = self._build_sub_request(req, current_agent, parent_run_id, snapshot)
            handle = await adapter.submit_run(sub_req)
            run = await adapter.get_run(handle.run_id)

            record.sub_run_ids.append(handle.run_id)
            record.sub_run_to_agent[handle.run_id] = current_agent
            self._run_to_adapter[handle.run_id] = current_agent
            self._run_requests[handle.run_id] = sub_req
            self._append_parent_event(
                record,
                "state_changed",
                status=run.status,
                payload={"agent_id": current_agent, "sub_run_id": handle.run_id},
            )
            await self._collect_sub_artifacts(adapter, handle.run_id, record)

            # Extract and apply shared state update via COW.
            update = self._extract_shared_state_update(run)
            if update:
                self._shared_store.write_all(parent_run_id, current_agent, update)
                self._shared_store.commit(parent_run_id, current_agent)

            record.final_run = run

            # Check for handoff.
            handoff_to = self._extract_handoff_to(run)
            if not handoff_to:
                break

            # Cycle detection.
            if handoff_to in visited:
                cycle = visited + [handoff_to]
                raise MultiAgentCycleError(
                    f"handoff cycle detected: {' -> '.join(cycle)} "
                    f"(agent {handoff_to!r} already in handoff chain)"
                )

            # Max handoffs enforcement.
            if handoff_count >= orch.max_handoffs:
                raise MultiAgentHandoffLimitError(
                    f"handoff limit exceeded: {handoff_count} handoffs >= max_handoffs={orch.max_handoffs}; "
                    f"handoff chain: {' -> '.join(visited)}"
                )

            handoff_count += 1
            visited.append(handoff_to)
            record.handoff_chain = list(visited)
            current_agent = handoff_to

    # ------------------------------------------------------------------
    # Parallel orchestration
    # ------------------------------------------------------------------

    async def _orchestrate_parallel(
        self,
        req: RunRequest,
        parent_run_id: str,
        record: _ParentRunRecord,
    ) -> None:
        orch = self.config.orchestration
        agent_ids = list(orch.agent_set) if orch.agent_set else list(self._sub_adapters.keys())
        if not agent_ids:
            raise MultiAgentRoutingError("no agents available for parallel orchestration")

        snapshot = self._shared_store.snapshot(parent_run_id)
        sem = asyncio.Semaphore(orch.parallel_concurrency)

        async def _run_agent(agent_id: str) -> tuple[str, RunHandle, Run]:
            async with sem:
                adapter = self._sub_adapters.get(agent_id)
                if adapter is None:
                    raise MultiAgentRoutingError(
                        f"no sub-adapter registered for agent_id={agent_id!r}"
                    )
                sub_req = self._build_sub_request(req, agent_id, parent_run_id, snapshot)
                handle = await adapter.submit_run(sub_req)
                run = await adapter.get_run(handle.run_id)
                return agent_id, handle, run

        results = await asyncio.gather(*[_run_agent(a) for a in agent_ids])

        last_run: Run | None = None
        for agent_id, handle, run in results:
            record.sub_run_ids.append(handle.run_id)
            record.sub_run_to_agent[handle.run_id] = agent_id
            self._run_to_adapter[handle.run_id] = agent_id
            self._run_requests[handle.run_id] = req
            self._append_parent_event(
                record,
                "state_changed",
                status=run.status,
                payload={"agent_id": agent_id, "sub_run_id": handle.run_id},
            )
            # COW write — isolated per agent, NOT committed to shared state.
            update = self._extract_shared_state_update(run)
            if update:
                self._shared_store.write_all(parent_run_id, agent_id, update)
            adapter = self._sub_adapters[agent_id]
            await self._collect_sub_artifacts(adapter, handle.run_id, record)
            last_run = run

        record.final_run = last_run
        record.handoff_chain = list(agent_ids)

    # ------------------------------------------------------------------
    # Supervisor orchestration
    # ------------------------------------------------------------------

    async def _orchestrate_supervisor(
        self,
        req: RunRequest,
        parent_run_id: str,
        record: _ParentRunRecord,
    ) -> None:
        orch = self.config.orchestration
        supervisor_id = orch.supervisor_agent_id or orch.entry_agent_id or req.solution.backend_id
        if supervisor_id is None:
            raise MultiAgentRoutingError("no supervisor_agent_id and solution.backend_id is None")

        # Supervisor runs first.
        snapshot = self._shared_store.snapshot(parent_run_id)
        sup_run, sup_handle = await self._dispatch_agent(
            req, supervisor_id, parent_run_id, snapshot, record
        )
        record.handoff_chain = [supervisor_id]

        # Extract and commit supervisor's shared state update.
        update = self._extract_shared_state_update(sup_run)
        if update:
            self._shared_store.write_all(parent_run_id, supervisor_id, update)
            self._shared_store.commit(parent_run_id, supervisor_id)

        # Check for delegation.
        delegate_to = self._extract_delegate_to(sup_run)
        if delegate_to:
            worker_ids = delegate_to if isinstance(delegate_to, list) else [delegate_to]
            worker_snapshot = self._shared_store.snapshot(parent_run_id)
            sem = asyncio.Semaphore(orch.parallel_concurrency)

            async def _run_worker(worker_id: str) -> tuple[str, RunHandle, Run]:
                async with sem:
                    return await self._dispatch_agent_raw(
                        req, worker_id, parent_run_id, worker_snapshot
                    )

            worker_results = await asyncio.gather(*[_run_worker(w) for w in worker_ids])
            for worker_id, w_handle, w_run in worker_results:
                record.sub_run_ids.append(w_handle.run_id)
                record.sub_run_to_agent[w_handle.run_id] = worker_id
                self._run_to_adapter[w_handle.run_id] = worker_id
                self._run_requests[w_handle.run_id] = req
                self._append_parent_event(
                    record,
                    "state_changed",
                    status=w_run.status,
                    payload={"agent_id": worker_id, "sub_run_id": w_handle.run_id, "role": "worker"},
                )
                w_update = self._extract_shared_state_update(w_run)
                if w_update:
                    self._shared_store.write_all(parent_run_id, worker_id, w_update)
                w_adapter = self._sub_adapters.get(worker_id)
                if w_adapter is not None:
                    await self._collect_sub_artifacts(w_adapter, w_handle.run_id, record)
                record.handoff_chain.append(worker_id)

        record.final_run = sup_run

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_sub_request(
        self,
        req: RunRequest,
        agent_id: str,
        parent_run_id: str,
        shared_state: dict[str, Any],
    ) -> RunRequest:
        """Build a sub-RunRequest with the target agent_id and shared state."""
        new_metadata = dict(req.metadata) if req.metadata else {}
        new_metadata["shared_state"] = dict(shared_state)
        new_metadata["parent_run_id"] = parent_run_id
        new_metadata["agent_id"] = agent_id
        new_solution = replace(req.solution, backend_id=agent_id)
        return replace(req, solution=new_solution, metadata=new_metadata)

    async def _dispatch_agent(
        self,
        req: RunRequest,
        agent_id: str,
        parent_run_id: str,
        snapshot: dict[str, Any],
        record: _ParentRunRecord,
    ) -> tuple[Run, RunHandle]:
        """Submit and record a single agent run. Returns (run, handle)."""
        adapter = self._sub_adapters.get(agent_id)
        if adapter is None:
            raise MultiAgentRoutingError(
                f"no sub-adapter registered for agent_id={agent_id!r}; "
                f"available: {list(self._sub_adapters.keys())}"
            )
        sub_req = self._build_sub_request(req, agent_id, parent_run_id, snapshot)
        handle = await adapter.submit_run(sub_req)
        run = await adapter.get_run(handle.run_id)
        record.sub_run_ids.append(handle.run_id)
        record.sub_run_to_agent[handle.run_id] = agent_id
        self._run_to_adapter[handle.run_id] = agent_id
        self._run_requests[handle.run_id] = sub_req
        self._append_parent_event(
            record,
            "state_changed",
            status=run.status,
            payload={"agent_id": agent_id, "sub_run_id": handle.run_id},
        )
        await self._collect_sub_artifacts(adapter, handle.run_id, record)
        return run, handle

    async def _dispatch_agent_raw(
        self,
        req: RunRequest,
        agent_id: str,
        parent_run_id: str,
        snapshot: dict[str, Any],
    ) -> tuple[str, RunHandle, Run]:
        """Submit a single agent run without recording into a _ParentRunRecord."""
        adapter = self._sub_adapters.get(agent_id)
        if adapter is None:
            raise MultiAgentRoutingError(
                f"no sub-adapter registered for agent_id={agent_id!r}"
            )
        sub_req = self._build_sub_request(req, agent_id, parent_run_id, snapshot)
        handle = await adapter.submit_run(sub_req)
        run = await adapter.get_run(handle.run_id)
        return agent_id, handle, run

    async def _collect_sub_artifacts(
        self,
        adapter: Any,
        run_id: str,
        record: _ParentRunRecord,
    ) -> None:
        try:
            arts = await adapter.collect_artifacts(run_id)
            record.artifacts.extend(arts)
        except Exception:  # noqa: BLE001
            pass

    def _extract_shared_state_update(self, run: Run) -> dict[str, Any]:
        update = run.metadata.get("shared_state_update") if run.metadata else None
        if isinstance(update, dict):
            return update
        return {}

    def _extract_handoff_to(self, run: Run) -> str | None:
        handoff = run.metadata.get("handoff_to") if run.metadata else None
        if isinstance(handoff, str) and handoff:
            return handoff
        return None

    def _extract_delegate_to(self, run: Run) -> str | list[str] | None:
        delegate = run.metadata.get("delegate_to") if run.metadata else None
        if isinstance(delegate, str) and delegate:
            return delegate
        if isinstance(delegate, list) and delegate:
            return delegate
        return None

    def _append_parent_event(
        self,
        record: _ParentRunRecord,
        event_type: str,
        *,
        status: AsyncTaskState | str,
        payload: dict[str, Any] | None = None,
    ) -> RunEvent:
        seq = len(record.events)
        event_payload: dict[str, Any] = {"status": _status_value(status)}
        if payload:
            event_payload.update(payload)
        event = RunEvent(
            event_id=f"{record.parent_run_id}-evt-{seq:03d}",
            run_id=record.parent_run_id,
            event_type=event_type,
            occurred_at=self._clock.now(),
            seq=seq,
            payload=event_payload,
            metadata={},
        )
        record.events.append(event)
        return event

    def _parent_run(self, parent_run_id: str) -> Run:
        record = self._parent_records[parent_run_id]
        final = record.final_run
        result = final.result if final is not None else None
        return Run(
            run_id=parent_run_id,
            status=record.status,
            turn_id=record.req.turn.turn_id if record.req else "",
            solution_id=record.req.solution.solution_id if record.req else "",
            result=result,
            metadata={
                "multi_agent": True,
                "orchestration_mode": _mode_value(self.config.orchestration.mode),
                "sub_run_ids": list(record.sub_run_ids),
                "handoff_chain": list(record.handoff_chain),
                "sub_run_to_agent": dict(record.sub_run_to_agent),
                "shared_state": self._shared_store.snapshot(parent_run_id) if parent_run_id in self._shared_store._shared else {},
            },
        )

    async def _cancel_parent_run(self, parent_run_id: str) -> Run:
        record = self._parent_records[parent_run_id]
        record.cancelled = True
        record.status = AsyncTaskState.CANCELLED
        for sub_run_id in record.sub_run_ids:
            agent_id = record.sub_run_to_agent.get(sub_run_id)
            if agent_id is None:
                continue
            adapter = self._sub_adapters.get(agent_id)
            if adapter is not None:
                try:
                    await adapter.cancel_run(sub_run_id)
                except Exception:  # noqa: BLE001
                    pass
        self._append_parent_event(
            record,
            "state_changed",
            status=AsyncTaskState.CANCELLED,
            payload={"cancelled": True},
        )
        return self._parent_run(parent_run_id)

    def _resolve_adapter(self, run_id: str) -> Any:
        backend_id = self._run_to_adapter.get(run_id)
        if backend_id is None:
            raise KeyError(f"unknown multi-agent run: {run_id}")
        adapter = self._sub_adapters.get(backend_id)
        if adapter is None:
            raise KeyError(f"sub-adapter {backend_id!r} no longer registered")
        return adapter


# ---------------------------------------------------------------------------
# Capability merging
# ---------------------------------------------------------------------------


def _merge_capabilities(sub_adapters: dict[str, Any]) -> AdapterCapabilitySet:
    """Merge sub-adapter capabilities into a single AdapterCapabilitySet.

    Boolean fields are OR'd (True if any sub-adapter has True).
    List fields are unioned (deduplicated, order preserved).
    String fields take the first non-None value.
    """

    hook_events: list[str] = []
    invocation_mode: str | None = None
    feedback_target: str | None = None
    session_read = False
    artifact_return = False
    trace = False
    no_channel_io: bool | None = None
    run_modes: list[str] = []
    stream_event = False
    cancel = False
    approval = False
    live_update = False
    parallel = False
    session_memory = False

    for adapter in sub_adapters.values():
        caps = adapter.capabilities()
        for item in caps.hook_event_support:
            if item not in hook_events:
                hook_events.append(item)
        if invocation_mode is None:
            invocation_mode = caps.invocation_mode
        if feedback_target is None:
            feedback_target = caps.feedback_target_support
        session_read = session_read or caps.session_read_support
        artifact_return = artifact_return or caps.artifact_return_support
        trace = trace or caps.trace_support
        if no_channel_io is None:
            no_channel_io = caps.no_channel_io
        elif caps.no_channel_io is True:
            no_channel_io = True
        for mode in caps.run_invocation_modes:
            if mode not in run_modes:
                run_modes.append(mode)
        stream_event = stream_event or caps.stream_event_support
        cancel = cancel or caps.cancel_support
        approval = approval or caps.approval_support
        live_update = live_update or caps.live_update_support
        parallel = parallel or caps.parallel_task_support
        session_memory = session_memory or caps.session_memory_support

    return AdapterCapabilitySet(
        hook_event_support=hook_events,
        invocation_mode=invocation_mode,
        feedback_target_support=feedback_target,
        session_read_support=session_read,
        artifact_return_support=artifact_return,
        trace_support=trace,
        no_channel_io=no_channel_io,
        run_invocation_modes=run_modes,
        stream_event_support=stream_event,
        cancel_support=cancel,
        approval_support=approval,
        live_update_support=live_update,
        parallel_task_support=parallel,
        session_memory_support=session_memory,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _status_value(status: AsyncTaskState | str) -> str:
    if isinstance(status, AsyncTaskState):
        return status.value
    return str(status)


def _mode_value(mode: MultiAgentOrchestrationMode | str) -> str:
    if isinstance(mode, MultiAgentOrchestrationMode):
        return mode.value
    return str(mode)


class _SystemClock:
    def now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = ["MultiAgentRuntimeAdapter"]
