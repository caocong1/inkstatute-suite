"""Fast control-plane routing for follow-up WeCom turns during active tasks (thin shim over channel_core)."""

from __future__ import annotations

from typing import Any, Mapping

from channel_core.active_task_router import (
    ActiveTaskRoute,
    ActiveTaskRoutingDecision,
    AdapterTaskCapabilities,
    route_active_task_turn as _core_route,
)


def route_active_task_turn(
    *,
    text: str | None,
    active_task: Mapping[str, Any],
    capabilities: AdapterTaskCapabilities,
    raw_payload_ref: str | None = None,
) -> ActiveTaskRoutingDecision:
    """Classify a follow-up WeCom turn without blocking on the active task."""

    return _core_route(
        text=text,
        active_task=active_task,
        capabilities=capabilities,
        raw_payload_ref=raw_payload_ref,
        event_name="wecom_active_task_route",
    )


__all__ = [
    "ActiveTaskRoute",
    "ActiveTaskRoutingDecision",
    "AdapterTaskCapabilities",
    "route_active_task_turn",
]
