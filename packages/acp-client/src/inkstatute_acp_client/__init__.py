"""InkStatute ACP Backend Client — drives any ACP v1 agent as a backend over stdio."""

from .adapter import (
    ACPBackendAdapter,
    ACPBackendConfig,
    HERMES_COMPATIBILITY_MATRIX,
    check_hermes_compatibility,
    create_hermes_adapter,
)
from .capability_negotiation import (
    CapabilityMismatchError,
    CapabilityNegotiationResult,
    RequiredCapabilities,
    build_required_capabilities,
    negotiate,
)
from .client import ACPClient, ACPTransport, StdioACPTransport
from .event_mapping import map_acp_update_to_run_event
from .lifecycle import SubprocessInfo, SubprocessLifecycleManager, assert_no_orphans
from .process_mode import (
    IMPLEMENTED_MODES,
    ProcessModeConfig,
    UNIMPLEMENTED_MODES,
    is_mode_implemented,
    validate_process_mode,
)

__all__ = [
    "ACPBackendAdapter",
    "ACPBackendConfig",
    "ACPClient",
    "ACPTransport",
    "CapabilityMismatchError",
    "CapabilityNegotiationResult",
    "HERMES_COMPATIBILITY_MATRIX",
    "IMPLEMENTED_MODES",
    "ProcessModeConfig",
    "RequiredCapabilities",
    "StdioACPTransport",
    "SubprocessInfo",
    "SubprocessLifecycleManager",
    "UNIMPLEMENTED_MODES",
    "assert_no_orphans",
    "build_required_capabilities",
    "check_hermes_compatibility",
    "create_hermes_adapter",
    "is_mode_implemented",
    "map_acp_update_to_run_event",
    "negotiate",
    "validate_process_mode",
]
