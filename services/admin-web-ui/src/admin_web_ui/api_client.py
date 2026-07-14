"""Admin API client — proxies requests to admin-console-api.

Reuses ``admin_console_api.handle_admin_get`` for reads and
``handle_admin_put`` for ``/config/*`` mutations (Channel Config SSR POST).
The Admin Web UI never makes direct database or read-model calls.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from rbac import Identity

# Type aliases for admin-console-api callables.
HandleAdminGet = Callable[..., tuple[int, dict[str, Any]]]
HandleAdminPut = Callable[..., tuple[int, dict[str, Any]]]


class AdminApiClient:
    """Proxy client that delegates to ``handle_admin_get`` / ``handle_admin_put``.

    The caller provides the same ``read_model``, ``feedback_queue``,
    ``feature_flags``, ``env``, ``rbac_secret``, and ``config_store`` that the
    admin-console-api uses. Auth headers are injected like the GET proxy.
    """

    def proxy(
        self,
        handle_admin_get: HandleAdminGet,
        path: str,
        identity: Identity,
        *,
        read_model: Any,
        feedback_queue: list[dict[str, Any]] | None = None,
        feature_flags: Any,
        env: Mapping[str, str] | None = None,
        rbac_secret: str | None = None,
        auth_header: str | None = None,
        config_store: Any = None,
        process_supervisor: Any = None,
        reports_aggregator: Any = None,
    ) -> tuple[int, dict[str, Any]]:
        """Proxy a GET request to ``handle_admin_get``.

        Returns ``(status_code, response_dict)``.
        """
        del identity  # auth is carried via Authorization header
        headers: dict[str, str] = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        kwargs: dict[str, Any] = {
            "path": path,
            "query": None,
            "headers": headers,
            "read_model": read_model,
            "feedback_queue": feedback_queue,
            "feature_flags": feature_flags,
            "env": env,
            "rbac_secret": rbac_secret,
        }
        if config_store is not None:
            kwargs["config_store"] = config_store
        if process_supervisor is not None:
            kwargs["process_supervisor"] = process_supervisor
        if reports_aggregator is not None:
            kwargs["reports_aggregator"] = reports_aggregator
        return handle_admin_get(**kwargs)

    def proxy_put(
        self,
        handle_admin_put: HandleAdminPut,
        path: str,
        body: Any,
        identity: Identity,
        *,
        feature_flags: Any,
        config_store: Any = None,
        env: Mapping[str, str] | None = None,
        rbac_secret: str | None = None,
        auth_header: str | None = None,
        process_supervisor: Any = None,
    ) -> tuple[int, dict[str, Any]]:
        """Proxy a PUT request to ``handle_admin_put`` (config mutate only).

        Returns ``(status_code, response_dict)``.
        """
        del identity  # auth is carried via Authorization header
        headers: dict[str, str] = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        kwargs: dict[str, Any] = {
            "path": path,
            "body": body,
            "headers": headers,
            "feature_flags": feature_flags,
            "env": env,
            "config_store": config_store,
            "rbac_secret": rbac_secret,
        }
        if process_supervisor is not None:
            kwargs["process_supervisor"] = process_supervisor
        return handle_admin_put(**kwargs)


__all__ = ["AdminApiClient", "HandleAdminGet", "HandleAdminPut"]
