"""Multi-Agent Runtime Adapter — composite BackendAdapter for the InkStatute platform."""

from .adapter import MultiAgentRuntimeAdapter
from .config import (
    MultiAgentOrchestrationConfig,
    MultiAgentOrchestrationMode,
    MultiAgentRuntimeAdapterConfig,
)
from .errors import (
    MultiAgentCycleError,
    MultiAgentError,
    MultiAgentHandoffLimitError,
    MultiAgentRoutingError,
)
from .shared_state import SharedStateStore

__all__ = [
    "MultiAgentCycleError",
    "MultiAgentError",
    "MultiAgentHandoffLimitError",
    "MultiAgentOrchestrationConfig",
    "MultiAgentOrchestrationMode",
    "MultiAgentRoutingError",
    "MultiAgentRuntimeAdapter",
    "MultiAgentRuntimeAdapterConfig",
    "SharedStateStore",
]
