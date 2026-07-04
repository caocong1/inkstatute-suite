"""Main entry point for the Admin Console API.

``handle_admin_get`` is the only public handler.  It gates on the
``admin_api_enabled`` feature flag, validates a static token from env, and
routes to read-only view handlers.  No POST/PUT/DELETE handlers exist.
"""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import parse_qs

from conversation_read_view.privacy import scrub_contract_payload
from platform_runtime.feature_flags import (
    RuntimeFeatureDisabledError,
    RuntimeFeatureFlags,
)

from .auth import check_auth_header, extract_auth_header, resolve_admin_token
from .views import handle_feedback, handle_sessions, handle_tasks


def handle_admin_get(
    path: str,
    query: str | Mapping[str, str] | None,
    headers: Mapping[str, str] | None,
    read_model: Any,
    feedback_queue: list[dict[str, Any]] | None,
    feature_flags: RuntimeFeatureFlags,
    env: Mapping[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Gate on feature flag + auth, then route to read-only view handlers.

    Returns ``(status_code, response_dict)``.  Read-only — no mutations.
    """

    # Step 1 — feature flag gate
    try:
        feature_flags.require_enabled("admin_api_enabled")
    except RuntimeFeatureDisabledError:
        return 403, {
            "error": {
                "code": "admin_api_disabled",
                "message": "admin_api_enabled flag is False",
            },
        }

    # Step 2 — token check
    expected_token = resolve_admin_token(env)
    if expected_token is None:
        return 403, {
            "error": {
                "code": "admin_api_not_configured",
                "message": "ADMIN_API_TOKEN env var is not set",
            },
        }

    # Step 3 — auth header check
    auth_header = extract_auth_header(headers)
    if not check_auth_header(auth_header, expected_token):
        return 401, {
            "error": {
                "code": "unauthorized",
                "message": "missing or invalid Authorization header",
            },
        }

    # Step 4 — route dispatch
    route_path, route_query = _split_path_query(path, query)

    if route_path == "/sessions" or route_path.startswith("/sessions/"):
        return handle_sessions(route_path, route_query, read_model)

    if route_path == "/tasks" or route_path.startswith("/tasks/"):
        return handle_tasks(route_path, route_query, read_model)

    if route_path == "/feedback":
        return handle_feedback(route_query, read_model, feedback_queue)

    if route_path == "/health":
        return 501, {
            "error": {
                "code": "not_implemented",
                "message": "health views are implemented in Wave 2",
            },
        }

    if route_path == "/gates":
        return 501, {
            "error": {
                "code": "not_implemented",
                "message": "gate views are implemented in Wave 2",
            },
        }

    return 404, not_found_response("route", route_path)


def _split_path_query(
    path: str,
    query: str | Mapping[str, str] | None,
) -> tuple[str, dict[str, str]]:
    if "?" in path:
        route_path, inline_query = path.split("?", 1)
        merged = parse_query_string(inline_query)
        merged.update(parse_query_string(query))
        return route_path, merged
    return path, parse_query_string(query)


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
            "admin_api": True,
            "read_only": True,
        },
    }


__all__ = ["handle_admin_get"]
