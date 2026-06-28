"""Pure GET handlers for contract-log-derived read views."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import parse_qs

from .privacy import scrub_contract_payload


def handle_get(
    path: str,
    query: str | Mapping[str, str] | None,
    read_model: Any,
    feedback_queue: list[dict[str, Any]] | None = None,
) -> tuple[int, dict[str, Any]]:
    route_path, route_query = _split_path_query(path, query)
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
    response = dict(body)
    metadata = dict(response.get("metadata", {})) if isinstance(response.get("metadata"), Mapping) else {}
    metadata["derived_from_contract_log"] = True
    response["metadata"] = metadata
    return response


__all__ = [
    "handle_get",
    "not_found_response",
    "parse_query_string",
]
