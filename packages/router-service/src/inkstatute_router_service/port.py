"""RouterPort Protocol — the injectable router interface.

Implementations of ``RouterPort`` must be stateless and side-effect free.
Callers fall back to inline inference when the router is unavailable
(``None`` default preserves existing in-process behavior).
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from platform_contract import RouteDecision


class RouterPort(Protocol):
    """Protocol for injectable router implementations.

    Implementations must be stateless and side-effect free.  When no router
    is injected (``router is None``), callers fall back to inline inference
    exactly as today.
    """

    def decide(self, context: Mapping[str, Any]) -> RouteDecision:
        """Produce a normalized ``RouteDecision`` from *context*.

        *context* is a mapping of router inputs (e.g. ``message``,
        ``turn_id``, ``route_decision_id``).  The returned ``RouteDecision``
        must use frozen ``RouteMode`` values only.
        """
        ...
