"""Non-mutating Hermes capability probe."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

from platform_contract.agent_adapter import AdapterCapabilitySet

from .config import HermesBackendConfig
from .manifest import hermes_oneshot_capabilities

SAFE_PROBE_PATHS = ("/health", "/v1/capabilities", "/v1/models")


class HermesProbeTransport(Protocol):
    """Host-provided transport for safe read-only Hermes probe endpoints."""

    def get_json(self, path: str) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class HermesProbeIssue:
    code: str
    endpoint: str
    message: str


@dataclass(frozen=True, slots=True)
class HermesProbeReport:
    ok: bool
    capabilities: AdapterCapabilitySet
    models: list[str] = field(default_factory=list)
    health: Mapping[str, object] = field(default_factory=dict)
    issues: list[HermesProbeIssue] = field(default_factory=list)
    fallback_reason: str | None = None


class HermesCapabilityProbe:
    """Probe Hermes capabilities without touching run/session state."""

    def __init__(self, transport: HermesProbeTransport, config: HermesBackendConfig | None = None) -> None:
        self.transport = transport
        self.config = config or HermesBackendConfig()

    def probe(self) -> HermesProbeReport:
        responses: dict[str, Mapping[str, object]] = {}
        issues: list[HermesProbeIssue] = []
        for path in SAFE_PROBE_PATHS:
            try:
                responses[path] = self.transport.get_json(path)
            except Exception:
                issues.append(
                    HermesProbeIssue(
                        code="probe_endpoint_unavailable",
                        endpoint=path,
                        message="safe probe endpoint unavailable",
                    )
                )
                return HermesProbeReport(
                    ok=False,
                    capabilities=hermes_oneshot_capabilities(),
                    health=responses.get("/health", {}),
                    issues=issues,
                    fallback_reason="probe_endpoint_unavailable",
                )

        capability_payload = _capability_payload(responses.get("/v1/capabilities", {}))
        capabilities = _capabilities_from_payload(capability_payload)
        models = _models_from_payload(responses.get("/v1/models", {}))
        return HermesProbeReport(
            ok=not issues,
            capabilities=capabilities,
            models=models,
            health=responses.get("/health", {}),
            issues=issues,
            fallback_reason=None if "runs_api" in capabilities.run_invocation_modes else "runs_api_not_advertised",
        )


def _capability_payload(payload: Mapping[str, object]) -> Mapping[str, object]:
    nested = payload.get("capabilities")
    if isinstance(nested, Mapping):
        return nested
    return payload


def _capabilities_from_payload(payload: Mapping[str, object]) -> AdapterCapabilitySet:
    one_shot = hermes_oneshot_capabilities()
    modes = _string_list(payload.get("run_invocation_modes")) or list(one_shot.run_invocation_modes)
    if _bool(payload.get("runs_api_support"), default=False) and "runs_api" not in modes:
        modes.append("runs_api")
    if "oneshot" not in modes:
        modes.insert(0, "oneshot")
    return AdapterCapabilitySet(
        hook_event_support=_string_list(payload.get("hook_event_support")),
        invocation_mode=str(payload.get("invocation_mode") or one_shot.invocation_mode),
        feedback_target_support=str(payload.get("feedback_target_support") or one_shot.feedback_target_support),
        session_read_support=_bool(payload.get("session_read_support"), default=one_shot.session_read_support),
        artifact_return_support=_bool(payload.get("artifact_return_support"), default=one_shot.artifact_return_support),
        trace_support=_bool(payload.get("trace_support"), default=one_shot.trace_support),
        no_channel_io=True,
        run_invocation_modes=modes,
        stream_event_support=_bool(payload.get("stream_event_support"), default=one_shot.stream_event_support),
        cancel_support=_bool(payload.get("cancel_support"), default=one_shot.cancel_support),
        approval_support=_bool(payload.get("approval_support"), default=one_shot.approval_support),
        live_update_support=_bool(payload.get("live_update_support"), default=one_shot.live_update_support),
        parallel_task_support=_bool(payload.get("parallel_task_support"), default=one_shot.parallel_task_support),
        session_memory_support=_bool(payload.get("session_memory_support"), default=one_shot.session_memory_support),
    )


def _models_from_payload(payload: Mapping[str, object]) -> list[str]:
    raw_models = payload.get("models")
    if isinstance(raw_models, list):
        return [str(item) for item in raw_models if isinstance(item, str)]
    if isinstance(raw_models, Mapping):
        return [str(key) for key in raw_models]
    return []


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    if isinstance(value, tuple):
        return [str(item) for item in value if isinstance(item, str)]
    return []


def _bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


__all__ = [
    "HermesCapabilityProbe",
    "HermesProbeIssue",
    "HermesProbeReport",
    "HermesProbeTransport",
    "SAFE_PROBE_PATHS",
]
