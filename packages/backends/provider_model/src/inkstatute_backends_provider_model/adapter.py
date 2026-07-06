"""Concrete provider_model BackendAdapter prototype implementation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, replace
from typing import Any, AsyncIterator, Iterator, Protocol

from platform_contract.agent_adapter import AdapterCapabilitySet
from platform_contract.enums import AgentResultStatus, AsyncTaskState
from platform_contract.events import AgentResult, ErrorInfo, JsonObject, ReplyType
from platform_runtime import (
    Approval,
    ArtifactRecord,
    BootstrapStatus,
    Run,
    RunHandle,
    RunRequest,
)

from .config import ProviderModelBackendConfig
from .manifest import build_provider_model_manifest


class ProviderModelRunner(Protocol):
    """Injected runner for the direct LLM invocation lane (implemented in Plan 40-02)."""

    async def invoke(self, req: RunRequest) -> "ProviderModelExecResult": ...


class StreamingProviderModelRunner(Protocol):
    """Injected runner for the streaming SSE delta lane (implemented in Plan 46-02)."""

    async def stream(self, req: RunRequest) -> AsyncIterator["ProviderModelStreamDelta"]: ...


@dataclass(frozen=True, slots=True)
class ProviderModelExecResult:
    """Reference-first result returned by a provider_model runner."""

    status: AsyncTaskState | str = AsyncTaskState.SUCCEEDED
    result: AgentResult | None = None
    completion_id: str | None = None
    artifact_refs: list[str] = field(default_factory=list)
    raw_payload_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderModelStreamDelta:
    """A single SSE delta chunk yielded by a streaming provider_model runner."""

    content: str
    finish_reason: str | None = None


class ProviderModelBackendAdapter:
    """Provider_model prototype adapter with truthful reduced capabilities.

    production_ready: false, no_channel_io: true.
    submit_run delegates to an injectable ProviderModelRunner (wired in Plan 40-02).
    """

    def __init__(
        self,
        *,
        config: ProviderModelBackendConfig | None = None,
        runner: ProviderModelRunner | None = None,
        clock: Any | None = None,
    ) -> None:
        self.config = config or ProviderModelBackendConfig()
        self._runner = runner
        self._clock = clock or _SystemClock()
        self._next_run = 1
        self._runs: dict[str, Run] = {}
        self._artifacts: dict[str, list[ArtifactRecord]] = {}

    def backend_id(self) -> str:
        return self.config.backend_id

    def capabilities(self) -> AdapterCapabilitySet:
        return build_provider_model_manifest(self.config).capabilities

    async def bootstrap_check(self) -> BootstrapStatus:
        runner_ready = self._runner is not None
        return BootstrapStatus(
            ok=runner_ready,
            backend_id=self.config.backend_id,
            checked_at=self._clock.now(),
            issues=[] if runner_ready else ["provider_model_runner_not_configured"],
            metadata={
                "invocation_mode": "direct_llm",
                "no_channel_io": True,
                "runner_injected": self._runner is not None,
                "model_name": self.config.model_name,
            },
        )

    async def submit_run(self, req: RunRequest) -> RunHandle:
        if self._runner is None:
            raise RuntimeError("provider_model runner not configured")

        result = await self._runner.invoke(req)
        status = _coerce_task_state(result.status)
        run_id = self._new_run_id()
        backend_run_id = f"{self.config.backend_id}:{run_id}"
        raw_payload_ref = result.raw_payload_ref or _raw_payload_ref(req)
        run_metadata = {
            "backend_id": self.config.backend_id,
            "backend_run_id": backend_run_id,
            "invocation_mode": "direct_llm",
            "raw_payload_ref": raw_payload_ref,
            "request_content_sha256": _content_sha256(req.turn.content),
            "provider_completion_id": result.completion_id,
            "artifact_refs": list(result.artifact_refs),
            "runner_metadata": _sanitize_metadata(result.metadata),
        }
        run = Run(
            run_id=run_id,
            status=status,
            turn_id=req.turn.turn_id,
            solution_id=req.solution.solution_id,
            result=_sanitize_result(result.result) or _default_result(req, status),
            metadata=run_metadata,
        )
        self._runs[run_id] = run
        self._artifacts[run_id] = []
        return RunHandle(
            run_id=run_id,
            backend_run_id=backend_run_id,
            status=status,
            metadata={
                "backend_id": self.config.backend_id,
                "invocation_mode": "direct_llm",
                "raw_payload_ref": raw_payload_ref,
            },
        )

    async def get_run(self, run_id: str) -> Run:
        return self._require_run(run_id)

    async def stream_events(self, run_id: str) -> AsyncIterator[Any]:
        self._require_run(run_id)
        if False:
            yield

    async def cancel_run(self, run_id: str) -> Run:
        run = self._require_run(run_id)
        updated = replace(run, metadata={**run.metadata, "reason": "unsupported_by_provider_model_prototype"})
        self._runs[run_id] = updated
        return updated

    async def submit_approval(self, run_id: str, approval: Approval) -> Run:
        run = self._require_run(run_id)
        updated = replace(
            run,
            metadata={
                **run.metadata,
                "reason": "approval_unsupported_by_provider_model_prototype",
                "approval_id": approval.approval_id,
                "approval_decision_recorded": False,
            },
        )
        self._runs[run_id] = updated
        return updated

    async def collect_artifacts(self, run_id: str) -> list[ArtifactRecord]:
        return list(self._artifacts.get(run_id, ()))

    def _new_run_id(self) -> str:
        value = self._next_run
        self._next_run += 1
        return f"provider-model-run-{value:03d}"

    def _require_run(self, run_id: str) -> Run:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise KeyError(f"unknown provider_model run: {run_id}") from exc


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
        metadata={"source": "provider_model_prototype"},
    )


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


_URL_RE = re.compile(r"https?://\S+")
_TOKEN_RE = re.compile(r"token=\S+")


def _sanitize_text(text: str | None) -> str | None:
    """Strip URLs and token-like patterns from a text string."""

    if text is None:
        return None
    sanitized = _URL_RE.sub("[url_redacted]", text)
    sanitized = _TOKEN_RE.sub("token=[redacted]", sanitized)
    return sanitized


def _sanitize_error_info(error: ErrorInfo | None) -> ErrorInfo | None:
    """Return a new :class:`ErrorInfo` with sanitized message and details."""

    if error is None:
        return None
    return ErrorInfo(
        category=error.category,
        code=error.code,
        message=_sanitize_text(error.message),
        stage=error.stage,
        retryable=error.retryable,
        details=_sanitize_metadata(error.details) if error.details else {},
        metadata=_sanitize_metadata(error.metadata) if error.metadata else {},
    )


def _sanitize_result(result: AgentResult | None) -> AgentResult | None:
    """Return a new :class:`AgentResult` with a sanitized :class:`ErrorInfo`."""

    if result is None:
        return None
    sanitized_error = _sanitize_error_info(result.error)
    if sanitized_error is result.error:
        return result
    return replace(result, error=sanitized_error)


__all__ = ["ProviderModelBackendAdapter", "ProviderModelExecResult", "ProviderModelRunner"]
