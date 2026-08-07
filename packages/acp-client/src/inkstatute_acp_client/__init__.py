"""InkStatute ACP Backend Client — drives any ACP v1 agent as a backend over stdio."""

from .capability_negotiation import (
    CapabilityMismatchError,
    CapabilityNegotiationResult,
    RequiredCapabilities,
    build_required_capabilities,
    negotiate,
)
from .client import ACPClient, ACPTransport, StdioACPTransport
from .event_mapping import map_acp_update_to_run_event

__all__ = [
    "ACPClient",
    "ACPTransport",
    "CapabilityMismatchError",
    "CapabilityNegotiationResult",
    "RequiredCapabilities",
    "StdioACPTransport",
    "build_required_capabilities",
    "map_acp_update_to_run_event",
    "negotiate",
]
