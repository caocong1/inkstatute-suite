"""Deterministic in-memory adapters for runtime lifecycle tests."""

from __future__ import annotations

from dataclasses import replace
from typing import AsyncIterator, Iterable

from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_contract.enums import AsyncTaskState, RunEventType

from .protocols import (
    AckResponse,
    Approval,
    ArtifactRecord,
    BootstrapStatus,
    ChannelCapabilitySet,
    ChannelDelivery,
    ComponentHealth,
    DeliveryResult,
    InboundNormalized,
    RawInbound,
    Run,
    RunEvent,
    RunHandle,
    RunRequest,
)


class FakeIdFactory:
    """Deterministic prefix-scoped ID generator for tests."""

    def __init__(self, *, start: int = 1) -> None:
        self._next_by_prefix: dict[str, int] = {}
        self._start = start

    def new_id(self, prefix: str) -> str:
        next_value = self._next_by_prefix.get(prefix, self._start)
        self._next_by_prefix[prefix] = next_value + 1
        return f"{prefix}-{next_value:03d}"


class FakeRuntimeClock:
    """Deterministic clock whose value advances only when tests ask it to."""

    def __init__(self, *, start: str = "2026-06-29T00:00:00Z") -> None:
        self._current = start

    def now(self) -> str:
        return self._current

    def set(self, value: str) -> None:
        self._current = value


class FakeBackendAdapter:
    """In-memory backend adapter with deterministic run lifecycle scripts."""

    def __init__(
        self,
        *,
        backend_id: str = "fake-backend",
        clock: FakeRuntimeClock | None = None,
        id_factory: FakeIdFactory | None = None,
        submit_statuses: Iterable[AsyncTaskState | str] = (
            AsyncTaskState.QUEUED,
            AsyncTaskState.RUNNING,
            AsyncTaskState.SUCCEEDED,
        ),
    ) -> None:
        self._backend_id = backend_id
        self._clock = clock or FakeRuntimeClock()
        self._id_factory = id_factory or FakeIdFactory()
        self._submit_statuses = tuple(_coerce_status(status) for status in submit_statuses)
        if not self._submit_statuses:
            self._submit_statuses = (AsyncTaskState.QUEUED,)

        self.submitted_requests: list[RunRequest] = []
        self.cancelled_run_ids: list[str] = []
        self.submitted_approvals: list[tuple[str, Approval]] = []
        self.runs: dict[str, Run] = {}
        self.events: dict[str, list[RunEvent]] = {}
        self.artifacts: dict[str, list[ArtifactRecord]] = {}

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
        self.submitted_requests.append(req)
        run_id = self._id_factory.new_id("run")
        backend_run_id = self._id_factory.new_id("backend-run")
        final_status = self._submit_statuses[-1]
        run = Run(
            run_id=run_id,
            status=final_status,
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            metadata={
                "backend_run_id": backend_run_id,
                "backend_id": self._backend_id,
                "tenant_id": req.tenant_id,
                "workspace_id": req.workspace_id,
                "session_id": req.session_id,
                "raw_payload_ref": req.turn.metadata.get("raw_payload_ref"),
            },
        )
        self.runs[run_id] = run
        self.events[run_id] = []
        for status in self._submit_statuses:
            self._append_event(run_id, RunEventType.STATE_CHANGED, status=status)
        self.artifacts[run_id] = [
            ArtifactRecord(
                artifact_id=self._id_factory.new_id("artifact"),
                kind="text",
                uri_ref=f"fixture://artifacts/{run_id}/result",
                name=f"{run_id}-result.txt",
                metadata={"content_sha256": "0" * 64},
            )
        ]
        return RunHandle(
            run_id=run_id,
            backend_run_id=backend_run_id,
            status=self._submit_statuses[0],
            metadata={"event_count": len(self.events[run_id])},
        )

    async def get_run(self, run_id: str) -> Run:
        return self._require_run(run_id)

    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]:
        self._require_run(run_id)
        for event in tuple(self.events[run_id]):
            yield event

    async def cancel_run(self, run_id: str) -> Run:
        run = self._require_run(run_id)
        self.cancelled_run_ids.append(run_id)
        updated = replace(run, status=AsyncTaskState.CANCELLED)
        self.runs[run_id] = updated
        self._append_event(run_id, RunEventType.STATE_CHANGED, status=AsyncTaskState.CANCELLED)
        return updated

    async def submit_approval(self, run_id: str, approval: Approval) -> Run:
        run = self._require_run(run_id)
        self.submitted_approvals.append((run_id, approval))
        metadata = dict(run.metadata)
        metadata["approval_id"] = approval.approval_id
        metadata["approval_decision"] = approval.decision
        updated = replace(run, status=AsyncTaskState.RUNNING, metadata=metadata)
        self.runs[run_id] = updated
        self._append_event(
            run_id,
            RunEventType.APPROVAL_REQUESTED,
            status=AsyncTaskState.WAITING_FOR_USER,
            payload={"approval_id": approval.approval_id, "decision": approval.decision},
        )
        self._append_event(run_id, RunEventType.STATE_CHANGED, status=AsyncTaskState.RUNNING)
        return updated

    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        self._require_run(run_id)
        return list(self.artifacts[run_id])

    def _require_run(self, run_id: str) -> Run:
        try:
            return self.runs[run_id]
        except KeyError as exc:
            raise KeyError(f"unknown fake run: {run_id}") from exc

    def _append_event(
        self,
        run_id: str,
        event_type: RunEventType | str,
        *,
        status: AsyncTaskState | str,
        payload: dict[str, object] | None = None,
    ) -> RunEvent:
        seq = len(self.events[run_id])
        status_value = _coerce_status(status)
        event_payload = {"status": status_value, "raw_payload_ref": f"fixture://runs/{run_id}/events/{seq}"}
        if payload:
            event_payload.update(payload)
        event = RunEvent(
            event_id=self._id_factory.new_id("run-event"),
            run_id=run_id,
            event_type=str(event_type),
            occurred_at=self._clock.now(),
            seq=seq,
            payload=event_payload,
            metadata={"backend_id": self._backend_id},
        )
        self.events[run_id].append(event)
        return event


