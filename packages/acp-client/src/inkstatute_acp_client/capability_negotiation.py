"""ACP initialize → AdapterCapabilitySet mapping with explicit rejection.

Maps ACP ``initialize`` response capabilities to the platform's
:class:`AdapterCapabilitySet` and enforces that required capabilities
are present — never silently degrades.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platform_contract.agent_adapter import AdapterCapabilitySet

JsonObject = dict[str, Any]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RequiredCapabilities:
    """Capabilities the caller requires from the ACP agent."""

    streaming: bool = True
    elicitation: bool = False
    permissions: bool = False
    artifacts: bool = False
    citations: bool = False


@dataclass(frozen=True, slots=True)
class CapabilityNegotiationResult:
    """Outcome of a successful capability negotiation."""

    protocol_version: int
    agent_name: str
    agent_version: str
    capabilities: AdapterCapabilitySet
    raw_capabilities: dict


class CapabilityMismatchError(Exception):
    """Raised when the ACP agent lacks a required capability.

    Never silently degrades — if a required capability is missing, this
    error is raised with a descriptive message listing all missing items.
    """

    def __init__(self, missing: list[str], agent_name: str, details: str) -> None:
        self.missing = missing
        self.agent_name = agent_name
        self.details = details
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        missing_str = ", ".join(self.missing) if self.missing else "(none)"
        return (
            f"Capability mismatch with agent '{self.agent_name}': "
            f"missing [{missing_str}]. {self.details}"
        )


# ---------------------------------------------------------------------------
# Negotiation logic
# ---------------------------------------------------------------------------

# Mapping from ACP capability key → AdapterCapabilitySet field(s)
_ACP_CAP_TO_ADAPTER: dict[str, list[str]] = {
    "streaming": ["stream_event_support"],
    "elicitation": ["approval_support", "live_update_support"],
    "permissions": ["cancel_support"],
    "artifacts": ["artifact_return_support"],
    "citations": ["trace_support"],
}


def negotiate(
    initialize_response: dict,
    required: RequiredCapabilities,
) -> CapabilityNegotiationResult:
    """Negotiate capabilities from an ACP ``initialize`` response.

    Parameters
    ----------
    initialize_response
        The ``result`` field of the JSON-RPC ``initialize`` response.
    required
        The capabilities the caller requires.

    Returns
    -------
    CapabilityNegotiationResult
        The negotiated capabilities if all required caps are present.

    Raises
    ------
    CapabilityMismatchError
        If the protocol version is not 1, or if any required capability
        is missing from the ACP response.  Never silently degrades.
    """
    missing: list[str] = []

    # 1. Protocol version check — must be exactly 1
    protocol_version = initialize_response.get("protocolVersion")
    if protocol_version != 1:
        missing.append("protocol_version")
        agent_info = initialize_response.get("agentInfo", {})
        agent_name = agent_info.get("name", "unknown") if isinstance(agent_info, dict) else "unknown"
        raise CapabilityMismatchError(
            missing=missing,
            agent_name=agent_name,
            details=(
                f"Expected protocolVersion 1 (ACP v1 lock), "
                f"got {protocol_version!r}. ACP v2 is draft with breaking "
                f"changes — not supported."
            ),
        )

    # 2. Extract agent info
    agent_info = initialize_response.get("agentInfo", {})
    if not isinstance(agent_info, dict):
        agent_info = {}
    agent_name = agent_info.get("name", "unknown")
    agent_version = agent_info.get("version", "unknown")

    # 3. Extract capabilities dict
    raw_capabilities = initialize_response.get("capabilities", {})
    if not isinstance(raw_capabilities, dict):
        raw_capabilities = {}

    # 4. Map ACP capabilities → AdapterCapabilitySet
    adapter_kwargs: dict[str, Any] = {}
    for acp_key, adapter_fields in _ACP_CAP_TO_ADAPTER.items():
        value = bool(raw_capabilities.get(acp_key, False))
        for field_name in adapter_fields:
            adapter_kwargs[field_name] = value

    capabilities = AdapterCapabilitySet(**adapter_kwargs)

    # 5. Check required capabilities — collect ALL missing before raising
    required_checks: list[tuple[str, bool, bool]] = [
        ("streaming", required.streaming, bool(raw_capabilities.get("streaming", False))),
        ("elicitation", required.elicitation, bool(raw_capabilities.get("elicitation", False))),
        ("permissions", required.permissions, bool(raw_capabilities.get("permissions", False))),
        ("artifacts", required.artifacts, bool(raw_capabilities.get("artifacts", False))),
        ("citations", required.citations, bool(raw_capabilities.get("citations", False))),
    ]

    for cap_name, is_required, is_present in required_checks:
        if is_required and not is_present:
            missing.append(cap_name)

    if missing:
        raise CapabilityMismatchError(
            missing=missing,
            agent_name=agent_name,
            details=(
                f"Agent '{agent_name}' does not provide the following required "
                f"capabilities: {', '.join(missing)}. "
                f"Explicit rejection — no silent degradation."
            ),
        )

    # 6. Return result
    return CapabilityNegotiationResult(
        protocol_version=protocol_version,
        agent_name=agent_name,
        agent_version=agent_version,
        capabilities=capabilities,
        raw_capabilities=dict(raw_capabilities),
    )


def build_required_capabilities(
    streaming: bool = True,
    elicitation: bool = False,
    permissions: bool = False,
    artifacts: bool = False,
    citations: bool = False,
) -> RequiredCapabilities:
    """Convenience constructor for :class:`RequiredCapabilities`."""
    return RequiredCapabilities(
        streaming=streaming,
        elicitation=elicitation,
        permissions=permissions,
        artifacts=artifacts,
        citations=citations,
    )


__all__ = [
    "CapabilityMismatchError",
    "CapabilityNegotiationResult",
    "RequiredCapabilities",
    "build_required_capabilities",
    "negotiate",
]
