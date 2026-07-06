"""Admin API client — proxies read-only requests to admin-console-api.

Reuses ``admin_console_api.handle_admin_get`` for all data retrieval.
The Admin Web UI never makes direct database or read-model calls.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from rbac import Identity

# Type alias for the handle_admin_get callable signature.
HandleAdminGet = Callable[..., tuple[int, dict[str, Any]]]


class AdminApiClient:
    """Proxy client that delegates to ``handle_admin_get``.

    The caller provides the same ``read_model``, ``feedback_queue``,
    ``feature_flags``, ``env``, and ``rbac_secret`` that the admin-console-api
    uses. The client constructs the auth header from the resolved identity's
    token and passes it through.
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
    ) -> tuple[int, dict[str, Any]]:
        """Proxy a GET request to ``handle_admin_get``.

        Returns ``(status_code, response_dict)``.
        """
        headers: dict[str, str] = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        return handle_admin_get(
            path=path,
            query=None,
            headers=headers,
            read_model=read_model,
            feedback_queue=feedback_queue,
            feature_flags=feature_flags,
            env=env,
            rbac_secret=rbac_secret,
        )


__all__ = ["AdminApiClient", "HandleAdminGet"]
