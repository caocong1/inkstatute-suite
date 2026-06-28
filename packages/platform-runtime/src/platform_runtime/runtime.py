"""Dependency-injected embeddable run runtime."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from typing import AsyncIterator, Iterable, Mapping

from platform_contract.enums import AsyncTaskState, RunEventType

from .feature_flags import RuntimeFeatureFlags
from .output_boundary import BoundaryAction, DefaultAssistantOutputBoundary
from .ports import AssistantOutputBoundary, ContractLogStore, IdFactory, RuntimeClock
from .protocols import Approval, BackendAdapter, ChannelAdapter, Run, RunEvent, RunRequest


class RunRuntimeStateError(RuntimeError):
    """Raised when runtime dependencies are inconsistent with enabled lanes."""


class DefaultRunRuntime:
    """RunRuntime implementation that speaks only injected protocol ports."""

    def __init__(
        self,
        *,
        backend: BackendAdapter,
        channels: Iterable[ChannelAdapter] = (),
        feature_flags: RuntimeFeatureFlags | None = None,
        contract_log_store: ContractLogStore | None = None,
        output_boundary: AssistantOutputBoundary | None = None,
        clock: RuntimeClock | None = None,
        id_factory: IdFactory | None = None,
    ) -> None:
        self.backend = backend
        self.channels = tuple(channels)
        self.feature_flags = feature_flags or RuntimeFeatureFlags()
        self.contract_log_store = contract_log_store
        self.output_boundary = output_boundary or DefaultAssistantOutputBoundary()
        self.clock = clock or _SystemRuntimeClock()
        self.id_factory = id_factory or _SequentialIdFactory()

    async def create_run(self, req: RunRequest) -> Run:
        self.feature_flags.require_enabled("run_runtime_enabled")
        handle = await self.backend.submit_run(req)
        if self.feature_flags.contract_log_enabled:
            self._append_run_record(req, handle.run_id, handle.status, handle.backend_run_id)
            self._append_state_event(
                run_id=handle.run_id,
                turn_id=req.turn.turn_id,
                status=handle.status,
                event_id=self.id_factory.new_id("run-event"),
                metadata={"source": "runtime_create"},
            )
        return await self.backend.get_run(handle.run_id)

    async def poll(self, run_id: str) -> Run:
        self.feature_flags.require_enabled("run_runtime_enabled")
        return await self.backend.get_run(run_id)

    async def stream(self, run_id: str) -> AsyncIterator[RunEvent]:
        self.feature_flags.require_enabled("run_runtime_enabled")
        self.feature_flags.require_enabled("streaming_lane_enabled")
        async for event in self.backend.stream_events(run_id):
            bounded_event = self._apply_output_boundary(event)
            if bounded_event is not None:
                yield bounded_event

    async def cancel(self, run_id: str) -> Run:
        self.feature_flags.require_enabled("run_runtime_enabled")
        run = await self.backend.cancel_run(run_id)
        if self.feature_flags.contract_log_enabled:
            self._append_state_event(
                run_id=run.run_id,
                turn_id=run.turn_id,
                status=AsyncTaskState.CANCELLED,
                event_id=self.id_factory.new_id("run-event"),
                metadata={"source": "runtime_cancel"},
            )
        return run

    async def approve(self, run_id: str, approval: Approval) -> Run:
        self.feature_flags.require_enabled("run_runtime_enabled")
        self.feature_flags.require_enabled("approval_lane_enabled")
        run = await self.backend.submit_approval(run_id, approval)
        if self.feature_flags.contract_log_enabled:
            self._append_state_event(
                run_id=run.run_id,
                turn_id=run.turn_id,
                status=run.status,
                event_id=self.id_factory.new_id("run-event"),
                metadata={
                    "source": "runtime_approval",
                    "approval_id": approval.approval_id,
                    "approval_decision": approval.decision,
                },
            )
        return run

    def _append_run_record(
        self,
        req: RunRequest,
        run_id: str,
        status: AsyncTaskState | str,
        backend_run_id: str | None,
    ) -> None:
        self._contract_log().append(
            "run",
            {
                "run_id": run_id,
                "backend_run_id": backend_run_id,
                "turn_id": req.turn.turn_id,
                "solution_id": req.solution.solution_id,
                "tenant_id": req.tenant_id,
                "workspace_id": req.workspace_id,
                "session_id": req.session_id,
                "status": _status_value(status),
                "occurred_at": self.clock.now(),
                "raw_payload_ref": _raw_payload_ref(req),
                "content_sha256": _sha256_or_none(req.turn.content),
                "metadata": {"runtime": "default"},
            },
        )

    def _append_state_event(
        self,
        *,
        run_id: str,
        turn_id: str,
        status: AsyncTaskState | str,
        event_id: str,
        metadata: dict[str, object],
    ) -> None:
        self._contract_log().append(
            "run_event",
            {
                "event_id": event_id,
                "run_id": run_id,
                "turn_id": turn_id,
                "event_type": RunEventType.STATE_CHANGED.value,
                "status": _status_value(status),
                "occurred_at": self.clock.now(),
                "metadata": metadata,
            },
        )

    def _contract_log(self) -> ContractLogStore:
        if self.contract_log_store is None:
            raise RunRuntimeStateError("contract_log_enabled requires contract_log_store")
        return self.contract_log_store

    def _apply_output_boundary(self, event: RunEvent) -> RunEvent | None:
        visible_text = _event_visible_text(event)
        if visible_text is None:
            return event

        decision = self.output_boundary.apply(
            visibility_target="ordinary_user",
            text=visible_text,
            event_metadata=event.metadata,
        )
        policy_metadata = {
            "action": _boundary_action_value(decision.action),
            "reason": getattr(decision, "reason", None),
            "audit": dict(decision.audit_metadata),
        }

        if _boundary_action_value(decision.action) == BoundaryAction.BLOCK.value:
            return replace(
                event,
                payload=_without_visible_text(event.payload),
                metadata={**_without_visible_text(event.metadata), "output_boundary": policy_metadata},
            )

        if _boundary_action_value(decision.action) == BoundaryAction.REWRITE.value:
            return replace(
                event,
                payload=_replace_visible_text(event.payload, decision.visible_text),
                metadata={**_without_visible_text(event.metadata), "output_boundary": policy_metadata},
            )

        return replace(
            event,
            payload=dict(event.payload),
            metadata={**event.metadata, "output_boundary": policy_metadata},
        )


class _SystemRuntimeClock:
    def now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class _SequentialIdFactory:
    def __init__(self) -> None:
        self._next_by_prefix: dict[str, int] = {}

    def new_id(self, prefix: str) -> str:
        next_value = self._next_by_prefix.get(prefix, 1)
        self._next_by_prefix[prefix] = next_value + 1
        return f"{prefix}-{next_value:06d}"


def _raw_payload_ref(req: RunRequest) -> str | None:
    value = req.turn.metadata.get("raw_payload_ref")
    return str(value) if value is not None else None


def _sha256_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _status_value(status: AsyncTaskState | str) -> str:
    if isinstance(status, AsyncTaskState):
        return status.value
    return str(status)


_VISIBLE_TEXT_KEYS = ("message_delta", "visible_text", "text", "content", "delta")


def _event_visible_text(event: RunEvent) -> str | None:
    for mapping in (event.payload, event.metadata):
        for key in _VISIBLE_TEXT_KEYS:
            value = mapping.get(key)
            if isinstance(value, str):
                return value
    return None


def _without_visible_text(mapping: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in mapping.items() if key not in _VISIBLE_TEXT_KEYS}


def _replace_visible_text(mapping: Mapping[str, object], value: str | None) -> dict[str, object]:
    updated = dict(mapping)
    for key in _VISIBLE_TEXT_KEYS:
        if key in updated:
            updated[key] = value
            return updated
    updated["message_delta"] = value
    return updated


def _boundary_action_value(action: object) -> str:
    if isinstance(action, BoundaryAction):
        return action.value
    return str(action)


__all__ = [
    "DefaultRunRuntime",
    "RunRuntimeStateError",
]
