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

    raise NotImplementedError


__all__ = [
    "AdapterCapabilitySet",
    "AgentBackendManifest",
    "AgentBackendMode",
    "validate_agent_backend_manifest",
]
