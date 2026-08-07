"""Signature-only Protocols for the InkStatute platform runtime.

This module deliberately contains no orchestration, network, storage, channel,
backend, or solution materialization behavior. It only defines the Protocol
surfaces and pure data shapes required to type those surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Protocol, TypeAlias

from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_contract.enums import AsyncTaskState
from platform_contract.events import (
    AgentResult,
    AgentTurn,
    FeedbackEvent,
    JsonObject,
    OutputConstraints,
)

from .session_resolver import SessionScope

RunId: TypeAlias = str
ChannelId: TypeAlias = str
BackendId: TypeAlias = str
SolutionId: TypeAlias = str


@dataclass(frozen=True, slots=True)
class RawInbound:
    channel_id: ChannelId
    payload_ref: str
    received_at: str
    idempotency_key: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AckResponse:
    accepted: bool
    status_code: int = 200
    idempotency_key: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class InboundNormalized:
    message: AgentTurn | None = None
    feedback: FeedbackEvent | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChannelCapabilitySet:
    supports_text: bool = True
    supports_files: bool = False
    supports_cards: bool = False
    supports_images: bool = False
    supports_voice: bool = False
    supports_streaming: bool = False
    ack_deadline_ms: int | None = None
    idempotency_strategy: str | None = None
    verify_and_ack_support: bool = False
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    ok: bool
    component_id: str
    checked_at: str
    detail: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    delivery_id: str
    accepted: bool
    delivered_at: str | None = None
    idempotency_key: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChannelDelivery:
    delivery_id: str
    channel_id: ChannelId
    run_id: RunId | None = None
    result: AgentResult | None = None
    content: str | None = None
    artifact_refs: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SolutionBinding:
    solution_id: SolutionId
    version: str | None = None
    backend_id: BackendId | None = None
    config_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RunRequest:
    turn: AgentTurn
    solution: SolutionBinding
    tenant_id: str | None = None
    workspace_id: str | None = None
    bot_instance_id: str | None = None
    session_id: str | None = None
    output_constraints: OutputConstraints | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RunHandle:
    run_id: RunId
    backend_run_id: str | None = None
    status: AsyncTaskState | str = AsyncTaskState.QUEUED
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Run:
    run_id: RunId
    status: AsyncTaskState | str
    turn_id: str
    solution_id: SolutionId
    result: AgentResult | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RunEvent:
    event_id: str
    run_id: RunId
    event_type: str
    occurred_at: str
    seq: int
    payload: JsonObject = field(default_factory=dict)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Approval:
    approval_id: str
    decision: str
    decided_by: str | None = None
    decided_at: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    kind: str
    uri_ref: str
    name: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BootstrapStatus:
    ok: bool
    backend_id: BackendId
    checked_at: str
    issues: list[str] = field(default_factory=list)
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    path: str
    message: str
    severity: str = "error"
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SolutionPackageManifest:
    solution_id: SolutionId
    version: str
    manifest_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Solution:
    solution_id: SolutionId
    version: str
    manifest: SolutionPackageManifest
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BackendSolutionBundle:
    backend_id: BackendId
    solution_id: SolutionId
    bundle_ref: str
    metadata: JsonObject = field(default_factory=dict)


class ChannelAdapter(Protocol):
    def channel_id(self) -> str: ...

    def capabilities(self) -> ChannelCapabilitySet: ...

    async def verify_and_ack(self, raw: RawInbound) -> AckResponse: ...

    async def normalize_inbound(self, raw: RawInbound) -> InboundNormalized: ...

    async def deliver(self, delivery: ChannelDelivery) -> DeliveryResult: ...

    async def health(self) -> ComponentHealth: ...


class BackendAdapter(Protocol):
    def backend_id(self) -> str: ...

    def capabilities(self) -> AdapterCapabilitySet: ...

    async def bootstrap_check(self) -> BootstrapStatus: ...

    async def submit_run(self, req: RunRequest) -> RunHandle: ...

    async def get_run(self, run_id: str) -> Run: ...

    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]: ...

    async def cancel_run(self, run_id: str) -> Run: ...

    async def submit_approval(self, run_id: str, approval: Approval) -> Run: ...

    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]: ...


class SolutionLoader(Protocol):
    def validate(self, manifest: SolutionPackageManifest) -> list[Issue]: ...

    def load(self, manifest: SolutionPackageManifest) -> Solution: ...

    def materialize_for(
        self,
        solution: Solution,
        backend_id: str,
        output_dir: Path | None = None,
    ) -> tuple[list[Issue], BackendSolutionBundle | None]: ...


class RunRuntime(Protocol):
    async def create_run(self, req: RunRequest) -> Run: ...

    async def resume_interrupt(
        self,
        *,
        interrupt_id: str,
        scope: SessionScope,
        req: RunRequest,
        idempotency_key: str | None = None,
    ) -> Run: ...

    async def poll(self, run_id: str) -> Run: ...

    async def stream(self, run_id: str) -> AsyncIterator[RunEvent]: ...

    async def cancel(self, run_id: str) -> Run: ...

    async def approve(self, run_id: str, approval: Approval) -> Run: ...


__all__ = [
    "AckResponse",
    "AdapterCapabilitySet",
    "Approval",
    "ArtifactRecord",
    "BackendAdapter",
    "BackendId",
    "BackendSolutionBundle",
    "BootstrapStatus",
    "ChannelAdapter",
    "ChannelCapabilitySet",
    "ChannelDelivery",
    "ChannelId",
    "ComponentHealth",
    "DeliveryResult",
    "InboundNormalized",
    "Issue",
    "RawInbound",
    "Run",
    "RunEvent",
    "RunHandle",
    "RunId",
    "RunRequest",
    "RunRuntime",
    "Solution",
    "SolutionBinding",
    "SolutionId",
    "SolutionLoader",
    "SolutionPackageManifest",
]
