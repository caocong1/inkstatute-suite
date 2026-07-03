"""Runtime selector for backend-neutral agent adapter manifests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from platform_contract.agent_adapter import AgentBackendManifest, AgentBackendMode, validate_agent_backend_manifest


class AgentBackendSelectionError(ValueError):
    """Raised when no safe agent backend can be selected."""


@dataclass(frozen=True, slots=True)
class AgentBackendSelection:
    mode: str
    manifest: AgentBackendManifest | Mapping[str, Any]
    live_acceptance_allowed: bool
    contract_compatible: bool = True


def select_agent_backend(
    config: Mapping[str, Any],
    manifests: Sequence[AgentBackendManifest | Mapping[str, Any]],
) -> AgentBackendSelection:
    """Select an agent backend manifest for the WeCom service."""

    requested_mode = _requested_mode(config)
    if requested_mode not in {item.value for item in AgentBackendMode}:
        raise AgentBackendSelectionError(f"unsupported agent_backend.mode {requested_mode!r}")

    manifest = _find_manifest(requested_mode, manifests)
    if manifest is None:
        raise AgentBackendSelectionError(f"no adapter manifest found for mode {requested_mode!r}")

    issues = validate_agent_backend_manifest(manifest)
    if issues:
        codes = ", ".join(str(issue.get("code")) for issue in issues)
        raise AgentBackendSelectionError(f"invalid adapter manifest for {requested_mode}: {codes}")

    if _capabilities_no_channel_io(manifest) is not True:
        raise AgentBackendSelectionError(
            f"adapter {_adapter_name(manifest)!r} cannot be selected because no_channel_io is not true"
        )

    metadata = _metadata(manifest)
    production_ready = bool(metadata.get("production_ready", requested_mode == AgentBackendMode.HERMES.value))
    live_acceptance_allowed = production_ready and requested_mode == AgentBackendMode.HERMES.value

    return AgentBackendSelection(
        mode=requested_mode,
        manifest=manifest,
        live_acceptance_allowed=live_acceptance_allowed,
        contract_compatible=True,
    )


def _requested_mode(config: Mapping[str, Any]) -> str:
    agent_backend = config.get("agent_backend")
    if isinstance(agent_backend, Mapping):
        mode = agent_backend.get("mode")
    else:
        mode = config.get("agent_backend.mode")
    if mode is None:
        raise AgentBackendSelectionError("missing agent_backend.mode")
    return str(mode)


def _find_manifest(
    mode: str,
    manifests: Sequence[AgentBackendManifest | Mapping[str, Any]],
) -> AgentBackendManifest | Mapping[str, Any] | None:
    for manifest in manifests:
        raw_mode = manifest.get("mode") if isinstance(manifest, Mapping) else manifest.mode
        manifest_mode = raw_mode.value if isinstance(raw_mode, AgentBackendMode) else str(raw_mode)
        if manifest_mode == mode:
            return manifest
    return None


def _capabilities_no_channel_io(manifest: AgentBackendManifest | Mapping[str, Any]) -> bool | None:
    capabilities = manifest.get("capabilities") if isinstance(manifest, Mapping) else manifest.capabilities
    if isinstance(capabilities, Mapping):
        value = capabilities.get("no_channel_io")
    else:
        value = getattr(capabilities, "no_channel_io", None)
    return value if isinstance(value, bool) else None


def _metadata(manifest: AgentBackendManifest | Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = manifest.get("metadata") if isinstance(manifest, Mapping) else manifest.metadata
    return metadata if isinstance(metadata, Mapping) else {}


def _adapter_name(manifest: AgentBackendManifest | Mapping[str, Any]) -> str | None:
    value = manifest.get("adapter_name") if isinstance(manifest, Mapping) else manifest.adapter_name
    return str(value) if value is not None else None


__all__ = [
    "AgentBackendSelection",
    "AgentBackendSelectionError",
    "select_agent_backend",
]
