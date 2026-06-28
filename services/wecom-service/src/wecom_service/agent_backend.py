"""Runtime selector for backend-neutral agent adapter manifests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from platform_contract.agent_adapter import AgentBackendManifest


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

    raise NotImplementedError


__all__ = [
    "AgentBackendSelection",
    "AgentBackendSelectionError",
    "select_agent_backend",
]
