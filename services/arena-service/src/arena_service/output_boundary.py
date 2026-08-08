"""Arena Service output boundary — two-layer enforcement (SVC-04).

Wraps :class:`ACPOutputFilter` as the first enforcement layer (ACP
pre-filter) and :class:`DefaultAssistantOutputBoundary` as the second
layer.  This is the arena service's second enforcement point of the
"output boundary enforced twice" requirement from AGENTS.md (the first
is at the ACP event bridge).

Blocked content categories (8): meta, gateway, system, update, command,
help, available_commands_update, terminal.  Unknown event types are
default-denied (blocked) — only :data:`ACP_ALLOWED_EVENT_TYPES` pass
through.
"""

from __future__ import annotations

from typing import Any

from inkstatute_acp_event_bridge.output_filter import (
    ACPOutputFilter,
    FilterAction,
    FilterDecision,
)
from platform_runtime.output_boundary import DefaultAssistantOutputBoundary


class ArenaOutputBoundary:
    """Two-layer output boundary for the Arena Service.

    Layer 1 — ACP pre-filter (:class:`ACPOutputFilter`): event-type
    default-deny + 8 blocked content categories + backend-lifecycle
    rewrite.

    Layer 2 — :class:`DefaultAssistantOutputBoundary`: secret patterns,
    internal paths, provider leaks, operator commands, debug traces.

    The ACP pre-filter runs first.  If it returns BLOCK or REWRITE, the
    second layer is **not** called (short-circuit).  If it returns
    ALLOW, the second layer is applied for additional content-based
    filtering.
    """

    def __init__(self) -> None:
        self._acp_filter = ACPOutputFilter()
        self._default_boundary = DefaultAssistantOutputBoundary()

    # ------------------------------------------------------------------
    # Core filtering
    # ------------------------------------------------------------------

    def filter_event(
        self,
        event_type: str,
        content: str | None,
        metadata: dict | None = None,
    ) -> FilterDecision:
        """Filter a single event through both enforcement layers.

        Layer 1 (ACP pre-filter) runs first.  If BLOCK or REWRITE,
        short-circuit — the second layer is not called.  If ALLOW,
        apply the second layer (:class:`DefaultAssistantOutputBoundary`)
        for additional content-based checks.

        Parameters
        ----------
        event_type
            The unified event type string (e.g. ``"message.delta"``).
        content
            The content text to filter.  May be ``None`` or empty.
        metadata
            Optional event metadata (reserved for future use).

        Returns
        -------
        FilterDecision
            The combined decision from both enforcement layers.
        """
        # Layer 1: ACP pre-filter
        acp_decision = self._acp_filter.filter_event(event_type, content, metadata)

        # Short-circuit: if ACP filter blocks or rewrites, don't call
        # the second layer.
        if acp_decision.action != FilterAction.ALLOW.value:
            return acp_decision

        # Layer 2: DefaultAssistantOutputBoundary
        boundary_decision = self._default_boundary.apply(
            visibility_target="user",
            text=content,
            event_type=None,  # content-based checks only
        )

        # Convert BoundaryDecision to FilterDecision
        action = boundary_decision.action
        if hasattr(action, "value"):
            action = action.value
        else:
            action = str(action)

        return FilterDecision(
            action=action,
            visible_content=boundary_decision.visible_text,
            audit_metadata=boundary_decision.audit_metadata,
            reason=boundary_decision.reason,
        )

    # ------------------------------------------------------------------
    # SSE event integration
    # ------------------------------------------------------------------

    def apply_to_sse_event(
        self,
        event: dict[str, Any],
    ) -> tuple[bool, dict[str, Any]]:
        """Apply the boundary to an SSE event dict.

        Extracts ``event_type`` and content from the event's payload,
        calls :meth:`filter_event`, and returns
        ``(should_send, filtered_event)``.

        - BLOCK  → ``(False, event)``
        - ALLOW  → ``(True, event)``
        - REWRITE → ``(True, event_with_replaced_content)``

        Parameters
        ----------
        event
            An SSE event dict with ``event_type``, ``payload`` (with
            ``text`` / ``content`` / ``message_delta``), and optional
            ``metadata``.

        Returns
        -------
        tuple[bool, dict[str, Any]]
            ``(should_send, filtered_event)``.
        """
        event_type = event.get("event_type", "")
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        content: str | None = None
        for key in ("text", "content", "message_delta"):
            value = payload.get(key)
            if isinstance(value, str):
                content = value
                break

        decision = self.filter_event(event_type, content, event.get("metadata"))

        if decision.action == FilterAction.BLOCK.value:
            return False, event

        if decision.action == FilterAction.REWRITE.value:
            result = dict(event)
            result_payload = dict(payload)
            replaced = False
            for key in ("text", "content", "message_delta"):
                if key in result_payload:
                    result_payload[key] = decision.visible_content
                    replaced = True
                    break
            if not replaced:
                result_payload["text"] = decision.visible_content
            result["payload"] = result_payload
            return True, result

        return True, event

    # ------------------------------------------------------------------
    # Decision helpers
    # ------------------------------------------------------------------

    def should_send(self, decision: FilterDecision) -> bool:
        """Return ``True`` if the decision allows the event to be sent."""
        return decision.action != FilterAction.BLOCK.value


__all__ = [
    "ArenaOutputBoundary",
]
