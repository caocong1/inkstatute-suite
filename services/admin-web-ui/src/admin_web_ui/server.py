"""Admin Web UI HTTP server — stdlib http.server with RBAC + output boundary.

Request flow:
  Browser --HTTP--> AdminWebUiServer
    -> feature flag gate (admin_web_ui_enabled)
    -> RBAC token verify (rbac.verify_token) -> Identity(role, tenant_id)
    -> RbacGuard.check(role, endpoint)
    -> api_client.proxy / proxy_put (handle_admin_get / handle_admin_put)
    -> dashboard / channels render (escaped plaintext)
    -> response with CSP header: default-src 'self'
"""

from __future__ import annotations

import os
import secrets
from http.server import BaseHTTPRequestHandler
from typing import Any, Mapping
from urllib.parse import parse_qs

from platform_runtime.feature_flags import (
    RuntimeFeatureDisabledError,
    RuntimeFeatureFlags,
)
from rbac import (
    Identity,
    RbacGuard,
    Role,
    resolve_identity,
)

from .api_client import AdminApiClient, HandleAdminGet, HandleAdminPut
from .boundary import AdminUiBoundary
from .channels import (
    ERROR_FLAG_OFF,
    ERROR_FORBIDDEN,
    ERROR_GENERIC,
    ERROR_VALIDATION,
    SUCCESS_FLASH,
    parse_channels_form,
    render_channels_page,
)
from .dashboard import render_dashboard

CSP_HEADER = "default-src 'self'; script-src 'self'; style-src 'self'"

_BEARER_PREFIX = "Bearer "

# Cap channels SSR POST bodies (WR-04) — form payloads are small refs-only.
MAX_CHANNELS_POST_BYTES = 64 * 1024

_SECTION_MAP = {
    "/": "index",
    "/sessions": "sessions",
    "/tasks": "tasks",
    "/feedback": "feedback",
    "/health": "health",
    "/gates": "gates",
    "/config/channels": "channels",
}

_CHANNELS_PATH = "/config/channels"


def _channels_post_body_usable(body: bytes | str | None) -> bool:
    """True when POST carries at least one qqbot./wecom. field (CR-01).

    Empty or marker-less bodies must not reach ``parse_channels_form`` → PUT,
    which would persist all-disabled empty refs and wipe stored credentials.
    """
    if body is None:
        return False
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
    if not text.strip():
        return False
    parsed = parse_qs(text, keep_blank_values=True)
    return any(
        key.startswith("qqbot.") or key.startswith("wecom.") for key in parsed
    )


