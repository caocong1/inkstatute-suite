"""Pure GET handlers for the contract event audit trail (Phase 83)."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import parse_qs

from .pagination import clamp_limit, resolve_max_result_limit, slice_page
from .privacy import scrub_contract_payload

AUDIT_EVENT_TYPES = ("agent_turn", "feedback_event")

# Field allowlist for trace reconstruction display.
# Only these fields are retained in each event dict; all others are dropped.
# Refs (e.g. raw_payload_ref) are kept; resolved secrets are never present
# because scrub_contract_payload already rejects forbidden keys.
TRACE_FIELD_ALLOWLIST = frozenset({
    "event_key",
    "occurred_at",
    "seq",
    "turn_id",
    "conversation_id",
    "trace_id",
    "channel",
    "user_id",
    "received_at",
    "route_decision_id",
    "primary_skill",
    "mode",
    "status",
    "started_at",
    "ended_at",
    "duration_ms",
    "feedback_action",
    "action",
    "feedback_target",
    "raw_payload_ref",
    "skill_candidate",
    "related_skill",
    "related_route_decision",
    "created_at",
})


def handle_audit_get(
    path: str,
    query: str | Mapping[str, str] | None,
    read_model: Any,
    tenant_filter: Any = None,
) -> tuple[int, dict[str, Any]]:
    """Handle ``GET /audit`` (paginated audit trail) and ``GET /audit/<trace_id>``.

    ``GET /audit`` returns AgentTurn and FeedbackEvent records in
    reverse-chronological order with cursor pagination and an event-type
    filter.  ``GET /audit/<trace_id>`` returns the full trace reconstruction
    with a field allowlist applied.
    """
    route_path, route_query = _split_path_query(path, query)

    # GET /audit/<trace_id> — trace reconstruction.
    if route_path.startswith("/audit/"):
        trace_id = route_path.removeprefix("/audit/")
        reconstruction = read_model.get_trace_reconstruction(trace_id)
        if reconstruction is None:
            return 404, {
                "error": {
                    "code": "not_found",
                    "resource": "trace",
                    "identifier": trace_id,
                },
                "metadata": {
                    "derived_from_contract_log": True,
                },
            }
        events = reconstruction.get("events", [])
        reconstruction = dict(reconstruction)
        reconstruction["events"] = _apply_trace_field_allowlist(events)
        scrubbed = scrub_contract_payload(reconstruction)
        return 200, scrubbed

    # GET /audit — paginated audit trail list.
    event_type = route_query.get("event_type")
    if event_type is not None and event_type not in AUDIT_EVENT_TYPES:
        return 400, {
            "error": {
                "code": "invalid_event_type",
                "message": "event_type must be 'agent_turn', 'feedback_event', or absent",
                "event_type": event_type,
            },
            "metadata": {
                "derived_from_contract_log": True,
            },
        }

    max_limit = resolve_max_result_limit()
    limit = clamp_limit(route_query.get("limit"), max_limit)
    cursor = route_query.get("cursor")
    items = read_model.list_audit_events(
        event_type=event_type, tenant_filter=tenant_filter
    )
    page_items, next_cursor, has_more = slice_page(items, cursor, limit)

    return 200, {
        "items": page_items,
        "count": len(page_items),
        "next_cursor": next_cursor,
        "has_more": has_more,
        "metadata": {
            "derived_from_contract_log": True,
            "limit": limit,
            "max_result_limit": max_limit,
            "event_type": event_type,
            "admin_api": True,
            "read_only": True,
        },
    }


def _apply_trace_field_allowlist(events: list[dict]) -> list[dict]:
    """Filter each trace event entry to only allowlisted fields.

    Each entry is ``{"event_key": ..., "occurred_at": ..., "seq": ..., "event": {...}}``.
    The ``event_key``, ``occurred_at``, and ``seq`` fields are always kept at
    the entry level.  The nested ``event`` dict is filtered to only keys in
    ``TRACE_FIELD_ALLOWLIST``; a nested ``metadata`` dict keeps only
    ``trace_id``.
    """
    result: list[dict] = []
    for entry in events:
        if not isinstance(entry, Mapping):
            continue
        filtered: dict[str, Any] = {
            "event_key": entry.get("event_key"),
            "occurred_at": entry.get("occurred_at"),
            "seq": entry.get("seq"),
        }
        event = entry.get("event")
        if isinstance(event, Mapping):
            allowed_event: dict[str, Any] = {}
            for key, value in event.items():
                if key == "metadata" and isinstance(value, Mapping):
                    # metadata is not in the allowlist as a top-level key, but
                    # metadata.trace_id is always retained.
                    allowed_event["metadata"] = {"trace_id": value.get("trace_id")}
                elif key in TRACE_FIELD_ALLOWLIST:
                    allowed_event[key] = value
            filtered["event"] = allowed_event
        result.append(filtered)
    return result


def _split_path_query(
    path: str,
    query: str | Mapping[str, str] | None,
) -> tuple[str, dict[str, str]]:
    if "?" in path:
        route_path, inline_query = path.split("?", 1)
        merged = _parse_query_string(inline_query)
        merged.update(_parse_query_string(query))
        return route_path, merged
    return path, _parse_query_string(query)


def _parse_query_string(query: str | Mapping[str, str] | None) -> dict[str, str]:
    if query is None:
        return {}
    if isinstance(query, Mapping):
        return {str(key): str(value) for key, value in query.items()}
    parsed = parse_qs(query.lstrip("?"), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


__all__ = [
    "AUDIT_EVENT_TYPES",
    "TRACE_FIELD_ALLOWLIST",
    "handle_audit_get",
    "_apply_trace_field_allowlist",
]
