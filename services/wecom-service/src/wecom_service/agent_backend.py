"""Runtime selector for backend-neutral agent adapter manifests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from platform_contract.agent_adapter import (
    AgentBackendManifest,
    AgentBackendMode,
    validate_agent_backend_manifest,
)


class AgentBackendSelectionError(ValueError):
    """Raised when no safe agent backend can be selected."""


@dataclass(frozen=True, slots=True)
class AgentBackendSelection:
    mode: str
    manifest: AgentBackendManifest
    live_acceptance_allowed: bool
    contract_compatible: bool = True


def select_agent_backend(
    config: Mapping[str, Any],
    manifests: Sequence[AgentBackendManifest],
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

    if manifest.capabilities.no_channel_io is not True:
        raise AgentBackendSelectionError(
            f"adapter {manifest.adapter_name!r} cannot be selected because no_channel_io is not true"
        )

    production_ready = bool(manifest.metadata.get("production_ready", requested_mode == AgentBackendMode.HERMES.value))
    live_acceptance_allowed = production_ready and requested_mode == AgentBackendMode.HERMES.value
    if requested_mode != AgentBackendMode.HERMES.value and manifest.metadata.get("production_ready") is True:
        live_acceptance_allowed = True

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
    manifests: Sequence[AgentBackendManifest],
) -> AgentBackendManifest | None:
    for manifest in manifests:
        manifest_mode = manifest.mode.value if isinstance(manifest.mode, AgentBackendMode) else str(manifest.mode)
        if manifest_mode == mode:
            return manifest
    return None


__all__ = [
    "AgentBackendSelection",
    "AgentBackendSelectionError",
    "select_agent_backend",
]