def _merge_channel_metadata_from_current(
    section_payload: dict[str, Any],
    current_data: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Preserve API-set channel metadata the SSR form does not edit (WR-01)."""
    if not isinstance(current_data, Mapping):
        return section_payload
    merged = dict(section_payload)
    for key in ("qqbot", "wecom"):
        channel = merged.get(key)
        existing = current_data.get(key)
        if not isinstance(channel, dict) or not isinstance(existing, Mapping):
            continue
        meta = existing.get("metadata")
        if isinstance(meta, Mapping):
            channel = dict(channel)
            channel["metadata"] = dict(meta)
            merged[key] = channel
    return merged


def _resolve_rbac_secret(
    env: Mapping[str, str] | None = None,
    rbac_secret: str | None = None,
) -> str | None:
    if rbac_secret is not None:
        return rbac_secret if rbac_secret else None
    source: Mapping[str, str] = env if env is not None else os.environ
    token = source.get("RBAC_TOKEN_SECRET", "")
    return token if token else None


def _guard_path(route_path: str) -> str:
    """Map UI routes to RBAC matrix prefixes (``/config`` for channel config)."""
    if route_path == "/":
        return "/sessions"
    if route_path == _CHANNELS_PATH or route_path.startswith("/config/"):
        return "/config"
    return route_path


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
    method: str = "GET",
    body: bytes | str | None = None,
    handle_admin_put: HandleAdminPut | None = None,
    config_store: Any = None,
) -> tuple[int, str, dict[str, str]]:
    """Handle a single admin web UI request (GET, or POST on ``/config/channels``).

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

    http_method = (method or "GET").upper()

    # Step 1 — feature flag gate
    try:
        feature_flags.require_enabled("admin_web_ui_enabled")
    except RuntimeFeatureDisabledError:
        body_html = render_dashboard(
            "index",
            {"error": {"code": "admin_web_ui_disabled", "message": "admin_web_ui_enabled flag is False"}},
            identity=None,
        )
        return 503, body_html, response_headers

    # Step 2 — resolve route
    route_path = path.split("?")[0]
    section = _SECTION_MAP.get(route_path)
    if section is None:
        body_html = render_dashboard(
            "index",
            {"error": {"code": "not_found", "message": f"Unknown route: {route_path}"}},
            identity=None,
        )
        return 404, body_html, response_headers

    # Operational routes remain GET-only (POST only on /config/channels).
    if http_method == "POST" and route_path != _CHANNELS_PATH:
        body_html = render_dashboard(
            section if section != "channels" else "index",
            {"error": {"code": "method_not_allowed", "message": "POST is only allowed on /config/channels"}},
            identity=None,
        )
        return 405, body_html, response_headers

    if http_method not in ("GET", "POST"):
        body_html = render_dashboard(
            "index",
            {"error": {"code": "method_not_allowed", "message": f"Unsupported method: {http_method}"}},
            identity=None,
        )
        return 405, body_html, response_headers

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
            render_section = section if section != "channels" else "index"
            body_html = render_dashboard(
                render_section,
                {"error": {"code": "unauthorized", "message": "Invalid or expired RBAC token"}},
                identity=None,
            )
            return 401, body_html, response_headers

        # Step 3b — RBAC role guard
        guard = RbacGuard()
        if not guard.check(identity.role, _guard_path(route_path)):
            if section == "channels":
                body_html = render_channels_page(
                    {"error": {"code": "forbidden", "message": ERROR_FORBIDDEN}},
                    identity=identity,
                )
            else:
                body_html = render_dashboard(
                    section,
                    {"error": {
                        "code": "forbidden",
                        "message": f"Role '{identity.role.value}' not permitted for this endpoint",
                    }},
                    identity=identity,
                )
            return 403, body_html, response_headers
    else:
        # Static-token fallback — use admin-console-api's own auth
        identity = Identity(role=Role.ADMIN, tenant_id="default")

    client = AdminApiClient()
    boundary = AdminUiBoundary()

    # Step 4/5 — channels GET/POST
    if route_path == _CHANNELS_PATH:
        return _handle_channels(
            http_method=http_method,
            body=body,
            identity=identity,
            auth_header=auth_header,
            feature_flags=feature_flags,
            handle_admin_get=handle_admin_get,
            handle_admin_put=handle_admin_put,
            config_store=config_store,
            read_model=read_model,
            feedback_queue=feedback_queue,
            env=env,
            rbac_secret=secret,
            client=client,
            boundary=boundary,
            response_headers=response_headers,
        )

    # Step 4 — proxy operational GET to admin-console-api
    api_path = "/sessions" if route_path == "/" else route_path
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
        config_store=config_store,
    )

    # Step 5 — render dashboard
    body_html = render_dashboard(section, api_data, identity=identity, boundary=boundary)
    return status, body_html, response_headers


