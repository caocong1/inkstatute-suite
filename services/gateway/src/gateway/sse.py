"""SSE encoding for the InkStatute Gateway.

Inlines ``encode_sse_event`` (originally from the retired ``web_sse``
channel package) with output boundary enforcement per event.

The output boundary is the second enforcement point (the first is at the
ACP event bridge). Backend meta / gateway / system / update / command
notices must never reach the SSE stream.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
import json
from typing import Any, Iterator, Mapping

from platform_runtime.output_boundary import (
    BoundaryAction,
    DefaultAssistantOutputBoundary,
)
from platform_runtime.protocols import RunEvent

JsonObject = dict[str, Any]


def encode_sse_event(event: RunEvent | Mapping[str, Any]) -> str:
    """Encode a runtime event into a deterministic SSE frame."""

    payload = _event_mapping(event)
    _assert_no_forbidden_payload_keys(payload)
    data = json.dumps(_json_ready(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"id: {payload['event_id']}\nevent: {payload['event_type']}\ndata: {data}\n\n"


def _event_mapping(event: RunEvent | Mapping[str, Any]) -> JsonObject:
    if isinstance(event, Mapping):
        payload = dict(event)
    elif is_dataclass(event):
        payload = asdict(event)
    else:
        raise TypeError("event must be a RunEvent or mapping")
    for key in ("event_id", "event_type"):
        if not payload.get(key):
            raise ValueError(f"SSE event requires {key}")
    return payload


def _assert_no_forbidden_payload_keys(value: Any, path: str = "") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
            if normalized in {"rawpayload", "rawbody", "callbackbody"}:
                raise ValueError(f"SSE payload contains forbidden raw payload key at {child_path}")
            _assert_no_forbidden_payload_keys(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_payload_keys(child, f"{path}[{index}]")


def _json_ready(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_json_ready(child) for child in value]
    return value


class GatewaySseStream:
    """SSE stream encoder with output boundary enforcement.

    Wraps ``encode_sse_event`` and applies the
    ``DefaultAssistantOutputBoundary`` to each event's text content before
    encoding. Events with blocked content are dropped (return ``None``).
    """

    def __init__(self, boundary: DefaultAssistantOutputBoundary | None = None) -> None:
        self._boundary = boundary or DefaultAssistantOutputBoundary()

    def encode_event(self, event: RunEvent | Mapping[str, Any]) -> str | None:
        """Encode a single event as an SSE frame with boundary applied.

        Returns the SSE frame string, or ``None`` if the event was blocked
        by the output boundary.
        """
        payload = _event_to_mapping(event)
        event_type = payload.get("event_type", "")
        text_content = _extract_text(payload)

        if text_content is not None:
            decision = self._boundary.apply(
                "web",
                text=text_content,
                event_type=_normalize_event_type_for_boundary(event_type),
            )
            if decision.action == BoundaryAction.BLOCK:
                return None
            if decision.visible_text is not None:
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


def parse_last_event_id(headers: Mapping[str, str]) -> int | None:
    """Extract the ``Last-Event-ID`` header value and parse it as an integer.

    Returns ``None`` when the header is absent or not a valid integer.
    This is a placeholder for Plan 91-02's Last-Event-ID replay; in this
    plan it is only used to validate the header is parseable.
    """
    for key, value in headers.items():
        if key.lower() == "last-event-id":
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
    return None


# ---------------------------------------------------------------------------
# Internal helpers (same pattern as lawyer-web-chat/sse.py)
# ---------------------------------------------------------------------------


def _event_to_mapping(event: RunEvent | Mapping[str, Any]) -> dict[str, Any]:
    """Convert a RunEvent or mapping to a plain dict."""
    if isinstance(event, Mapping):
        return dict(event)
    if is_dataclass(event):
        return asdict(event)
    raise TypeError("event must be a RunEvent or mapping")


_V3_TO_V2_EVENT_TYPE_MAP: dict[str, str] = {
    "message.delta": "message_delta",
    "message.completed": "message_delta",
    "run.state_changed": "state_changed",
    "artifact.created": "artifact_created",
    "elicitation.requested": "approval_requested",
    "permission.requested": "approval_requested",
}


def _normalize_event_type_for_boundary(event_type: str) -> str | None:
    """Normalize V3 event types to V2 equivalents for the output boundary.

    The ``DefaultAssistantOutputBoundary`` checks ``event_type`` against a
    V2 allowlist. V3 types (e.g. ``message.delta``) are mapped to their V2
    equivalents (e.g. ``message_delta``). Unknown V3 types return ``None``
    so the event-type check is skipped and text-based rules still apply —
    the event-type filtering is primarily enforced at the ACP event bridge
    (first enforcement point), while the Gateway enforces text-based rules
    (second enforcement point).
    """
    if not event_type:
        return None
    if event_type in _V3_TO_V2_EVENT_TYPE_MAP:
        return _V3_TO_V2_EVENT_TYPE_MAP[event_type]
    # If it's already a V2 type, pass it through
    from platform_runtime.output_boundary import _ALLOWED_STREAM_EVENT_TYPES
    if event_type in _ALLOWED_STREAM_EVENT_TYPES:
        return event_type
    # Unknown type — don't pass to boundary (text rules still apply)
    return None


def _extract_text(payload: Mapping[str, Any]) -> str | None:
    """Extract the text content from an event payload."""
    for key in ("message_delta", "text", "content", "visible_text"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
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


__all__ = [
    "GatewaySseStream",
    "encode_sse_event",
    "parse_last_event_id",
]
