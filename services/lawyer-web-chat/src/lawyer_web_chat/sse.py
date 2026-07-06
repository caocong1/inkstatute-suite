"""SSE streaming for Lawyer Web Chat.

Reuses ``encode_sse_event`` from ``inkstatute_channels_web_sse`` for SSE frame
encoding. The output boundary is applied per event — backend noise (model names,
API error traces, function call internals) is filtered before any event reaches
the lawyer's browser.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Iterator, Mapping

from inkstatute_channels_web_sse import encode_sse_event
from platform_runtime.output_boundary import BoundaryAction
from platform_runtime.protocols import RunEvent

from .boundary import ChatBoundary


class SseStream:
    """SSE stream encoder with output boundary enforcement.

    Wraps ``encode_sse_event`` and applies the ``ChatBoundary`` to each event's
    text content before encoding. Events with blocked content are dropped.
    """

    def __init__(self, boundary: ChatBoundary | None = None) -> None:
        self._boundary = boundary or ChatBoundary()

    def encode_event(
        self,
        event: RunEvent | Mapping[str, Any],
    ) -> str | None:
        """Encode a single event as an SSE frame with boundary applied.

        Returns the SSE frame string, or ``None`` if the event was blocked
        by the output boundary.
        """
        payload = _event_to_mapping(event)
        event_type = payload.get("event_type", "")
        text_content = _extract_text(payload)

        if text_content is not None:
            decision = self._boundary.apply(text_content, event_type=event_type)
            if decision.action == BoundaryAction.BLOCK:
                return None
            if decision.action == BoundaryAction.REWRITE and decision.visible_text is not None:
                _replace_text(payload, decision.visible_text)
            elif decision.action == BoundaryAction.ALLOW and decision.visible_text is not None:
                _replace_text(payload, decision.visible_text)

        return encode_sse_event(payload)

    def encode_events(
        self,
        events: list[RunEvent | Mapping[str, Any]],
    ) -> Iterator[str]:
        """Encode a list of events as SSE frames, skipping blocked events."""
        for event in events:
            frame = self.encode_event(event)
            if frame is not None:
                yield frame

    def encode_stream_response(
        self,
        events: list[RunEvent | Mapping[str, Any]],
    ) -> str:
        """Encode events as a complete SSE response body."""
        return "".join(self.encode_events(events))


def _event_to_mapping(event: RunEvent | Mapping[str, Any]) -> dict[str, Any]:
    """Convert a RunEvent or mapping to a plain dict."""
    if isinstance(event, Mapping):
        return dict(event)
    if is_dataclass(event):
        return asdict(event)
    raise TypeError("event must be a RunEvent or mapping")


def _extract_text(payload: Mapping[str, Any]) -> str | None:
    """Extract the text content from an event payload."""
    # Check common text fields in order of preference
    for key in ("message_delta", "text", "content", "visible_text"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    # Check nested payload
    nested = payload.get("payload")
    if isinstance(nested, Mapping):
        for key in ("message_delta", "text", "content", "visible_text"):
            value = nested.get(key)
            if isinstance(value, str):
                return value
    return None


def _replace_text(payload: dict[str, Any], new_text: str) -> None:
    """Replace the text content in an event payload."""
    for key in ("message_delta", "text", "content", "visible_text"):
        if key in payload:
            payload[key] = new_text
            return
    nested = payload.get("payload")
    if isinstance(nested, dict):
        for key in ("message_delta", "text", "content", "visible_text"):
            if key in nested:
                nested[key] = new_text
                return


__all__ = ["SseStream"]
