"""Concrete Hermes BackendAdapter implementation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from typing import Any, AsyncIterator, Protocol

from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_contract.enums import AgentResultStatus, AsyncTaskState
from platform_contract.events import AgentResult, JsonObject, ReplyType
from platform_runtime import (
    Approval,
    ArtifactRecord,
    BootstrapStatus,
    Run,
    RunEvent,
    RunHandle,
    RunRequest,
)

from .config import HermesBackendConfig
from .manifest import build_hermes_oneshot_manifest


class HermesOneShotRunner(Protocol):
    """Injected runner for the Hermes one-shot invocation lane."""

    async def invoke(self, req: RunRequest) -> "HermesOneShotResult": ...


@dataclass(frozen=True, slots=True)
class HermesOneShotResult:
    """Reference-first result returned by a Hermes one-shot runner."""

    status: AsyncTaskState | str = AsyncTaskState.SUCCEEDED
    result: AgentResult | None = None
    artifact_refs: list[str] = field(default_factory=list)
    trace_refs: list[str] = field(default_factory=list)
    raw_payload_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)


class HermesBackendAdapter:
    """One-shot Hermes adapter with truthful reduced capabilities."""

    def __init__(
        self,
        *,
        config: HermesBackendConfig | None = None,
        runner: HermesOneShotRunner | None = None,
        clock: Any | None = None,
    ) -> None:
        self.config = config or HermesBackendConfig()
        self._runner = runner
        self._clock = clock or _SystemClock()
        self._next_run = 1
        self._runs: dict[str, Run] = {}
        self._artifacts: dict[str, list[ArtifactRecord]] = {}
        self._runner_calls = 0

    @property
    def runner_calls(self) -> int:
        return self._runner_calls

    def backend_id(self) -> str:
        return self.config.backend_id

    def capabilities(self) -> AdapterCapabilitySet:
        return build_hermes_oneshot_manifest(self.config).capabilities

    async def bootstrap_check(self) -> BootstrapStatus:
        runner_ready = self._runner is not None or bool(self.config.oneshot_command)
        return BootstrapStatus(
            ok=runner_ready,
            backend_id=self.config.backend_id,
            checked_at=self._clock.now(),
            issues=[] if runner_ready else ["oneshot_runner_not_configured"],
            metadata={
                "invocation_mode": "oneshot",
                "no_channel_io": True,
                "runner_injected": self._runner is not None,
                "oneshot_command_configured": bool(self.config.oneshot_command),
            },
        )

    async def submit_run(self, req: RunRequest) -> RunHandle:
        if self._runner is None:
            raise RuntimeError("Hermes one-shot runner is not configured")

        self._runner_calls += 1
        result = await self._runner.invoke(req)
        status = _coerce_task_state(result.status)
        run_id = self._new_run_id()
        backend_run_id = f"{self.config.backend_id}:{run_id}"
        raw_payload_ref = result.raw_payload_ref or _raw_payload_ref(req)
        run_metadata = {
            "backend_id": self.config.backend_id,
            "backend_run_id": backend_run_id,
            "profile_name": self.config.profile_name,
            "invocation_mode": "oneshot",
            "raw_payload_ref": raw_payload_ref,
            "request_content_sha256": _content_sha256(req.turn.content),
            "artifact_refs": list(result.artifact_refs),
            "trace_refs": list(result.trace_refs),
            "runner_metadata": _sanitize_metadata(result.metadata),
        }
        run = Run(
            run_id=run_id,
            status=status,
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            result=result.result or _default_result(req, status),
            metadata=run_metadata,
        )
        self._runs[run_id] = run
        self._artifacts[run_id] = _artifact_records(run_id, result.artifact_refs, result.metadata)
        return RunHandle(
            run_id=run_id,
            backend_run_id=backend_run_id,
            status=status,
            metadata={
                "backend_id": self.config.backend_id,
                "invocation_mode": "oneshot",
                "raw_payload_ref": raw_payload_ref,
            },
        )

    async def get_run(self, run_id: str) -> Run:
        return self._require_run(run_id)

    async def stream_events(self, run_id: str) -> AsyncIterator[RunEvent]:
        self._require_run(run_id)
        if False:
            yield

    async def cancel_run(self, run_id: str) -> Run:
        run = self._require_run(run_id)
        updated = replace(run, metadata={**run.metadata, "reason": "unsupported_by_oneshot"})
        self._runs[run_id] = updated
        return updated

    async def submit_approval(self, run_id: str, approval: Approval) -> Run:
        run = self._require_run(run_id)
        reason = "approval_unsupported_by_oneshot"
        if _is_high_risk_legal_approval(approval):
            reason = "high_risk_legal_approval_requires_human_review"
        updated = replace(
            run,
            metadata={
                **run.metadata,
                "reason": reason,
                "approval_id": approval.approval_id,
                "approval_decision_recorded": False,
            },
        )
        self._runs[run_id] = updated
        return updated

    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        self._require_run(run_id)
        return list(self._artifacts.get(run_id, ()))

    def _new_run_id(self) -> str:
        value = self._next_run
        self._next_run += 1
        return f"hermes-run-{value:03d}"

    def _require_run(self, run_id: str) -> Run:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise KeyError(f"unknown Hermes run: {run_id}") from exc


class _SystemClock:
    def now(self) -> str:
        return "1970-01-01T00:00:00Z"


def _raw_payload_ref(req: RunRequest) -> str | None:
    value = req.turn.metadata.get("raw_payload_ref")
    return str(value) if value else None


def _content_sha256(content: str | None) -> str | None:
    if content is None:
        return None
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _coerce_task_state(status: AsyncTaskState | str) -> AsyncTaskState:
    if isinstance(status, AsyncTaskState):
        return status
    status_value = str(status)
    if status_value == AgentResultStatus.SUCCESS.value:
        return AsyncTaskState.SUCCEEDED
    if status_value == AgentResultStatus.FAILED.value:
        return AsyncTaskState.FAILED
    return AsyncTaskState(status_value)


def _default_result(req: RunRequest, status: AsyncTaskState) -> AgentResult:
    result_status = AgentResultStatus.SUCCESS if status == AsyncTaskState.SUCCEEDED else AgentResultStatus.FAILED
    return AgentResult(
        result_id=f"result-{req.turn.turn_id}",
        turn_id=req.turn.turn_id,
        status=result_status,
        reply_type=ReplyType.TEXT,
        content=None,
        metadata={"source": "hermes_oneshot"},
    )


def _artifact_records(run_id: str, refs: list[str], metadata: JsonObject) -> list[ArtifactRecord]:
    kind = str(metadata.get("artifact_kind", "backend_ref"))
    return [
        ArtifactRecord(
            artifact_id=f"{run_id}-artifact-{index:03d}",
            kind=kind,
            uri_ref=ref,
            name=f"{run_id}-artifact-{index:03d}",
            metadata={"source": "hermes_oneshot"},
        )
        for index, ref in enumerate(refs, start=1)
    ]


def _sanitize_metadata(metadata: JsonObject) -> JsonObject:
    sanitized: JsonObject = {}
    for key, value in metadata.items():
        lowered = key.lower()
        if lowered in {"raw_payload", "content", "transcript", "prompt", "response_body"}:
            continue
        if "secret" in lowered or "token" in lowered or "profile_path" in lowered:
            continue
        sanitized[key] = _sanitize_value(value)
    return sanitized


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _sanitize_metadata(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _is_high_risk_legal_approval(approval: Approval) -> bool:
    text = " ".join(
        str(value).lower()
        for value in (
            approval.decision,
            approval.metadata.get("risk_level"),
            approval.metadata.get("approval_scope"),
            approval.metadata.get("action"),
        )
        if value is not None
    )
    return any(
        marker in text
        for marker in (
            "high",
            "legal_conclusion",
            "legal conclusion",
            "skill_modification",
            "auto_accept_legal_advice",
        )
    )


__all__ = ["HermesBackendAdapter", "HermesOneShotResult", "HermesOneShotRunner"]

