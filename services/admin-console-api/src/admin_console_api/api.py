"""Main entry point for the Admin Console API.

Operational views (sessions/tasks/feedback/health/gates) remain GET-only via
``handle_admin_get``. Config mutate is explicit via ``handle_admin_put`` and
only accepts ``/config/*`` (ADM-03). Non-config PUT returns 405 after auth.
"""

from __future__ import annotations

import os
from typing import Any, Mapping
from urllib.parse import parse_qs

from inkstatute_operator_config import OperatorConfigStore
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
from .config_api import handle_config_get, handle_config_put
from .feedback import ThreadSafeFeedbackQueue
from .gates import handle_gates
from .health import handle_health
from .processes_api import handle_process_get, handle_process_put
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


def _authenticate_admin(
    path: str,
    query: str | Mapping[str, str] | None,
    headers: Mapping[str, str] | None,
    feature_flags: RuntimeFeatureFlags,
    env: Mapping[str, str] | None = None,
    rbac_secret: str | None = None,
) -> tuple[int, dict[str, Any]] | tuple[None, tuple[str, dict[str, str], Any, Any]]:
    """Shared admin_api flag + auth + RBAC + tenant pipeline.

    On success returns ``(None, (route_path, route_query, identity, tenant_filter))``.
    On failure returns ``(status_code, error_body)``.
    """
    try:
        feature_flags.require_enabled("admin_api_enabled")
    except RuntimeFeatureDisabledError:
        return 403, {
            "error": {
                "code": "admin_api_disabled",
                "message": "admin_api_enabled flag is False",
            },
        }

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
        from rbac import Identity, Role

        identity = Identity(role=Role.ADMIN, tenant_id="default")

    resolver = TenantScopeResolver(feature_flags=feature_flags)
    tenant_guard = TenantGuard(feature_flags=feature_flags)
    scope = resolver.resolve(
        TenantScopeRequestContext(identity=identity, headers=headers)
    )
    tenant_filter = tenant_guard.enforce(scope)
    return None, (route_path, route_query, identity, tenant_filter)


def handle_admin_get(
    path: str,
    query: str | Mapping[str, str] | None,
    headers: Mapping[str, str] | None,
    read_model: Any,
    feedback_queue: list[dict[str, Any]] | ThreadSafeFeedbackQueue | None,
    feature_flags: RuntimeFeatureFlags,
    env: Mapping[str, str] | None = None,
    rbac_secret: str | None = None,
    *,
    config_store: OperatorConfigStore | None = None,
    process_supervisor: Any = None,
) -> tuple[int, dict[str, Any]]:
    """Gate on feature flag + auth, then route to view / config handlers.

    Operational views remain read-only. ``/config/*`` is the config surface
    (``read_only=False`` metadata) served via ``handle_config_get``.
    """
    auth = _authenticate_admin(path, query, headers, feature_flags, env, rbac_secret)
    if auth[0] is not None:
        return auth  # type: ignore[return-value]
    route_path, route_query, _identity, tenant_filter = auth[1]

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

    if route_path == "/processes" or route_path.startswith("/processes/"):
        return handle_process_get(route_path, process_supervisor, feature_flags)

    if route_path == "/config" or route_path.startswith("/config/"):
        store = config_store if config_store is not None else OperatorConfigStore()
        return handle_config_get(route_path, store, feature_flags)

    return 404, not_found_response("route", route_path)


def handle_admin_put(
    path: str,
    body: Any,
    headers: Mapping[str, str] | None,
    feature_flags: RuntimeFeatureFlags,
    env: Mapping[str, str] | None = None,
    *,
    config_store: OperatorConfigStore | None = None,
    rbac_secret: str | None = None,
    read_model: Any = None,
    feedback_queue: list[dict[str, Any]] | ThreadSafeFeedbackQueue | None = None,
    process_supervisor: Any = None,
) -> tuple[int, dict[str, Any]]:
    """Auth then mutate ``/config/*`` only; operational PUT → 405 after auth.

    ``read_model`` / ``feedback_queue`` are accepted for call-site symmetry and
    unused (config store is the mutate authority).
    """
    del read_model, feedback_queue  # pipeline symmetry only

    auth = _authenticate_admin(path, None, headers, feature_flags, env, rbac_secret)
    if auth[0] is not None:
        return auth  # type: ignore[return-value]
    route_path, _route_query, _identity, _tenant_filter = auth[1]

    # Probe dispatch: exact /config/providers/probe before generic section PUT.
    if route_path == "/config/providers/probe":
        from .probe import handle_config_probe

        store = config_store if config_store is not None else OperatorConfigStore()
        return handle_config_probe(
            route_path,
            body,
            headers,
            feature_flags,
            env,
            config_store=store,
            rbac_secret=rbac_secret,
        )

    if route_path == "/config" or route_path.startswith("/config/"):
        store = config_store if config_store is not None else OperatorConfigStore()
        return handle_config_put(
            route_path,
            body,
            store,
            feature_flags,
            process_supervisor=process_supervisor,
        )

    if route_path == "/processes" or route_path.startswith("/processes/"):
        return handle_process_put(route_path, body, process_supervisor, feature_flags)

    return 405, {
        "error": {
            "code": "method_not_allowed",
            "message": "PUT is only allowed on /config/* or /processes/*",
        },
        "metadata": {
            "admin_api": True,
            "read_only": True,
        },
    }


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


__all__ = ["handle_admin_get", "handle_admin_put"]
