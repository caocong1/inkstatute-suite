"""Default-off Hermes /v1/runs client seam."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Protocol

from platform_contract.enums import AsyncTaskState
from platform_runtime import Approval, RunRequest

from .config import HermesBackendConfig

JsonObject = dict[str, object]


class HermesRunsDisabledError(RuntimeError):
    """Raised when the opt-in Hermes runs API lane is used while disabled."""


class HermesRunsTransport(Protocol):
    """Host-provided transport for the opt-in Hermes runs API lane."""

    def post_json(self, path: str, body: Mapping[str, object]) -> Mapping[str, object]: ...

    def get_json(self, path: str) -> Mapping[str, object]: ...

    def iter_json(self, path: str) -> Iterable[Mapping[str, object]]: ...


@dataclass(frozen=True, slots=True)
class HermesStatusMapping:
    status: AsyncTaskState
    metadata: JsonObject = field(default_factory=dict)


class HermesRunsClient:
    """Small opt-in client seam for Hermes /v1/runs fixtures and hosts."""

    def __init__(self, transport: HermesRunsTransport, config: HermesBackendConfig | None = None) -> None:
        self.transport = transport
        self.config = config or HermesBackendConfig()

    def submit_run(self, req: RunRequest) -> Mapping[str, object]:
        self._require_enabled()
        return self.transport.post_json("/v1/runs", _run_request_body(req))

    def get_run(self, run_id: str) -> Mapping[str, object]:
        self._require_enabled()
        return self.transport.get_json(f"/v1/runs/{run_id}")

    def stream_events(self, run_id: str) -> Iterable[Mapping[str, object]]:
        self._require_enabled()
        return self.transport.iter_json(f"/v1/runs/{run_id}/events")

    def cancel_run(self, run_id: str) -> Mapping[str, object]:
        self._require_enabled()
        return self.transport.post_json(f"/v1/runs/{run_id}/cancel", {})

    def submit_approval(self, run_id: str, approval: Approval) -> Mapping[str, object]:
        self._require_enabled()
        return self.transport.post_json(
            f"/v1/runs/{run_id}/approval",
            {
                "approval_id": approval.approval_id,
                "decision": approval.decision,
                "decided_by": approval.decided_by,
                "decided_at": approval.decided_at,
            },
        )

    def _require_enabled(self) -> None:
        if not self.config.api_runs_enabled:
            raise HermesRunsDisabledError("Hermes /v1/runs lane is disabled")


def map_hermes_run_status(value: object) -> HermesStatusMapping:
    """Map Hermes run status into known platform async states only."""

    normalized = str(value or "").strip().lower()
    mapping = {
        "queued": AsyncTaskState.QUEUED,
        "pending": AsyncTaskState.QUEUED,
        "running": AsyncTaskState.RUNNING,
        "in_progress": AsyncTaskState.RUNNING,
        "waiting_for_user": AsyncTaskState.WAITING_FOR_USER,
        "requires_action": AsyncTaskState.WAITING_FOR_USER,
        "succeeded": AsyncTaskState.SUCCEEDED,
        "success": AsyncTaskState.SUCCEEDED,
        "completed": AsyncTaskState.SUCCEEDED,
        "failed": AsyncTaskState.FAILED,
        "error": AsyncTaskState.FAILED,
        "cancelled": AsyncTaskState.CANCELLED,
        "canceled": AsyncTaskState.CANCELLED,
    }
    if normalized in mapping:
        return HermesStatusMapping(mapping[normalized])
    return HermesStatusMapping(
        AsyncTaskState.FAILED,
        {
            "unknown_status": True,
            "status_sha256": hashlib.sha256(str(value).encode("utf-8")).hexdigest(),
        },
    )


def _run_request_body(req: RunRequest) -> JsonObject:
    return {
        "turn_id": req.turn.turn_id,
        "conversation_id": req.turn.conversation_id,
        "solution_id": req.solution.solution_id,
        "tenant_id": req.tenant_id,
        "workspace_id": req.workspace_id,
        "session_id": req.session_id,
        "raw_payload_ref": req.turn.metadata.get("raw_payload_ref"),
        "content_sha256": _sha256(req.turn.content),
        "attachment_refs": [attachment.uri for attachment in req.turn.attachments],
    }


def _sha256(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = [
    "HermesRunsClient",
    "HermesRunsDisabledError",
    "HermesRunsTransport",
    "HermesStatusMapping",
    "map_hermes_run_status",
]
