"""Pure GET handlers for contract-log-derived read views."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping
from urllib.parse import parse_qs

from .pagination import clamp_limit, resolve_max_result_limit, slice_page
from .privacy import scrub_contract_payload

_ALLOWED_CONVERSATION_FILTERS = {"from", "to", "user_id", "channel"}
_ALLOWED_TASK_FILTERS = {"from", "to", "user_id", "channel", "status"}
_PAGINATION_KEYS = {"cursor", "limit"}


def handle_get(
    path: str,
    query: str | Mapping[str, str] | None,
    read_model: Any,
    feedback_queue: list[dict[str, Any]] | None = None,
) -> tuple[int, dict[str, Any]]:
    route_path, route_query = _split_path_query(path, query)

    if route_path == "/conversations":
        return _handle_list_conversations(route_query, read_model)

    if route_path == "/tasks":
        return _handle_list_tasks(route_query, read_model)

    if route_path.startswith("/conversations/"):
        conversation_id = route_path.removeprefix("/conversations/")
        conversation = read_model.get_conversation(conversation_id)
        if conversation is None:
            return 404, not_found_response("conversation", conversation_id)
        return 200, _with_contract_metadata(conversation)

    if route_path.startswith("/tasks/"):
        identifier = route_path.removeprefix("/tasks/")
        task = read_model.get_task(identifier)
        if task is None:
            task = read_model.get_task_by_trace_id(identifier)
        if task is None:
            return 404, not_found_response("task", identifier)
        return 200, _with_contract_metadata(task)

    if route_path.startswith("/traces/"):
        trace_id = route_path.removeprefix("/traces/")
        reconstruction = read_model.get_trace_reconstruction(trace_id)
        if reconstruction is None:
            return 404, not_found_response("trace", trace_id)
        return 200, _with_contract_metadata(reconstruction)

    if route_path == "/feedback":
        status = route_query.get("status", "pending")
        if status != "pending":
            return 400, {
                "error": {
                    "code": "unsupported_status",
                    "message": "only pending feedback is supported by the Phase 6 API",
                    "status": status,
                },
                "metadata": {
                    "derived_from_contract_log": True,
                    "source_status": "unsupported_filter",
                },
            }
        items = [scrub_contract_payload(item) for item in feedback_queue or [] if item.get("status") == "pending"]
        return 200, {
            "items": items,
            "count": len(items),
            "metadata": {
                "derived_from_contract_log": True,
                "source_status": "derived_pending_queue",
            },
        }

    return 404, not_found_response("route", route_path)


def _handle_list_conversations(
    query: dict[str, str],
    read_model: Any,
) -> tuple[int, dict[str, Any]]:
    filters, error = _parse_list_filters(query, _ALLOWED_CONVERSATION_FILTERS)
    if error is not None:
        return 400, _filter_error_response(error, query)

    max_limit = resolve_max_result_limit()
    items = read_model.list_conversations(
        time_from=filters.get("from"),
        time_to=filters.get("to"),
        user_id=filters.get("user_id"),
        channel=filters.get("channel"),
    )
    return _list_response(items, query, max_limit, filters)


def _handle_list_tasks(
    query: dict[str, str],
    read_model: Any,
) -> tuple[int, dict[str, Any]]:
    filters, error = _parse_list_filters(query, _ALLOWED_TASK_FILTERS)
    if error is not None:
        return 400, _filter_error_response(error, query)

    max_limit = resolve_max_result_limit()
    items = read_model.list_tasks(
        time_from=filters.get("from"),
        time_to=filters.get("to"),
        user_id=filters.get("user_id"),
        channel=filters.get("channel"),
        status=filters.get("status"),
    )
    return _list_response(items, query, max_limit, filters)


def _list_response(
    items: list[tuple[str, str, dict[str, Any]]],
    query: dict[str, str],
    max_limit: int,
    filters: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    cursor = query.get("cursor")
    limit = clamp_limit(query.get("limit"), max_limit)
    page_items, next_cursor, has_more = slice_page(items, cursor, limit)

    return 200, {
        "items": [scrub_contract_payload(item) for item in page_items],
        "count": len(page_items),
        "next_cursor": next_cursor,
        "has_more": has_more,
        "metadata": {
            "derived_from_contract_log": True,
            "limit": limit,
            "max_result_limit": max_limit,
            "filters": filters,
        },
    }


def _parse_list_filters(
    query: dict[str, str],
    allowed_keys: set[str],
) -> tuple[dict[str, Any], str | None]:
    filters: dict[str, Any] = {}
    for key, value in query.items():
        if key in _PAGINATION_KEYS:
            continue
        if key not in allowed_keys:
            return filters, "unsupported_filter"
        if key in ("from", "to"):
            parsed = _parse_time_filter(value, key)
            if parsed is None:
                return filters, "invalid_time_filter"
            filters[key] = parsed
        else:
            filters[key] = value
    return filters, None


def _parse_time_filter(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return value


def _filter_error_response(code: str, query: dict[str, str]) -> dict[str, Any]:
    if code == "unsupported_filter":
        return {
            "error": {
                "code": "unsupported_filter",
                "message": "unknown filter key in query",
                "query": dict(query),
            },
            "metadata": {
                "derived_from_contract_log": True,
                "source_status": "unsupported_filter",
            },
        }
    return {
        "error": {
            "code": "invalid_time_filter",
            "message": "from/to must be valid ISO-8601 timestamps",
            "query": dict(query),
        },
        "metadata": {
            "derived_from_contract_log": True,
            "source_status": "invalid_time_filter",
        },
    }


def parse_query_string(query: str | Mapping[str, str] | None) -> dict[str, str]:
    if query is None:
        return {}
    if isinstance(query, Mapping):
        return {str(key): str(value) for key, value in query.items()}
    parsed = parse_qs(query.lstrip("?"), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def not_found_response(resource: str, identifier: str) -> dict[str, Any]:
    return {
        "error": {
            "code": "not_found",
            "resource": resource,
            "identifier": identifier,
        },
        "metadata": {
            "derived_from_contract_log": True,
            "source_status": "not_found",
        },
    }


def _split_path_query(path: str, query: str | Mapping[str, str] | None) -> tuple[str, dict[str, str]]:
    if "?" in path:
        route_path, inline_query = path.split("?", 1)
        merged = parse_query_string(inline_query)
        merged.update(parse_query_string(query))
        return route_path, merged
    return path, parse_query_string(query)


def _with_contract_metadata(body: dict[str, Any]) -> dict[str, Any]:
    scrubbed = scrub_contract_payload(body)
    response = dict(scrubbed) if isinstance(scrubbed, dict) else {"data": scrubbed}
    metadata = dict(response.get("metadata", {})) if isinstance(response.get("metadata"), Mapping) else {}
    metadata["derived_from_contract_log"] = True
    response["metadata"] = metadata
    return response


__all__ = [
    "handle_get",
    "not_found_response",
    "parse_query_string",
]
