"""MockACPBackendAdapter — deterministic offline BackendAdapter for arena tests.

Implements the :class:`BackendAdapter` Protocol from
``platform_runtime.protocols`` with fully deterministic behaviour:
no subprocesses, no network, no LLM providers.  Used by the arena-engine
test suite and by SlotRunner integration tests.

ENGINE-05: this module imports zero LLM provider packages.
ENGINE-06: this module never calls ``session/resume`` or ``resume_session``.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any, AsyncIterator

from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_contract.enums import AsyncTaskState, RunEventType
from platform_runtime.fakes import FakeIdFactory, FakeRuntimeClock
from platform_runtime.protocols import (
    Approval,
    ArtifactRecord,
    BootstrapStatus,
    Run,
    RunEvent,
    RunHandle,
    RunRequest,
)

from .families import get_backend_family

JsonObject = dict[str, Any]


class MockACPBackendAdapter:
    """Deterministic in-memory BackendAdapter with scripted responses.

    All nine ``BackendAdapter`` Protocol methods are implemented with
    deterministic behaviour suitable for offline arena testing.  Run IDs
    follow the pattern ``mock-run-001``, ``mock-run-002``, … using
    :class:`FakeIdFactory`.

    Parameters
    ----------
    backend_id
        Unique identifier for this mock backend.
    responses
        Ordered list of scripted response strings.  Each ``submit_run``
        consumes the next response (cycling if exhausted).
    agent_slot
        Slot identifier stamped into every event's metadata.
    crash_on_stream
        If ``True``, ``stream_events`` raises ``RuntimeError("mock crash")``
        instead of yielding events.
    timeout_seconds
        Configured timeout (stored in metadata; actual timeout enforcement
        is the caller's responsibility via ``SlotRunner``).
    delay
        Seconds to ``asyncio.sleep`` before yielding the first event.
    id_factory
        Optional deterministic ID factory.  Defaults to a new
        :class:`FakeIdFactory`.
    backend_family
        Optional explicit model family for cross-family enforcement
        (SAFE-06).  When ``None``, auto-derives from ``backend_id`` via
        :func:`get_backend_family`.
    """

    def __init__(
        self,
        *,
        backend_id: str,
        responses: list[str],
        agent_slot: str = "slot-0",
        crash_on_stream: bool = False,
        timeout_seconds: float = 30.0,
        delay: float = 0.0,
        id_factory: FakeIdFactory | None = None,
        backend_family: str | None = None,
    ) -> None:
        self._backend_id = backend_id
        self._backend_family = backend_family
        self._responses = list(responses)
        self._agent_slot = agent_slot
        self._crash_on_stream = crash_on_stream
        self._timeout_seconds = timeout_seconds
        self._delay = delay
        self._id_factory = id_factory or FakeIdFactory()
        self._clock = FakeRuntimeClock()
        self._response_index = 0

        # Public observability collections (mirrors FakeBackendAdapter)
        self.submitted_requests: list[RunRequest] = []
        self.cancelled_run_ids: list[str] = []
        self.runs: dict[str, Run] = {}
        self.events: dict[str, list[RunEvent]] = {}
        self.artifacts: dict[str, list[ArtifactRecord]] = {}

        # Active session tracking — mirrors the real ACP adapter's
        # ``_sessions`` so the engine's "zero orphaned processes" cleanup
        # logic (ENGINE-09) can be validated with the mock.  Each
        # ``submit_run`` opens a session; ``cancel_run`` / ``shutdown``
        # close it.  Phase 107 uses mocks (no real subprocesses); the
        # real subprocess PID assertion is Phase 109.
        self._sessions: set[str] = set()

    # ------------------------------------------------------------------
    # Protocol method 1: backend_id
    # ------------------------------------------------------------------

    def backend_id(self) -> str:
        return self._backend_id

    # ------------------------------------------------------------------
    # Protocol method 2: backend_family
    # ------------------------------------------------------------------

    def backend_family(self) -> str:
        """Return the model family for cross-family enforcement (SAFE-06).

        When an explicit ``backend_family`` was provided at construction,
        return it directly.  Otherwise, auto-derive from ``backend_id``
        via :func:`get_backend_family` (uses :data:`DEFAULT_FAMILY_MAP`).
        Unknown backends default to their own ID as the family.
        """
        if self._backend_family is not None:
            return self._backend_family
        return get_backend_family(self._backend_id)

    # ------------------------------------------------------------------
    # Protocol method 3: capabilities
    # ------------------------------------------------------------------

    def capabilities(self) -> AdapterCapabilitySet:
        return AdapterCapabilitySet(
            stream_event_support=True,
            cancel_support=True,
        )

    # ------------------------------------------------------------------
    # Protocol method 3: bootstrap_check
    # ------------------------------------------------------------------

    async def bootstrap_check(self) -> BootstrapStatus:
        return BootstrapStatus(
            ok=True,
            backend_id=self._backend_id,
            checked_at=self._clock.now(),
            metadata={"in_memory": True, "mock": True},
        )

    # ------------------------------------------------------------------
    # Protocol method 4: submit_run
    # ------------------------------------------------------------------

    async def submit_run(self, req: RunRequest) -> RunHandle:
        self.submitted_requests.append(req)
        run_id = self._id_factory.new_id("mock-run")
        response = self._next_response()

        run = Run(
            run_id=run_id,
            status=AsyncTaskState.RUNNING,
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            metadata={
                "backend_id": self._backend_id,
                "agent_slot": self._agent_slot,
                "timeout_seconds": self._timeout_seconds,
                "crash_on_stream": self._crash_on_stream,
                "delay": self._delay,
            },
        )
        self.runs[run_id] = run
        self.events[run_id] = []
        self.artifacts[run_id] = []
        self._sessions.add(run_id)

        # Script MESSAGE_DELTA per response chunk + MESSAGE_COMPLETED
        if response:
            self._append_event(
                run_id,
                RunEventType.MESSAGE_DELTA,
                payload={"message_delta": response},
            )
        self._append_event(
            run_id,
            RunEventType.MESSAGE_COMPLETED,
            payload={"content": response},
        )

        return RunHandle(
            run_id=run_id,
            backend_run_id=f"mock-session-{run_id}",
            status=AsyncTaskState.RUNNING,
            metadata={"backend_id": self._backend_id, "agent_slot": self._agent_slot},
        )

    # ------------------------------------------------------------------
    # Protocol method 5: get_run
    # ------------------------------------------------------------------

    async def get_run(self, run_id: str) -> Run:
        return self._require_run(run_id)

    # ------------------------------------------------------------------
    # Protocol method 6: stream_events
    # ------------------------------------------------------------------

    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]:
        self._require_run(run_id)

        if self._crash_on_stream:
            # Record the crash in run metadata
            run = self.runs[run_id]
            self.runs[run_id] = replace(
                run,
                status=AsyncTaskState.FAILED,
                metadata={**run.metadata, "crash": "mock crash"},
            )
            raise RuntimeError("mock crash")

        if self._delay > 0:
            await asyncio.sleep(self._delay)

        for event in tuple(self.events[run_id]):
            yield event

    # ------------------------------------------------------------------
    # Protocol method 7: cancel_run
    # ------------------------------------------------------------------

    async def cancel_run(self, run_id: str) -> Run:
        run = self._require_run(run_id)
        self.cancelled_run_ids.append(run_id)
        self._sessions.discard(run_id)
        updated = replace(run, status=AsyncTaskState.CANCELLED)
        self.runs[run_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Protocol method 8: submit_approval
    # ------------------------------------------------------------------

    async def submit_approval(self, run_id: str, approval: Approval) -> Run:
        run = self._require_run(run_id)
        updated = replace(
            run,
            metadata={
                **run.metadata,
                "approval_id": approval.approval_id,
                "approval_decision": approval.decision,
            },
        )
        self.runs[run_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Protocol method 9: collect_artifacts
    # ------------------------------------------------------------------

    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        self._require_run(run_id)
        return list(self.artifacts[run_id])

    # ------------------------------------------------------------------
    # Cleanup — mirrors ACPBackendAdapter.shutdown() (adapter.py:452-466)
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Close all active sessions (zero orphaned processes, ENGINE-09).

        Mirrors the real :meth:`ACPBackendAdapter.shutdown` pattern: clear
        all active sessions so no orphaned subprocesses remain.  For the
        mock this simply empties ``_sessions``.
        """
        self._sessions.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_response(self) -> str:
        if not self._responses:
            return ""
        response = self._responses[self._response_index % len(self._responses)]
        self._response_index += 1
        return response

    def _require_run(self, run_id: str) -> Run:
        try:
            return self.runs[run_id]
        except KeyError as exc:
            raise KeyError(f"unknown mock run: {run_id}") from exc

    def _append_event(
        self,
        run_id: str,
        event_type: RunEventType | str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> RunEvent:
        seq = len(self.events[run_id])
        event_payload: dict[str, Any] = {
            "raw_payload_ref": f"mock://runs/{run_id}/events/{seq}",
        }
        if payload:
            event_payload.update(payload)
        event = RunEvent(
            event_id=self._id_factory.new_id("mock-event"),
            run_id=run_id,
            event_type=str(event_type),
            occurred_at=self._clock.now(),
            seq=seq,
            payload=event_payload,
            metadata={
                "agent_slot": self._agent_slot,
                "backend_id": self._backend_id,
            },
        )
        self.events[run_id].append(event)
        return event


__all__ = ["MockACPBackendAdapter"]
