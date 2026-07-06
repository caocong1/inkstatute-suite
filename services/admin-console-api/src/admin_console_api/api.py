"""Main entry point for the Admin Console API.

``handle_admin_get`` is the only public handler.  It gates on the
``admin_api_enabled`` feature flag, validates auth (static token when
``rbac_enabled=False`` or RBAC token with role+tenant claims when
``rbac_enabled=True``), and routes to read-only view handlers.  No
POST/PUT/DELETE handlers exist.
"""

from __future__ import annotations

import os
from typing import Any, Mapping
from urllib.parse import parse_qs

from conversation_read_view.privacy import scrub_contract_payload
from platform_runtime.feature_flags import (
    RuntimeFeatureDisabledError,
    RuntimeFeatureFlags,
)
from platform_runtime.tenant_scope import (
    TenantGuard,
    TenantScopeRequestContext,
    TenantScopeResolver,
)
from rbac import RbacGuard, resolve_identity

from .auth import check_auth_header, extract_auth_header, resolve_admin_token
from .gates import handle_gates
from .health import handle_health
from .views import handle_feedback, handle_sessions, handle_tasks

RBAC_TOKEN_SECRET_ENV = "RBAC_TOKEN_SECRET"


def _resolve_rbac_secret(
    env: Mapping[str, str] | None = None,
    rbac_secret: str | None = None,
) -> str | None:
    """Resolve the RBAC token signing secret.

    Explicit ``rbac_secret`` takes precedence; otherwise reads
    ``RBAC_TOKEN_SECRET`` from *env* (or ``os.environ``).
    """
    if rbac_secret is not None:
        return rbac_secret if rbac_secret else None
    source: Mapping[str, str] = env if env is not None else os.environ
    token = source.get(RBAC_TOKEN_SECRET_ENV, "")
    return token if token else None


def handle_admin_get(
    path: str,
    query: str | Mapping[str, str] | None,
    headers: Mapping[str, str] | None,
    read_model: Any,
    feedback_queue: list[dict[str, Any]] | None,
    feature_flags: RuntimeFeatureFlags,
    env: Mapping[str, str] | None = None,
    rbac_secret: str | None = None,
) -> tuple[int, dict[str, Any]]:
    """Gate on feature flag + auth, then route to read-only view handlers.

    Returns ``(status_code, response_dict)``.  Read-only — no mutations.

    When ``feature_flags.rbac_enabled`` is ``True``, the caller must present a
    valid short-lived RBAC token with role+tenant claims; ``RbacGuard`` then
    enforces role-based access per endpoint.  When ``False``, the v1.6
    static-token path runs unchanged.
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

    # Step 2 — auth (RBAC token or static token depending on flag)
    auth_header = extract_auth_header(headers)
    route_path, route_query = _split_path_query(path, query)
    identity = None

    if feature_flags.rbac_enabled:
        secret = _resolve_rbac_secret(env, rbac_secret)
        identity = resolve_identity(
            auth_header,
            rbac_secret=secret,
            static_token=resolve_admin_token(env),
            rbac_enabled=True,
        )
        if identity is None:
            return 401, {
                "error": {
                    "code": "unauthorized",
                    "message": "invalid or expired RBAC token",
                },
            }
        # Step 2b — RBAC role guard (default-deny)
        guard = RbacGuard()
        if not guard.check(identity.role, route_path):
            return 403, {
                "error": {
                    "code": "forbidden",
                    "message": "role not permitted for this endpoint",
                    "role": identity.role.value,
                },
            }
    else:
        # v1.6 static-token path (unchanged)
        expected_token = resolve_admin_token(env)
        if expected_token is None:
            return 403, {
                "error": {
                    "code": "admin_api_not_configured",
                    "message": "ADMIN_API_TOKEN env var is not set",
                },
            }
        if not check_auth_header(auth_header, expected_token):
            return 401, {
                "error": {
                    "code": "unauthorized",
                    "message": "missing or invalid Authorization header",
                },
            }
        # Synthetic identity for static-token path (tenant_id="default")
        from rbac import Identity, Role
        identity = Identity(role=Role.ADMIN, tenant_id="default")

    # Step 2c — tenant scope resolution + guard enforcement
    resolver = TenantScopeResolver(feature_flags=feature_flags)
    tenant_guard = TenantGuard(feature_flags=feature_flags)
    scope = resolver.resolve(TenantScopeRequestContext(identity=identity, headers=headers))
    tenant_filter = tenant_guard.enforce(scope)

    # Step 3 — route dispatch
    if route_path == "/sessions" or route_path.startswith("/sessions/"):
        return handle_sessions(route_path, route_query, read_model, tenant_filter=tenant_filter)

    if route_path == "/tasks" or route_path.startswith("/tasks/"):
        return handle_tasks(route_path, route_query, read_model, tenant_filter=tenant_filter)

    if route_path == "/feedback":
        return handle_feedback(route_query, read_model, feedback_queue, tenant_filter=tenant_filter)

    if route_path == "/health":
        return handle_health(feature_flags, read_model)

    if route_path == "/gates":
        return handle_gates()

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
