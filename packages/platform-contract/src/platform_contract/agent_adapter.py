"""Backend-neutral agent adapter manifest bindings."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

JsonObject = dict[str, Any]


class AgentBackendMode(StrEnum):
    HERMES = "hermes"
    CODEX = "codex"
    PROVIDER_MODEL = "provider_model"


@dataclass(frozen=True, slots=True)
class AdapterCapabilitySet:
    hook_event_support: list[str] = field(default_factory=list)
    invocation_mode: str | None = None
    feedback_target_support: str | None = None
    session_read_support: bool = False
    artifact_return_support: bool = False
    trace_support: bool = False
    no_channel_io: bool | None = None
    run_invocation_modes: list[str] = field(default_factory=list)
    stream_event_support: bool = False
    cancel_support: bool = False
    approval_support: bool = False
    live_update_support: bool = False
    parallel_task_support: bool = False
    session_memory_support: bool = False
    supports_vision: bool = False


@dataclass(frozen=True, slots=True)
class AgentBackendManifest:
    adapter_name: str
    adapter_version: str
    mode: AgentBackendMode | str
    backend_version: str
    capabilities: AdapterCapabilitySet
    profile_name: str | None = None
    bundle_id: str | None = None
    metadata: JsonObject = field(default_factory=dict)


def validate_agent_backend_manifest(manifest: AgentBackendManifest | JsonObject) -> list[JsonObject]:
    """Return structured validation issues for an adapter manifest."""

    issues: list[JsonObject] = []
    adapter_name = _field(manifest, "adapter_name")
    adapter_version = _field(manifest, "adapter_version")
    mode = _field(manifest, "mode")
    backend_version = _field(manifest, "backend_version")
    capabilities = _field(manifest, "capabilities")

    if _blank(adapter_name):
        issues.append(_issue("missing_adapter_name", "adapter_name", "adapter manifest requires adapter_name"))

    if _blank(adapter_version):
        issues.append(_issue("missing_adapter_version", "adapter_version", "adapter manifest requires adapter_version"))

    if _blank(mode):
        issues.append(_issue("missing_mode", "mode", "adapter manifest requires mode"))
    elif _mode_value(mode) not in {item.value for item in AgentBackendMode}:
        issues.append(_issue("unsupported_mode", "mode", f"unsupported adapter mode {_mode_value(mode)!r}"))

    if _blank(backend_version):
        issues.append(
            _issue("missing_backend_version", "backend_version", "adapter manifest requires backend_version")
        )

    if capabilities is None:
        issues.append(_issue("missing_capabilities", "capabilities", "adapter manifest requires capabilities"))
        return issues

    invocation_mode = _field(capabilities, "invocation_mode")
    if _blank(invocation_mode):
        issues.append(
            _issue(
                "missing_invocation_mode",
                "capabilities.invocation_mode",
                "adapter manifest requires invocation_mode",
            )
        )

    no_channel_io = _field(capabilities, "no_channel_io", missing=None)
    if no_channel_io is None:
        issues.append(
            _issue(
                "missing_no_channel_io",
                "capabilities.no_channel_io",
                "adapter manifest requires no_channel_io",
            )
        )
    elif not isinstance(no_channel_io, bool):
        issues.append(
            _issue(
                "invalid_no_channel_io",
                "capabilities.no_channel_io",
                "no_channel_io must be a boolean",
            )
        )

    return issues


def _field(value: Any, name: str, *, missing: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, missing)
    return getattr(value, name, missing)


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _mode_value(value: Any) -> str:
    if isinstance(value, AgentBackendMode):
        return value.value
    return str(value)


def _issue(code: str, path: str, message: str) -> JsonObject:
    return {
        "code": code,
        "path": path,
        "message": message,
    }


__all__ = [
    "AdapterCapabilitySet",
    "AgentBackendManifest",
    "AgentBackendMode",
    "validate_agent_backend_manifest",
]
