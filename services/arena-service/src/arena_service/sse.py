"""SSE encoding for the Arena Service with N-agent multiplexing.

Encodes arena events (lifecycle + per-slot ``RunEvent`` re-emissions) as
SSE frames on a single connection. Each event carries
``metadata.agent_slot`` so the client can demultiplex the interleaved
stream by slot.

This module mirrors the Gateway's ``gateway.sse`` pattern
(``encode_sse_event`` / ``GatewaySseStream`` / ``parse_last_event_id``)
but is reimplemented locally to keep ``arena-service`` dependency-free
(no import from ``gateway``).

SVC-03: N agents' events on a single SSE connection, each tagged with
``metadata.agent_slot``. The client demultiplexes by filtering on
``metadata.agent_slot`` in the SSE JSON data.

SVC-07: ``parse_last_event_id`` extracts the ``Last-Event-ID`` header
for reconnection; the actual replay is handled by
:class:`arena_service.event_buffer.ArenaEventBuffer`.
"""

from __future__ import annotations

import json
from typing import Any, Iterator, Mapping

JsonObject = dict[str, Any]


def encode_arena_sse_event(event: Mapping[str, Any]) -> str:
    """Encode an arena event into a deterministic SSE frame.

    The full event dict (including ``metadata`` with ``agent_slot``) is
    serialized as JSON with ``ensure_ascii=False, sort_keys=True,
    separators=(",", ":")`` so the output is stable and the
    ``agent_slot`` tag is preserved in the data line.

    Parameters
    ----------
    event
        A mapping with at least ``event_id`` and ``event_type`` keys.
        May also contain ``seq``, ``payload``, ``metadata`` (with
        ``agent_slot``), and any other fields.

    Returns
    -------
    str
        An SSE frame of the form::

            id: {event_id}\n
            event: {event_type}\n
            data: {json}\n
            \n

    Raises
    ------
    ValueError
        If ``event_id`` or ``event_type`` is missing or empty.
    """
    payload = dict(event)
    for key in ("event_id", "event_type"):
        if not payload.get(key):
            raise ValueError(f"SSE event requires {key}")
    data = json.dumps(
        _json_ready(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"id: {payload['event_id']}\nevent: {payload['event_type']}\ndata: {data}\n\n"


def parse_last_event_id(headers: Mapping[str, str]) -> int | None:
    """Extract the ``Last-Event-ID`` header and parse it as an integer.

    Performs a case-insensitive lookup for the ``Last-Event-ID`` header.
    Returns ``None`` when the header is absent or not a valid integer.

    Parameters
    ----------
    headers
        A mapping of HTTP header names to values (case-insensitive).

    Returns
    -------
    int | None
        The parsed integer, or ``None`` if absent / unparseable.
    """
    for key, value in headers.items():
        if key.lower() == "last-event-id":
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
    return None


class ArenaSseStream:
    """SSE stream encoder with agent_slot multiplexing and optional output filter.

    Wraps :func:`encode_arena_sse_event` and applies an optional output
    filter (wired in Plan 03 to ``ACPOutputFilter``) before encoding.
    Events blocked by the filter are dropped (``encode_event`` returns
    ``None``).

    The multiplexing is implicit: each event already carries
    ``metadata.agent_slot`` (set by the arena engine's
    ``EventEmitter``), so no slot-specific logic is needed here — the
    tag flows through the JSON serialization unchanged.
    """

    def __init__(self, output_filter: object | None = None) -> None:
        """Initialize the stream.

        Parameters
        ----------
        output_filter
            Optional object implementing ``filter_event(event_type,
            content, metadata)``. When provided, ``encode_event`` calls
            it before encoding. A BLOCK decision returns ``None``; a
            REWRITE decision replaces the content. Wired in Plan 03.
        """
        self._output_filter = output_filter

    def encode_event(self, event: Mapping[str, Any]) -> str | None:
        """Encode a single event as an SSE frame.

        If an output filter is set, it is consulted before encoding.
        Blocked events return ``None``; rewritten content replaces the
        event's payload content.

        Returns
        -------
        str | None
            The SSE frame string, or ``None`` if blocked by the filter.
        """
        payload = dict(event)
        if self._output_filter is not None:
            decision = self._output_filter.filter_event(
                payload.get("event_type", ""),
                _extract_content(payload),
                payload.get("metadata", {}),
            )
            action = _decision_action(decision)
            if action == "BLOCK":
                return None
            if action == "REWRITE":
                rewritten = _decision_content(decision)
                if rewritten is not None:
                    _replace_content(payload, rewritten)
        return encode_arena_sse_event(payload)

    def encode_events(
        self,
        events: list[Mapping[str, Any]],
    ) -> Iterator[str]:
        """Encode a list of events as SSE frames, skipping blocked events.

        Yields each non-``None`` frame in order, preserving the original
        event ordering and slot identity.
        """
        for event in events:
            frame = self.encode_event(event)
            if frame is not None:
                yield frame

    def encode_stream_response(
        self,
        events: list[Mapping[str, Any]],
    ) -> str:
        """Encode events as a complete SSE response body (joined frames)."""
        return "".join(self.encode_events(events))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _json_ready(value: Any) -> Any:
    """Recursively convert a value to a JSON-serializable form."""
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_json_ready(child) for child in value]
    return value


def _extract_content(payload: Mapping[str, Any]) -> str:
    """Extract the text content from an event payload for filter inspection."""
    for key in ("text", "content", "message_delta", "visible_text"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    nested = payload.get("payload")
    if isinstance(nested, Mapping):
        for key in ("text", "content", "message_delta", "visible_text"):
            value = nested.get(key)
            if isinstance(value, str):
                return value
    return ""


def _replace_content(payload: dict[str, Any], new_text: str) -> None:
    """Replace the text content in an event payload in place."""
    for key in ("text", "content", "message_delta", "visible_text"):
        if key in payload:
            payload[key] = new_text
            return
    nested = payload.get("payload")
    if isinstance(nested, dict):
        for key in ("text", "content", "message_delta", "visible_text"):
            if key in nested:
                nested[key] = new_text
                return


def _decision_action(decision: Any) -> str:
    """Extract the action string from a filter decision object."""
    action = getattr(decision, "action", None)
    if action is None and isinstance(decision, Mapping):
        action = decision.get("action")
    if hasattr(action, "value"):
        action = action.value
    return str(action).upper() if action is not None else ""


def _decision_content(decision: Any) -> str | None:
    """Extract the rewritten content from a filter decision object."""
    for attr in ("visible_text", "content", "rewritten_content"):
        value = getattr(decision, attr, None)
        if value is None and isinstance(decision, Mapping):
            value = decision.get(attr)
        if isinstance(value, str):
            return value
    return None


__all__ = [
    "ArenaSseStream",
    "encode_arena_sse_event",
    "parse_last_event_id",
]
