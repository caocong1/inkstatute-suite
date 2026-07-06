"""Admin Web UI HTTP server — stdlib http.server with RBAC + output boundary.

Request flow:
  Browser --HTTP--> AdminWebUiServer
    -> feature flag gate (admin_web_ui_enabled)
    -> RBAC token verify (rbac.verify_token) -> Identity(role, tenant_id)
    -> RbacGuard.check(role, endpoint)
    -> api_client.proxy(handle_admin_get, path, identity)
    -> dashboard.render(escaped_plaintext)
    -> response with CSP header: default-src 'self'
"""

from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler
from typing import Any, Callable, Mapping

from platform_runtime.feature_flags import (
    RuntimeFeatureDisabledError,
    RuntimeFeatureFlags,
)
from rbac import (
    Identity,
    RbacGuard,
    RbacTokenError,
    Role,
    resolve_identity,
    verify_token,
)

from .api_client import AdminApiClient, HandleAdminGet
from .boundary import AdminUiBoundary
from .dashboard import render_dashboard

CSP_HEADER = "default-src 'self'; script-src 'self'; style-src 'self'"

_BEARER_PREFIX = "Bearer "

_SECTION_MAP = {
    "/": "index",
    "/sessions": "sessions",
    "/tasks": "tasks",
    "/feedback": "feedback",
    "/health": "health",
    "/gates": "gates",
}


def _resolve_rbac_secret(
    env: Mapping[str, str] | None = None,
    rbac_secret: str | None = None,
) -> str | None:
    if rbac_secret is not None:
        return rbac_secret if rbac_secret else None
    source: Mapping[str, str] = env if env is not None else os.environ
    token = source.get("RBAC_TOKEN_SECRET", "")
    return token if token else None


def handle_admin_web_ui_request(
    path: str,
    headers: Mapping[str, str] | None,
    *,
    feature_flags: RuntimeFeatureFlags,
    handle_admin_get: HandleAdminGet,
    read_model: Any,
    feedback_queue: list[dict[str, Any]] | None = None,
    env: Mapping[str, str] | None = None,
    rbac_secret: str | None = None,
) -> tuple[int, str, dict[str, str]]:
    """Handle a single admin web UI GET request.

    Returns ``(status_code, html_body, response_headers)``.

    This function is the testable core — it does not depend on the
    BaseHTTPRequestHandler class and can be called directly from tests.
    """
    response_headers: dict[str, str] = {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Security-Policy": CSP_HEADER,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }

    # Step 1 — feature flag gate
    try:
        feature_flags.require_enabled("admin_web_ui_enabled")
    except RuntimeFeatureDisabledError:
        body = render_dashboard(
            "index",
            {"error": {"code": "admin_web_ui_disabled", "message": "admin_web_ui_enabled flag is False"}},
            identity=None,
        )
        return 503, body, response_headers

    # Step 2 — resolve route
    route_path = path.split("?")[0]
    section = _SECTION_MAP.get(route_path)
    if section is None:
        body = render_dashboard(
            "index",
            {"error": {"code": "not_found", "message": f"Unknown route: {route_path}"}},
            identity=None,
        )
        return 404, body, response_headers

    # Step 3 — RBAC auth
    auth_header = _extract_auth_header(headers)
    secret = _resolve_rbac_secret(env, rbac_secret)

    if feature_flags.rbac_enabled:
        identity = resolve_identity(
            auth_header,
            rbac_secret=secret,
            static_token=None,
            rbac_enabled=True,
        )
        if identity is None:
            body = render_dashboard(
                section,
                {"error": {"code": "unauthorized", "message": "Invalid or expired RBAC token"}},
                identity=None,
            )
            return 401, body, response_headers

        # Step 3b — RBAC role guard
        guard = RbacGuard()
        # Map web UI routes to admin API route prefixes for guard check
        guard_path = route_path if route_path != "/" else "/sessions"
        if not guard.check(identity.role, guard_path):
            body = render_dashboard(
                section,
                {"error": {
                    "code": "forbidden",
                    "message": f"Role '{identity.role.value}' not permitted for this endpoint",
                }},
                identity=identity,
            )
            return 403, body, response_headers
    else:
        # Static-token fallback — use admin-console-api's own auth
        identity = Identity(role=Role.ADMIN, tenant_id="default")

    # Step 4 — proxy to admin-console-api
    # Map dashboard index to /sessions for data retrieval
    api_path = "/sessions" if route_path == "/" else route_path

    client = AdminApiClient()
    status, api_data = client.proxy(
        handle_admin_get,
        api_path,
        identity,
        read_model=read_model,
        feedback_queue=feedback_queue,
        feature_flags=feature_flags,
        env=env,
        rbac_secret=secret,
        auth_header=auth_header,
    )

    # Step 5 — render dashboard
    boundary = AdminUiBoundary()
    body = render_dashboard(section, api_data, identity=identity, boundary=boundary)

    return status, body, response_headers


def _extract_auth_header(headers: Mapping[str, str] | None) -> str | None:
    """Extract the Authorization header from request headers (case-insensitive)."""
    if headers is None:
        return None
    for key, value in headers.items():
        if key.lower() == "authorization":
            return value
    return None


class AdminWebUiServer(BaseHTTPRequestHandler):
    """HTTP server handler for the Admin Web UI.

    Configuration is passed via server-level attributes set by the caller:

    - ``self.server.feature_flags`` — RuntimeFeatureFlags
    - ``self.server.handle_admin_get`` — handle_admin_get callable
    - ``self.server.read_model`` — ContractLogReadModel or compatible
    - ``self.server.feedback_queue`` — list[dict] or None
    - ``self.server.rbac_secret`` — str or None
    - ``self.server.env`` — Mapping[str, str] or None
    """

    def do_GET(self) -> None:
        status, body, headers = handle_admin_web_ui_request(
            self.path,
            dict(self.headers),
            feature_flags=self.server.feature_flags,  # type: ignore[attr-defined]
            handle_admin_get=self.server.handle_admin_get,  # type: ignore[attr-defined]
            read_model=self.server.read_model,  # type: ignore[attr-defined]
            feedback_queue=getattr(self.server, "feedback_queue", None),  # type: ignore[attr-defined]
            env=getattr(self.server, "env", None),  # type: ignore[attr-defined]
            rbac_secret=getattr(self.server, "rbac_secret", None),  # type: ignore[attr-defined]
        )
        encoded = body.encode("utf-8")
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # suppress default logging


__all__ = [
    "AdminWebUiServer",
    "handle_admin_web_ui_request",
    "CSP_HEADER",
]
