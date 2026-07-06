"""Output boundary enforcement for Lawyer Web Chat.

Wraps ``DefaultAssistantOutputBoundary.apply()`` and HTML-escapes the resulting
visible text, ensuring backend noise (model names, API error traces, function
call internals, gateway/meta/system notices) never reaches the lawyer's browser.
"""

from __future__ import annotations

import html
from typing import Any, Mapping

from platform_runtime.output_boundary import (
    BoundaryAction,
    BoundaryDecision,
    DefaultAssistantOutputBoundary,
)


class ChatBoundary:
    """Apply output boundary + HTML escaping for lawyer chat rendering."""

    def __init__(self, inner: DefaultAssistantOutputBoundary | None = None) -> None:
        self._inner = inner or DefaultAssistantOutputBoundary()

    def apply(
        self,
        text: str | None,
        *,
        event_type: str | None = None,
        event_metadata: Mapping[str, object] | None = None,
    ) -> BoundaryDecision:
        """Apply the output boundary and HTML-escape the visible text.

        Returns a ``BoundaryDecision`` whose ``visible_text`` is HTML-escaped.
        When the boundary blocks, ``visible_text`` is ``None``.
        When the boundary rewrites, the owned service notice is HTML-escaped.
        """
        decision = self._inner.apply(
            "web",
            text=text,
            event_type=event_type,
            event_metadata=event_metadata,
        )
        if decision.action == BoundaryAction.ALLOW and decision.visible_text is not None:
            return BoundaryDecision(
                action=decision.action,
                visible_text=html.escape(decision.visible_text),
                audit_metadata=decision.audit_metadata,
                reason=decision.reason,
            )
        if decision.action == BoundaryAction.REWRITE and decision.visible_text is not None:
            return BoundaryDecision(
                action=decision.action,
                visible_text=html.escape(decision.visible_text),
                audit_metadata=decision.audit_metadata,
                reason=decision.reason,
            )
        return decision

    def escape_value(self, value: Any) -> str:
        """HTML-escape an arbitrary value for safe rendering."""
        return html.escape(str(value))


__all__ = ["ChatBoundary"]