class FakeChannelAdapter:
    """In-memory channel adapter that records deliveries without I/O."""

    def __init__(
        self,
        *,
        channel_id: str = "fake-channel",
        clock: FakeRuntimeClock | None = None,
        id_factory: FakeIdFactory | None = None,
    ) -> None:
        self._channel_id = channel_id
        self._clock = clock or FakeRuntimeClock()
        self._id_factory = id_factory or FakeIdFactory()
        self.deliveries: list[ChannelDelivery] = []

    def channel_id(self) -> str:
        return self._channel_id

    def capabilities(self) -> ChannelCapabilitySet:
        return ChannelCapabilitySet(
            supports_text=True,
            supports_files=True,
            supports_cards=True,
            supports_streaming=False,
            idempotency_strategy="in_memory",
        )

    async def verify_and_ack(self, raw: RawInbound) -> AckResponse:
        return AckResponse(
            accepted=True,
            idempotency_key=raw.idempotency_key,
            metadata={"channel_id": self._channel_id},
        )

    async def normalize_inbound(self, raw: RawInbound) -> InboundNormalized:
        return InboundNormalized(metadata={"payload_ref": raw.payload_ref})

    async def deliver(self, delivery: ChannelDelivery) -> DeliveryResult:
        self.deliveries.append(delivery)
        return DeliveryResult(
            delivery_id=delivery.delivery_id or self._id_factory.new_id("delivery"),
            accepted=True,
            delivered_at=self._clock.now(),
            idempotency_key=delivery.metadata.get("idempotency_key"),
            metadata={"channel_id": self._channel_id, "recorded": True},
        )

    async def health(self) -> ComponentHealth:
        return ComponentHealth(
            ok=True,
            component_id=self._channel_id,
            checked_at=self._clock.now(),
            metadata={"in_memory": True},
        )


def _coerce_status(status: AsyncTaskState | str) -> AsyncTaskState:
    return status if isinstance(status, AsyncTaskState) else AsyncTaskState(str(status))


__all__ = [
    "FakeBackendAdapter",
    "FakeChannelAdapter",
    "FakeIdFactory",
    "FakeRuntimeClock",
]
