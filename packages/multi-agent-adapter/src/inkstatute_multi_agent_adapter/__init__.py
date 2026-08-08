"""Multi-Agent Runtime Adapter — composite BackendAdapter for the InkStatute platform.

.. deprecated:: Phase 104
    This package is **experimental** and **frozen** as of Phase 104 (2026-08-08).
    No production consumers exist and no new features should be added.
    The code and tests are preserved for reference and the package remains in
    the gate system to ensure it compiles. See ``FROZEN.md`` for details.
"""

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
