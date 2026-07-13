"""Read-only data view handlers for the Admin Console API.

Delegates to ``ContractLogReadModel`` methods from
``services/conversation-read-view/`` and reuses cursor pagination from the
same package.  All responses are routed through ``scrub_contract_payload``.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Mapping
from urllib.parse import parse_qs

from conversation_read_view.pagination import clamp_limit, slice_page
from conversation_read_view.privacy import scrub_contract_payload
from conversation_read_view.tenant_read_model import TenantScopedContractLogReadModel

from .feedback import ThreadSafeFeedbackQueue

ADMIN_API_MAX_LIMIT_ENV = "ADMIN_API_MAX_LIMIT"

DEFAULT_MAX_LIMIT = 100
MIN_MAX_LIMIT = 10
MAX_MAX_LIMIT = 1000
DEFAULT_PAGE_SIZE = 50

_ALLOWED_SESSION_FILTERS = {"from", "to", "user_id", "channel"}
_ALLOWED_TASK_FILTERS = {"from", "to", "user_id", "channel", "status"}
_PAGINATION_KEYS = {"cursor", "limit"}


def resolve_admin_max_limit(env: Mapping[str, str] | None = None) -> int:
    """Resolve the configured max result limit from env.

    Reads ``ADMIN_API_MAX_LIMIT`` from ``env`` (or ``os.environ``), parses as
    int, and clamps to ``[MIN_MAX_LIMIT, MAX_MAX_LIMIT]``.  Returns
    ``DEFAULT_MAX_LIMIT`` when absent or unparseable.
    """

    source: Mapping[str, str] = env if env is not None else os.environ
    raw = source.get(ADMIN_API_MAX_LIMIT_ENV)
    if raw is None:
        return DEFAULT_MAX_LIMIT
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_LIMIT
    return max(MIN_MAX_LIMIT, min(value, MAX_MAX_LIMIT))


def handle_sessions(
    path: str,
    query: dict[str, str],
    read_model: Any,
    *,
    tenant_filter: Any = None,
) -> tuple[int, dict[str, Any]]:
    """Handle ``/sessions`` (list) and ``/sessions/{id}`` (detail) views.

    Sessions = conversations in the contract log model.
    When ``tenant_filter`` is active, results are filtered by tenant_id.
    """

    scoped = _wrap_scoped(read_model)

    if path == "/sessions":
        filters, error = _parse_filters(query, _ALLOWED_SESSION_FILTERS)
        if error is not None:
            return 400, _filter_error_response(error, query)
        max_limit = resolve_admin_max_limit()
        items = scoped.list_conversations(
            time_from=filters.get("from"),
            time_to=filters.get("to"),
            user_id=filters.get("user_id"),
            channel=filters.get("channel"),
            tenant_filter=tenant_filter,
        )
        return _list_response(items, query, max_limit, filters)

    if path.startswith("/sessions/"):
        session_id = path.removeprefix("/sessions/")
        conversation = scoped.get_conversation(session_id, tenant_filter=tenant_filter)
        if conversation is None:
            return 404, _not_found_response("session", session_id)
        return 200, _with_admin_metadata(conversation)

    return 404, _not_found_response("route", path)


def handle_tasks(
    path: str,
    query: dict[str, str],
    read_model: Any,
    *,
    tenant_filter: Any = None,
) -> tuple[int, dict[str, Any]]:
    """Handle ``/tasks`` (list) and ``/tasks/{id}`` (detail) views.

    When ``tenant_filter`` is active, results are filtered by tenant_id.
    """

    scoped = _wrap_scoped(read_model)

    if path == "/tasks":
        filters, error = _parse_filters(query, _ALLOWED_TASK_FILTERS)
        if error is not None:
            return 400, _filter_error_response(error, query)
        max_limit = resolve_admin_max_limit()
        items = scoped.list_tasks(
            time_from=filters.get("from"),
            time_to=filters.get("to"),
            user_id=filters.get("user_id"),
            channel=filters.get("channel"),
            status=filters.get("status"),
            tenant_filter=tenant_filter,
        )
        return _list_response(items, query, max_limit, filters)

    if path.startswith("/tasks/"):
        identifier = path.removeprefix("/tasks/")
        task = scoped.get_task(identifier, tenant_filter=tenant_filter)
        if task is None:
            task = scoped.get_task_by_trace_id(identifier, tenant_filter=tenant_filter)
        if task is None:
            return 404, _not_found_response("task", identifier)
        return 200, _with_admin_metadata(task)

    return 404, _not_found_response("route", path)


def handle_feedback(
    query: dict[str, str],
    read_model: Any,
    feedback_queue: list[dict[str, Any]] | ThreadSafeFeedbackQueue | None,
    *,
    tenant_filter: Any = None,
) -> tuple[int, dict[str, Any]]:
    """Handle ``/feedback`` view — pending feedback items only.

    When ``tenant_filter`` is active, items are additionally filtered by
    ``tenant_id``.  Items without a ``tenant_id`` field are excluded when
    the filter is active (fail-safe: no tenant_id = no access in multi-tenant
    mode).
    """

    status = query.get("status", "pending")
    if status != "pending":
        return 400, {
            "error": {
                "code": "unsupported_status",
                "message": "only pending feedback is supported",
                "status": status,
            },
            "metadata": {"admin_api": True, "read_only": True},
        }
    filter_active = tenant_filter is not None and getattr(tenant_filter, "is_active", False)
    items = [
        scrub_contract_payload(item)
        for item in (feedback_queue or [])
        if item.get("status") == "pending"
        and (not filter_active or item.get("tenant_id") == tenant_filter.tenant_id)
    ]
    return 200, {
        "items": items,
        "count": len(items),
        "metadata": {
            "admin_api": True,
            "read_only": True,
            "source_status": "derived_pending_queue",
        },
    }


def _wrap_scoped(read_model: Any) -> Any:
    """Wrap read_model in TenantScopedContractLogReadModel.

    The wrapper delegates directly when tenant_filter is None or inactive,
    so there is no behavior change or overhead for disabled mode.
    """
    if isinstance(read_model, TenantScopedContractLogReadModel):
        return read_model
    return TenantScopedContractLogReadModel(read_model)


def _parse_filters(
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
            "admin_api": True,
            "read_only": True,
            "limit": limit,
            "max_result_limit": max_limit,
            "filters": filters,
        },
    }


def _filter_error_response(error: str, query: dict[str, str]) -> dict[str, Any]:
    if error == "unsupported_filter":
        return {
            "error": {
                "code": "unsupported_filter",
                "message": "unknown filter key in query",
                "query": dict(query),
            },
            "metadata": {"admin_api": True, "read_only": True},
        }
    return {
        "error": {
            "code": "invalid_time_filter",
            "message": "from/to must be valid ISO-8601 timestamps",
            "query": dict(query),
        },
        "metadata": {"admin_api": True, "read_only": True},
    }


def _not_found_response(resource: str, identifier: str) -> dict[str, Any]:
    return {
        "error": {
            "code": "not_found",
            "resource": resource,
            "identifier": identifier,
        },
        "metadata": {"admin_api": True, "read_only": True},
    }


def _with_admin_metadata(body: dict[str, Any]) -> dict[str, Any]:
    scrubbed = scrub_contract_payload(body)
    response = dict(scrubbed) if isinstance(scrubbed, dict) else {"data": scrubbed}
    metadata = (
        dict(response.get("metadata", {}))
        if isinstance(response.get("metadata"), Mapping)
        else {}
    )
    metadata["admin_api"] = True
    metadata["read_only"] = True
    response["metadata"] = metadata
    return response


__all__ = [
    "handle_sessions",
    "handle_tasks",
    "handle_feedback",
    "resolve_admin_max_limit",
    "ADMIN_API_MAX_LIMIT_ENV",
]