def _handle_channels(
    *,
    http_method: str,
    body: bytes | str | None,
    identity: Identity,
    auth_header: str | None,
    feature_flags: RuntimeFeatureFlags,
    handle_admin_get: HandleAdminGet,
    handle_admin_put: HandleAdminPut | None,
    config_store: Any,
    read_model: Any,
    feedback_queue: list[dict[str, Any]] | None,
    env: Mapping[str, str] | None,
    rbac_secret: str | None,
    client: AdminApiClient,
    boundary: AdminUiBoundary,
    response_headers: dict[str, str],
) -> tuple[int, str, dict[str, str]]:
    """GET renders dual-knob form; POST parses form and proxies handle_admin_put."""
    csrf_token = secrets.token_urlsafe(16)

    if http_method == "POST":
        if handle_admin_put is None:
            html_body = render_channels_page(
                {"error": {"code": "misconfigured", "message": ERROR_GENERIC}},
                identity=identity,
                boundary=boundary,
                csrf_token=csrf_token,
            )
            return 500, html_body, response_headers

        form_body = body if body is not None else b""
        if not _channels_post_body_usable(form_body):
            html_body = render_channels_page(
                {
                    "error": {
                        "code": "invalid_config",
                        "message": "Channel config POST body is empty or missing fields",
                    }
                },
                identity=identity,
                boundary=boundary,
                csrf_token=csrf_token,
                error_message=ERROR_VALIDATION,
            )
            return 400, html_body, response_headers

        section_payload = parse_channels_form(form_body)

        # Preserve channel metadata the form does not expose (WR-01).
        get_status, get_data = client.proxy(
            handle_admin_get,
            _CHANNELS_PATH,
            identity,
            read_model=read_model,
            feedback_queue=feedback_queue,
            feature_flags=feature_flags,
            env=env,
            rbac_secret=rbac_secret,
            auth_header=auth_header,
            config_store=config_store,
        )
        if get_status == 200 and isinstance(get_data, dict):
            current = get_data.get("data")
            if isinstance(current, Mapping):
                section_payload = _merge_channel_metadata_from_current(
                    section_payload, current
                )

        put_status, put_data = client.proxy_put(
            handle_admin_put,
            _CHANNELS_PATH,
            section_payload,
            identity,
            feature_flags=feature_flags,
            config_store=config_store,
            env=env,
            rbac_secret=rbac_secret,
            auth_header=auth_header,
        )

        if put_status == 200:
            html_body = render_channels_page(
                put_data,
                identity=identity,
                boundary=boundary,
                csrf_token=csrf_token,
                flash=SUCCESS_FLASH,
                flash_kind="success",
            )
            return 200, html_body, response_headers

        error = put_data.get("error") if isinstance(put_data, dict) else None
        code = error.get("code") if isinstance(error, dict) else None
        if code == "forbidden":
            err_msg = ERROR_FORBIDDEN
        elif code == "operator_config_disabled":
            err_msg = ERROR_FLAG_OFF
        elif code == "invalid_config":
            err_msg = ERROR_VALIDATION
        else:
            err_msg = ERROR_GENERIC

        # Re-fetch current config for form re-display when possible
        get_status, get_data = client.proxy(
            handle_admin_get,
            _CHANNELS_PATH,
            identity,
            read_model=read_model,
            feedback_queue=feedback_queue,
            feature_flags=feature_flags,
            env=env,
            rbac_secret=rbac_secret,
            auth_header=auth_header,
            config_store=config_store,
        )
        display = get_data if get_status == 200 else put_data
        # Preserve submitted host/refs on validation errors when PUT echoed data
        if isinstance(put_data, dict) and isinstance(put_data.get("data"), dict):
            display = put_data
        html_body = render_channels_page(
            display if isinstance(display, dict) else put_data,
            identity=identity,
            boundary=boundary,
            csrf_token=csrf_token,
            error_message=err_msg,
            read_only=code == "operator_config_disabled",
        )
        return put_status, html_body, response_headers

    # GET
    status, api_data = client.proxy(
        handle_admin_get,
        _CHANNELS_PATH,
        identity,
        read_model=read_model,
        feedback_queue=feedback_queue,
        feature_flags=feature_flags,
        env=env,
        rbac_secret=rbac_secret,
        auth_header=auth_header,
        config_store=config_store,
    )
    html_body = render_channels_page(
        api_data,
        identity=identity,
        boundary=boundary,
        csrf_token=csrf_token,
    )
    return status, html_body, response_headers


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
    - ``self.server.handle_admin_put`` — handle_admin_put callable (optional)
    - ``self.server.config_store`` — OperatorConfigStore or compatible (optional)
    - ``self.server.read_model`` — ContractLogReadModel or compatible
    - ``self.server.feedback_queue`` — list[dict] or None
    - ``self.server.rbac_secret`` — str or None
    - ``self.server.env`` — Mapping[str, str] or None
    """

    def do_GET(self) -> None:
        self._dispatch("GET", body=None)

    def do_POST(self) -> None:
        length_raw = self.headers.get("Content-Length", "0")
        try:
            length = int(length_raw)
        except ValueError:
            length = 0
        if length < 0 or length > MAX_CHANNELS_POST_BYTES:
            # Reject oversized/negative Content-Length without allocating (WR-04).
            body_html = (
                "<!DOCTYPE html><html><body>"
                "<p class=\"error\">Request body too large</p>"
                "</body></html>"
            )
            encoded = body_html.encode("utf-8")
            self.send_response(413)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy", CSP_HEADER)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return
        raw = self.rfile.read(length) if length > 0 else b""
        self._dispatch("POST", body=raw)

    def _dispatch(self, method: str, body: bytes | None) -> None:
        status, html_body, headers = handle_admin_web_ui_request(
            self.path,
            dict(self.headers),
            feature_flags=self.server.feature_flags,  # type: ignore[attr-defined]
            handle_admin_get=self.server.handle_admin_get,  # type: ignore[attr-defined]
            read_model=self.server.read_model,  # type: ignore[attr-defined]
            feedback_queue=getattr(self.server, "feedback_queue", None),  # type: ignore[attr-defined]
            env=getattr(self.server, "env", None),  # type: ignore[attr-defined]
            rbac_secret=getattr(self.server, "rbac_secret", None),  # type: ignore[attr-defined]
            method=method,
            body=body,
            handle_admin_put=getattr(self.server, "handle_admin_put", None),  # type: ignore[attr-defined]
            config_store=getattr(self.server, "config_store", None),  # type: ignore[attr-defined]
        )
        encoded = html_body.encode("utf-8")
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
    "MAX_CHANNELS_POST_BYTES",
]
