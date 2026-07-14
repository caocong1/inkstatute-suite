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
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from typing import Any, Mapping
from urllib.parse import parse_qs

from platform_runtime.feature_flags import (
    RuntimeFeatureDisabledError,
    RuntimeFeatureFlags,
)
from rbac import (
    DEFAULT_SESSION_TTL_SECONDS,
    Identity,
    RbacGuard,
    Role,
    SESSION_COOKIE_NAME,
    InMemorySessionStore,
    issue_token,
    parse_cookie_header,
    resolve_identity,
)

from .api_client import AdminApiClient, HandleAdminGet, HandleAdminPut
from .audit import render_audit_page, render_trace_page
from .auth import (
    ANONYMOUS_IDENTITY,
    LOGIN_PATH,
    LOGOUT_PATH,
    check_credentials,
    handle_login_post,
    handle_logout_post,
    render_login_page,
    render_logout_page,
)
from .boundary import AdminUiBoundary
from .catalog import (
    ERROR_FLAG_OFF as CATALOG_ERROR_FLAG_OFF,
    ERROR_FORBIDDEN as CATALOG_ERROR_FORBIDDEN,
    ERROR_GENERIC as CATALOG_ERROR_GENERIC,
    ERROR_VALIDATION as CATALOG_ERROR_VALIDATION,
    SUCCESS_FLASH as CATALOG_SUCCESS_FLASH,
    parse_catalog_form,
    render_catalog_page,
)
from .channels import (
    ERROR_CSRF,
    ERROR_FLAG_OFF,
    ERROR_FORBIDDEN,
    ERROR_GENERIC,
    ERROR_VALIDATION,
    SUCCESS_FLASH,
    parse_channels_form,
    render_channels_page,
)
from .csrf import issue_csrf_token, validate_csrf_token
from .dashboard import render_dashboard, render_error_page
from .logs import render_logs_page
from .processes import (
    parse_processes_form,
    render_processes_page,
)
from .providers import (
    ERROR_FLAG_OFF as PROVIDERS_ERROR_FLAG_OFF,
    ERROR_FORBIDDEN as PROVIDERS_ERROR_FORBIDDEN,
    ERROR_GENERIC as PROVIDERS_ERROR_GENERIC,
    ERROR_VALIDATION as PROVIDERS_ERROR_VALIDATION,
    SUCCESS_FLASH as PROVIDERS_SUCCESS_FLASH,
    parse_providers_form,
    render_providers_page,
)
from .vision import (
    ERROR_FLAG_OFF as VISION_ERROR_FLAG_OFF,
    ERROR_FORBIDDEN as VISION_ERROR_FORBIDDEN,
    ERROR_GENERIC as VISION_ERROR_GENERIC,
    ERROR_VALIDATION as VISION_ERROR_VALIDATION,
    SUCCESS_FLASH as VISION_SUCCESS_FLASH,
    parse_vision_form,
    render_vision_page,
)

CSP_HEADER = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"

_BEARER_PREFIX = "Bearer "

# Cap config SSR POST bodies (WR-04) — form payloads are small refs-only.
MAX_CHANNELS_POST_BYTES = 64 * 1024

_SECTION_MAP = {
    "/": "index",
    "/sessions": "sessions",
    "/tasks": "tasks",
    "/feedback": "feedback",
    "/health": "health",
    "/gates": "gates",
    "/reports": "reports",
    "/logs": "logs",
    "/audit": "audit",
    "/processes": "processes",
    "/config/channels": "channels",
    "/config/providers": "providers",
    "/config/providers/probe": "providers_probe",
    "/config/catalog": "catalog",
    "/config/vision": "vision",
}

_CHANNELS_PATH = "/config/channels"
_PROVIDERS_PATH = "/config/providers"
_PROBE_PATH = "/config/providers/probe"
_CATALOG_PATH = "/config/catalog"
_VISION_PATH = "/config/vision"
_PROCESSES_PATH = "/processes"
_REPORTS_PATH = "/reports"
_LOGS_PATH = "/logs"
_AUDIT_PATH = "/audit"
_LOGIN_PATH = LOGIN_PATH
_LOGOUT_PATH = LOGOUT_PATH

# Routes that accept POST (all other routes remain GET-only).
_POST_ROUTES = frozenset({
    _CHANNELS_PATH,
    _PROVIDERS_PATH,
    _PROBE_PATH,
    _CATALOG_PATH,
    _VISION_PATH,
    _PROCESSES_PATH,
})


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
    if route_path == _PROCESSES_PATH or route_path.startswith("/processes/"):
        return "/config"
    if route_path == _LOGS_PATH or route_path.startswith("/logs/"):
        return "/logs"
    if route_path == _AUDIT_PATH or route_path.startswith("/audit/"):
        return "/audit"
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
    handle_config_probe: Any = None,
    process_supervisor: Any = None,
    reports_aggregator: Any = None,
    log_reader: Any = None,
    session_store: Any = None,
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

    # Resolve the RBAC secret early so it is available for login/logout and
    # the standard auth flow.
    secret = _resolve_rbac_secret(env, rbac_secret)

    # Step 1b — login/logout routes (handled before standard RBAC auth).
    route_path = path.split("?")[0]
    if route_path == _LOGIN_PATH:
        return _handle_login(
            http_method=http_method,
            body=body,
            headers=headers,
            feature_flags=feature_flags,
            env=env,
            rbac_secret=secret,
            session_store=session_store,
            response_headers=response_headers,
        )
    if route_path == _LOGOUT_PATH:
        return _handle_logout(
            http_method=http_method,
            body=body,
            headers=headers,
            feature_flags=feature_flags,
            env=env,
            rbac_secret=secret,
            session_store=session_store,
            response_headers=response_headers,
        )

    # Step 2 — resolve route
    section = _SECTION_MAP.get(route_path)
    # /logs/<source> subpaths map to the "logs" section.
    if section is None and (route_path == _LOGS_PATH or route_path.startswith("/logs/")):
        section = "logs"
    if section is None and (route_path == _AUDIT_PATH or route_path.startswith("/audit/")):
        section = "audit"
    if section is None:
        body_html = render_error_page(
            404,
            "Not Found",
            f"Unknown route: {route_path}",
            identity=None,
        )
        return 404, body_html, response_headers

    # Operational routes remain GET-only (POST only on config routes).
    if http_method == "POST" and route_path not in _POST_ROUTES:
        body_html = render_dashboard(
            section if section not in ("channels", "providers", "catalog", "providers_probe", "vision") else "index",
            {"error": {"code": "method_not_allowed", "message": "POST is only allowed on config routes"}},
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

    if feature_flags.rbac_enabled:
        cookie_header = _extract_cookie_header(headers)
        session_cookie = parse_cookie_header(cookie_header, SESSION_COOKIE_NAME)
        identity = resolve_identity(
            auth_header,
            rbac_secret=secret,
            static_token=None,
            rbac_enabled=True,
            session_cookie=session_cookie,
            session_store=session_store,
        )
        if identity is None:
            render_section = section if section not in ("channels", "providers", "catalog", "providers_probe", "vision") else "index"
            body_html = render_dashboard(
                render_section,
                {"error": {"code": "unauthorized", "message": "Invalid or expired RBAC token"}},
                identity=None,
            )
            return 401, body_html, response_headers

        # When the caller authenticated via session cookie (no Bearer header),
        # mint a short-lived Bearer token so the downstream admin-console-api
        # auth check succeeds.  The API does its own resolve_identity on the
        # Bearer header — cookie auth is admin-web-ui-only.
        if auth_header is None and secret is not None:
            auth_header = "Bearer " + issue_token(
                secret, role=identity.role, tenant_id=identity.tenant_id
            )

        # Step 3b — RBAC role guard
        guard = RbacGuard()
        if not guard.check(identity.role, _guard_path(route_path)):
            if section == "channels":
                body_html = render_channels_page(
                    {"error": {"code": "forbidden", "message": ERROR_FORBIDDEN}},
                    identity=identity,
                )
            elif section == "providers" or section == "providers_probe":
                body_html = render_providers_page(
                    {"error": {"code": "forbidden", "message": PROVIDERS_ERROR_FORBIDDEN}},
                    identity=identity,
                )
            elif section == "catalog":
                body_html = render_catalog_page(
                    {"error": {"code": "forbidden", "message": CATALOG_ERROR_FORBIDDEN}},
                    identity=identity,
                )
            elif section == "vision":
                body_html = render_vision_page(
                    {"error": {"code": "forbidden", "message": VISION_ERROR_FORBIDDEN}},
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

    # Step 4/5 — providers GET/POST + probe POST
    if route_path == _PROVIDERS_PATH:
        return _handle_providers(
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

    if route_path == _PROBE_PATH:
        return _handle_probe(
            body=body,
            identity=identity,
            auth_header=auth_header,
            feature_flags=feature_flags,
            handle_admin_get=handle_admin_get,
            handle_config_probe=handle_config_probe,
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

    # Step 4/5 — catalog GET/POST
    if route_path == _CATALOG_PATH:
        return _handle_catalog(
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

    # Step 4/5 — vision GET/POST
    if route_path == _VISION_PATH:
        return _handle_vision(
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

    # Step 4 — process orchestration
    if route_path == _PROCESSES_PATH:
        return _handle_processes(
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
            process_supervisor=process_supervisor,
            client=client,
            boundary=boundary,
            response_headers=response_headers,
        )

    # Step 4 — log viewing
    if route_path == _LOGS_PATH or route_path.startswith("/logs/"):
        return _handle_logs(
            http_method=http_method,
            identity=identity,
            auth_header=auth_header,
            feature_flags=feature_flags,
            handle_admin_get=handle_admin_get,
            read_model=read_model,
            feedback_queue=feedback_queue,
            env=env,
            rbac_secret=secret,
            log_reader=log_reader,
            client=client,
            boundary=boundary,
            response_headers=response_headers,
            path=path,
        )

    # Step 4 — contract event audit
    if route_path == _AUDIT_PATH or route_path.startswith("/audit/"):
        return _handle_audit(
            http_method=http_method,
            identity=identity,
            auth_header=auth_header,
            feature_flags=feature_flags,
            handle_admin_get=handle_admin_get,
            read_model=read_model,
            feedback_queue=feedback_queue,
            env=env,
            rbac_secret=secret,
            client=client,
            boundary=boundary,
            response_headers=response_headers,
            path=path,
        )

    # Step 4 — proxy operational GET to admin-console-api
    # Preserve the original query string (e.g. ?window=today) so it reaches
    # handle_admin_get for routes like /reports that accept query params.
    if route_path == "/":
        api_path = "/sessions"
    else:
        api_path = path
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
        process_supervisor=process_supervisor,
        reports_aggregator=reports_aggregator,
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
    csrf_token: str | None = None,
) -> tuple[int, str, dict[str, str]]:
    """GET renders dual-knob form; POST validates CSRF and proxies handle_admin_put."""
    del csrf_token  # route issues and validates its own signed token
    save_token = issue_csrf_token(identity, _CHANNELS_PATH, signing_key=rbac_secret)

    if http_method == "POST":
        if handle_admin_put is None:
            html_body = render_channels_page(
                {"error": {"code": "misconfigured", "message": ERROR_GENERIC}},
                identity=identity,
                boundary=boundary,
                csrf_token=save_token,
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
                csrf_token=save_token,
                error_message=ERROR_VALIDATION,
            )
            return 400, html_body, response_headers

        valid, form_map = _validate_post_csrf(
            form_body, identity, _CHANNELS_PATH, rbac_secret=rbac_secret
        )
        if not valid:
            html_body = render_channels_page(
                {"error": {"code": "forbidden", "message": ERROR_CSRF}},
                identity=identity,
                boundary=boundary,
                csrf_token=save_token,
                error_message=ERROR_CSRF,
            )
            return 403, html_body, response_headers

        assert form_map is not None  # validated above
        section_payload = parse_channels_form(form_map)

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
                csrf_token=save_token,
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
            csrf_token=save_token,
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
        csrf_token=save_token,
    )
    return status, html_body, response_headers


def _extract_csrf_token(form_map: Mapping[str, Any]) -> str | None:
    """Extract exactly one non-empty csrf_token from a parsed form map."""
    raw = form_map.get("csrf_token")
    if raw is None:
        return None
    if isinstance(raw, list):
        values = [str(v).strip() for v in raw if str(v).strip()]
        if len(values) != 1:
            return None
        return values[0]
    text = str(raw).strip()
    return text if text else None


def _validate_post_csrf(
    body: bytes | str | None,
    identity: Identity,
    route: str,
    *,
    rbac_secret: str | None,
) -> tuple[bool, dict[str, Any] | None]:
    """Parse form body, extract csrf_token, and validate against the exact route.

    Returns ``(valid, form_map)``. ``form_map`` is the parsed form for downstream
    use when valid, or ``None`` when CSRF failed (no proxy should proceed).
    """
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body or "")
    form_map = parse_qs(text, keep_blank_values=True)
    token = _extract_csrf_token(form_map)
    if token is None:
        return False, None
    if not validate_csrf_token(token, identity, route, signing_key=rbac_secret):
        return False, None
    return True, form_map


def _vendor_profiles_from_metadata(
    api_data: Mapping[str, Any] | None,
) -> dict[str, dict[str, str]]:
    """Build vendor_id → profile dict from API providers metadata."""
    profiles: dict[str, dict[str, str]] = {}
    if not isinstance(api_data, Mapping):
        return profiles
    metadata = api_data.get("metadata")
    if not isinstance(metadata, Mapping):
        return profiles
    raw = metadata.get("builtin_vendor_profiles")
    if not isinstance(raw, list):
        return profiles
    for entry in raw:
        if isinstance(entry, Mapping):
            vid = entry.get("vendor_id")
            if isinstance(vid, str):
                profiles[vid] = {
                    "vendor_id": vid,
                    "api_base_url": str(entry.get("api_base_url", "")),
                    "default_key_ref_env": str(entry.get("default_key_ref_env", "")),
                }
    return profiles


def _merge_provider_metadata(
    parsed: list[dict[str, Any]],
    current_data: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Preserve API-set provider metadata the SSR form does not edit (WR-01)."""
    if not isinstance(current_data, Mapping):
        return parsed
    stored: dict[str, dict[str, Any]] = {}
    data = current_data.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, Mapping):
                pid = item.get("provider_id")
                if isinstance(pid, str):
                    stored[pid] = dict(item)
    merged: list[dict[str, Any]] = []
    for provider in parsed:
        pid = provider.get("provider_id")
        if pid and pid in stored:
            existing = stored[pid]
            meta = existing.get("metadata")
            if isinstance(meta, Mapping):
                provider = dict(provider)
                provider["metadata"] = dict(meta)
        merged.append(provider)
    return merged


def _handle_providers(
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
    """GET renders provider registry; POST validates CSRF then proxies list PUT."""
    save_token = issue_csrf_token(identity, _PROVIDERS_PATH, signing_key=rbac_secret)
    probe_token = issue_csrf_token(identity, _PROBE_PATH, signing_key=rbac_secret)

    if http_method == "POST":
        valid, form_map = _validate_post_csrf(
            body, identity, _PROVIDERS_PATH, rbac_secret=rbac_secret
        )
        if not valid:
            html_body = render_providers_page(
                {"error": {"code": "forbidden", "message": PROVIDERS_ERROR_FORBIDDEN}},
                identity=identity,
                csrf_token=save_token,
                probe_csrf_token=probe_token,
            )
            return 403, html_body, response_headers

        if handle_admin_put is None:
            html_body = render_providers_page(
                {"error": {"code": "misconfigured", "message": PROVIDERS_ERROR_GENERIC}},
                identity=identity,
                csrf_token=save_token,
                probe_csrf_token=probe_token,
            )
            return 500, html_body, response_headers

        assert form_map is not None  # validated above

        # Fetch current data AFTER CSRF passes (T-76-27: merge metadata only post-CSRF).
        get_status, get_data = client.proxy(
            handle_admin_get,
            _PROVIDERS_PATH,
            identity,
            read_model=read_model,
            feedback_queue=feedback_queue,
            feature_flags=feature_flags,
            env=env,
            rbac_secret=rbac_secret,
            auth_header=auth_header,
            config_store=config_store,
        )
        profiles = _vendor_profiles_from_metadata(get_data if get_status == 200 else None)
        parsed = parse_providers_form(form_map, vendor_profiles=profiles)
        if not parsed:
            html_body = render_providers_page(
                get_data if get_status == 200 else {"error": {"code": "invalid_config", "message": PROVIDERS_ERROR_VALIDATION}},
                identity=identity,
                csrf_token=save_token,
                probe_csrf_token=probe_token,
                error_message=PROVIDERS_ERROR_VALIDATION,
            )
            return 400, html_body, response_headers

        merged = _merge_provider_metadata(parsed, get_data if get_status == 200 else None)

        put_status, put_data = client.proxy_put(
            handle_admin_put,
            _PROVIDERS_PATH,
            merged,
            identity,
            feature_flags=feature_flags,
            config_store=config_store,
            env=env,
            rbac_secret=rbac_secret,
            auth_header=auth_header,
        )

        if put_status == 200:
            html_body = render_providers_page(
                put_data,
                identity=identity,
                csrf_token=save_token,
                probe_csrf_token=probe_token,
                flash=PROVIDERS_SUCCESS_FLASH,
                flash_kind="success",
            )
            return 200, html_body, response_headers

        error = put_data.get("error") if isinstance(put_data, dict) else None
        code = error.get("code") if isinstance(error, dict) else None
        if code == "forbidden":
            err_msg = PROVIDERS_ERROR_FORBIDDEN
        elif code == "operator_config_disabled":
            err_msg = PROVIDERS_ERROR_FLAG_OFF
        elif code == "invalid_config":
            err_msg = PROVIDERS_ERROR_VALIDATION
        else:
            err_msg = PROVIDERS_ERROR_GENERIC

        display = get_data if get_status == 200 else put_data
        if isinstance(put_data, dict) and isinstance(put_data.get("data"), list):
            display = put_data
        html_body = render_providers_page(
            display if isinstance(display, dict) else put_data,
            identity=identity,
            csrf_token=save_token,
            probe_csrf_token=probe_token,
            error_message=err_msg,
            read_only=code == "operator_config_disabled",
        )
        return put_status, html_body, response_headers

    # GET
    status, api_data = client.proxy(
        handle_admin_get,
        _PROVIDERS_PATH,
        identity,
        read_model=read_model,
        feedback_queue=feedback_queue,
        feature_flags=feature_flags,
        env=env,
        rbac_secret=rbac_secret,
        auth_header=auth_header,
        config_store=config_store,
    )
    html_body = render_providers_page(
        api_data,
        identity=identity,
        csrf_token=save_token,
        probe_csrf_token=probe_token,
    )
    return status, html_body, response_headers


def _handle_probe(
    *,
    body: bytes | str | None,
    identity: Identity,
    auth_header: str | None,
    feature_flags: RuntimeFeatureFlags,
    handle_admin_get: HandleAdminGet,
    handle_config_probe: Any,
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
    """POST /config/providers/probe — validate CSRF, proxy stored-target probe, re-render."""
    save_token = issue_csrf_token(identity, _PROVIDERS_PATH, signing_key=rbac_secret)
    probe_token = issue_csrf_token(identity, _PROBE_PATH, signing_key=rbac_secret)

    valid, form_map = _validate_post_csrf(
        body, identity, _PROBE_PATH, rbac_secret=rbac_secret
    )
    if not valid:
        # Parse return_to without trusting the CSRF token so the correct page is
        # re-rendered for a vision-probe CSRF failure.
        text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body or "")
        raw_form = parse_qs(text, keep_blank_values=True)
        raw_return_to = raw_form.get("return_to")
        if isinstance(raw_return_to, list):
            return_to = raw_return_to[0] if raw_return_to else ""
        else:
            return_to = str(raw_return_to or "")
        return_to = return_to.strip()
        if return_to == "vision":
            vision_save_token = issue_csrf_token(identity, _VISION_PATH, signing_key=rbac_secret)
            html_body = render_vision_page(
                {"error": {"code": "forbidden", "message": VISION_ERROR_FORBIDDEN}},
                identity=identity,
                csrf_token=vision_save_token,
                probe_csrf_token=probe_token,
            )
        else:
            html_body = render_providers_page(
                {"error": {"code": "forbidden", "message": PROVIDERS_ERROR_FORBIDDEN}},
                identity=identity,
                csrf_token=save_token,
                probe_csrf_token=probe_token,
            )
        return 403, html_body, response_headers

    assert form_map is not None  # validated above
    # Extract target (main or vision) — the only field besides csrf_token.
    raw_target = form_map.get("target")
    if isinstance(raw_target, list):
        target = raw_target[0] if raw_target else ""
    else:
        target = str(raw_target or "")
    target = target.strip()
    if target not in ("main", "vision"):
        html_body = render_providers_page(
            {"error": {"code": "invalid_config", "message": PROVIDERS_ERROR_VALIDATION}},
            identity=identity,
            csrf_token=save_token,
            probe_csrf_token=probe_token,
        )
        return 400, html_body, response_headers

    # Extract optional return_to (vision probe form re-renders the vision page).
    raw_return_to = form_map.get("return_to")
    if isinstance(raw_return_to, list):
        return_to = raw_return_to[0] if raw_return_to else ""
    else:
        return_to = str(raw_return_to or "")
    return_to = return_to.strip()

    # Proxy the probe — prefer dedicated handle_config_probe, fall back to handle_admin_put.
    probe_body: dict[str, Any] = {"target": target}
    if handle_config_probe is not None:
        probe_status, probe_data = handle_config_probe(
            _PROBE_PATH,
            probe_body,
            {"Authorization": auth_header} if auth_header else {},
            feature_flags,
            env,
            config_store=config_store,
            rbac_secret=rbac_secret,
        )
    elif handle_admin_put is not None:
        probe_status, probe_data = client.proxy_put(
            handle_admin_put,
            _PROBE_PATH,
            probe_body,
            identity,
            feature_flags=feature_flags,
            config_store=config_store,
            env=env,
            rbac_secret=rbac_secret,
            auth_header=auth_header,
        )
    else:
        html_body = render_providers_page(
            {"error": {"code": "misconfigured", "message": PROVIDERS_ERROR_GENERIC}},
            identity=identity,
            csrf_token=save_token,
            probe_csrf_token=probe_token,
        )
        return 500, html_body, response_headers

    probe_result = None
    if isinstance(probe_data, dict):
        probe_result = probe_data.get("data")
        if not isinstance(probe_result, Mapping):
            probe_result = None

    # When the probe handler returns an error (non-200), show a generic failure
    # banner so the operator sees feedback instead of a silently blank page.
    if probe_status != 200 or probe_result is None:
        probe_result = {"status": "fail", "target": target}

    if return_to == "vision":
        # Re-GET vision + catalog + provider data for the vision page re-render.
        vision_save_token = issue_csrf_token(identity, _VISION_PATH, signing_key=rbac_secret)
        display = _vision_display(
            client,
            handle_admin_get,
            identity,
            auth_header,
            feature_flags,
            read_model,
            feedback_queue,
            env,
            rbac_secret,
            config_store,
        )
        display_data = display if isinstance(display, dict) else {"error": {"code": "probe_error", "message": VISION_ERROR_GENERIC}}
        html_body = render_vision_page(
            display_data,
            identity=identity,
            csrf_token=vision_save_token,
            probe_csrf_token=probe_token,
            probe_result=probe_result,
        )
        return 200, html_body, response_headers

    # Re-GET provider data for the providers page re-render.
    get_status, get_data = client.proxy(
        handle_admin_get,
        _PROVIDERS_PATH,
        identity,
        read_model=read_model,
        feedback_queue=feedback_queue,
        feature_flags=feature_flags,
        env=env,
        rbac_secret=rbac_secret,
        auth_header=auth_header,
        config_store=config_store,
    )

    display = get_data if get_status == 200 else {"error": {"code": "probe_error", "message": PROVIDERS_ERROR_GENERIC}}
    html_body = render_providers_page(
        display,
        identity=identity,
        csrf_token=save_token,
        probe_csrf_token=probe_token,
        probe_result=probe_result,
    )
    return 200, html_body, response_headers


def _handle_catalog(
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
    """GET renders model catalog; POST validates CSRF then proxies object PUT."""
    save_token = issue_csrf_token(identity, _CATALOG_PATH, signing_key=rbac_secret)

    if http_method == "POST":
        valid, form_map = _validate_post_csrf(
            body, identity, _CATALOG_PATH, rbac_secret=rbac_secret
        )
        if not valid:
            html_body = render_catalog_page(
                {"error": {"code": "forbidden", "message": CATALOG_ERROR_FORBIDDEN}},
                identity=identity,
                csrf_token=save_token,
            )
            return 403, html_body, response_headers

        if handle_admin_put is None:
            html_body = render_catalog_page(
                {"error": {"code": "misconfigured", "message": CATALOG_ERROR_GENERIC}},
                identity=identity,
                csrf_token=save_token,
            )
            return 500, html_body, response_headers

        assert form_map is not None  # validated above
        section_payload = parse_catalog_form(form_map)

        put_status, put_data = client.proxy_put(
            handle_admin_put,
            _CATALOG_PATH,
            section_payload,
            identity,
            feature_flags=feature_flags,
            config_store=config_store,
            env=env,
            rbac_secret=rbac_secret,
            auth_header=auth_header,
        )

        if put_status == 200:
            # Re-GET to populate catalog_entries + providers for re-render.
            display = _catalog_display(client, handle_admin_get, identity, auth_header,
                                       feature_flags, read_model, feedback_queue,
                                       env, rbac_secret, config_store)
            display_data = display if isinstance(display, dict) else put_data
            html_body = render_catalog_page(
                display_data,
                identity=identity,
                csrf_token=save_token,
                flash=CATALOG_SUCCESS_FLASH,
                flash_kind="success",
            )
            return 200, html_body, response_headers

        error = put_data.get("error") if isinstance(put_data, dict) else None
        code = error.get("code") if isinstance(error, dict) else None
        if code == "forbidden":
            err_msg = CATALOG_ERROR_FORBIDDEN
        elif code == "operator_config_disabled":
            err_msg = CATALOG_ERROR_FLAG_OFF
        elif code == "invalid_config":
            err_msg = CATALOG_ERROR_VALIDATION
        else:
            err_msg = CATALOG_ERROR_GENERIC

        display = _catalog_display(client, handle_admin_get, identity, auth_header,
                                   feature_flags, read_model, feedback_queue,
                                   env, rbac_secret, config_store)
        display_data = display if isinstance(display, dict) else put_data
        html_body = render_catalog_page(
            display_data,
            identity=identity,
            csrf_token=save_token,
            error_message=err_msg,
            read_only=code == "operator_config_disabled",
        )
        return put_status, html_body, response_headers

    # GET
    display = _catalog_display(client, handle_admin_get, identity, auth_header,
                               feature_flags, read_model, feedback_queue,
                               env, rbac_secret, config_store)
    status = 200
    if not isinstance(display, dict):
        display = {"error": {"code": "catalog_error", "message": CATALOG_ERROR_GENERIC}}
        status = 500
    html_body = render_catalog_page(
        display,
        identity=identity,
        csrf_token=save_token,
    )
    return status, html_body, response_headers


def _catalog_display(
    client: AdminApiClient,
    handle_admin_get: HandleAdminGet,
    identity: Identity,
    auth_header: str | None,
    feature_flags: RuntimeFeatureFlags,
    read_model: Any,
    feedback_queue: list[dict[str, Any]] | None,
    env: Mapping[str, str] | None,
    rbac_secret: str | None,
    config_store: Any,
) -> dict[str, Any] | None:
    """Fetch catalog + provider registry IDs so the renderer has both."""
    cat_status, cat_data = client.proxy(
        handle_admin_get,
        _CATALOG_PATH,
        identity,
        read_model=read_model,
        feedback_queue=feedback_queue,
        feature_flags=feature_flags,
        env=env,
        rbac_secret=rbac_secret,
        auth_header=auth_header,
        config_store=config_store,
    )
    if cat_status != 200 or not isinstance(cat_data, dict):
        return cat_data if isinstance(cat_data, dict) else None

    # If catalog response already includes providers (test fixture), use it.
    if "providers" not in cat_data:
        prov_status, prov_data = client.proxy(
            handle_admin_get,
            _PROVIDERS_PATH,
            identity,
            read_model=read_model,
            feedback_queue=feedback_queue,
            feature_flags=feature_flags,
            env=env,
            rbac_secret=rbac_secret,
            auth_header=auth_header,
            config_store=config_store,
        )
        providers_list: list[Any] = []
        if prov_status == 200 and isinstance(prov_data, dict):
            data = prov_data.get("data")
            if isinstance(data, list):
                providers_list = data
        cat_data = dict(cat_data)
        cat_data["providers"] = providers_list
    return cat_data


def _vision_display(
    client: AdminApiClient,
    handle_admin_get: HandleAdminGet,
    identity: Identity,
    auth_header: str | None,
    feature_flags: RuntimeFeatureFlags,
    read_model: Any,
    feedback_queue: list[dict[str, Any]] | None,
    env: Mapping[str, str] | None,
    rbac_secret: str | None,
    config_store: Any,
) -> dict[str, Any] | None:
    """Fetch vision config + catalog + provider registry for the renderer."""
    vis_status, vis_data = client.proxy(
        handle_admin_get,
        _VISION_PATH,
        identity,
        read_model=read_model,
        feedback_queue=feedback_queue,
        feature_flags=feature_flags,
        env=env,
        rbac_secret=rbac_secret,
        auth_header=auth_header,
        config_store=config_store,
    )
    if vis_status != 200 or not isinstance(vis_data, dict):
        return vis_data if isinstance(vis_data, dict) else None

    # The API metadata normally reflects the flag, but enforce it here so the
    # renderer always disables the form when the flag is OFF.
    vis_data = dict(vis_data)
    metadata = vis_data.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["operator_config_enabled"] = bool(feature_flags.operator_config_enabled)
    vis_data["metadata"] = metadata

    cat_data = _catalog_display(
        client,
        handle_admin_get,
        identity,
        auth_header,
        feature_flags,
        read_model,
        feedback_queue,
        env,
        rbac_secret,
        config_store,
    )
    if isinstance(cat_data, dict):
        vis_data = dict(vis_data)
        vis_data["catalog_entries"] = cat_data.get("catalog_entries", [])
        vis_data["providers"] = cat_data.get("providers", [])
    return vis_data


def _handle_vision(
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
    """GET renders vision config; POST validates CSRF then proxies object PUT."""
    del boundary  # form uses escaped copy constants
    save_token = issue_csrf_token(identity, _VISION_PATH, signing_key=rbac_secret)
    probe_token = issue_csrf_token(identity, _PROBE_PATH, signing_key=rbac_secret)

    if http_method == "POST":
        valid, form_map = _validate_post_csrf(
            body, identity, _VISION_PATH, rbac_secret=rbac_secret
        )
        if not valid:
            html_body = render_vision_page(
                {"error": {"code": "forbidden", "message": VISION_ERROR_FORBIDDEN}},
                identity=identity,
                csrf_token=save_token,
                probe_csrf_token=probe_token,
            )
            return 403, html_body, response_headers

        if handle_admin_put is None:
            html_body = render_vision_page(
                {"error": {"code": "misconfigured", "message": VISION_ERROR_GENERIC}},
                identity=identity,
                csrf_token=save_token,
                probe_csrf_token=probe_token,
            )
            return 500, html_body, response_headers

        assert form_map is not None  # validated above
        section_payload = parse_vision_form(form_map)

        put_status, put_data = client.proxy_put(
            handle_admin_put,
            _VISION_PATH,
            section_payload,
            identity,
            feature_flags=feature_flags,
            config_store=config_store,
            env=env,
            rbac_secret=rbac_secret,
            auth_header=auth_header,
        )

        if put_status == 200:
            display = _vision_display(
                client,
                handle_admin_get,
                identity,
                auth_header,
                feature_flags,
                read_model,
                feedback_queue,
                env,
                rbac_secret,
                config_store,
            )
            display_data = display if isinstance(display, dict) else put_data
            html_body = render_vision_page(
                display_data,
                identity=identity,
                csrf_token=save_token,
                probe_csrf_token=probe_token,
                flash=VISION_SUCCESS_FLASH,
                flash_kind="success",
            )
            return 200, html_body, response_headers

        error = put_data.get("error") if isinstance(put_data, dict) else None
        code = error.get("code") if isinstance(error, dict) else None
        if code == "forbidden":
            err_msg = VISION_ERROR_FORBIDDEN
        elif code == "operator_config_disabled":
            err_msg = VISION_ERROR_FLAG_OFF
        elif code == "invalid_config":
            err_msg = VISION_ERROR_VALIDATION
        else:
            err_msg = VISION_ERROR_GENERIC

        display = _vision_display(
            client,
            handle_admin_get,
            identity,
            auth_header,
            feature_flags,
            read_model,
            feedback_queue,
            env,
            rbac_secret,
            config_store,
        )
        display_data = display if isinstance(display, dict) else put_data
        html_body = render_vision_page(
            display_data,
            identity=identity,
            csrf_token=save_token,
            probe_csrf_token=probe_token,
            error_message=err_msg,
            read_only=code in ("operator_config_disabled", "forbidden"),
        )
        return put_status, html_body, response_headers

    # GET
    display = _vision_display(
        client,
        handle_admin_get,
        identity,
        auth_header,
        feature_flags,
        read_model,
        feedback_queue,
        env,
        rbac_secret,
        config_store,
    )
    status = 200
    if not isinstance(display, dict):
        display = {"error": {"code": "vision_error", "message": VISION_ERROR_GENERIC}}
        status = 500
    html_body = render_vision_page(
        display,
        identity=identity,
        csrf_token=save_token,
        probe_csrf_token=probe_token,
    )
    return status, html_body, response_headers


def _handle_logs(
    *,
    http_method: str,
    identity: Identity,
    auth_header: str | None,
    feature_flags: RuntimeFeatureFlags,
    handle_admin_get: HandleAdminGet,
    read_model: Any,
    feedback_queue: list[dict[str, Any]] | None,
    env: Mapping[str, str] | None,
    rbac_secret: str | None,
    log_reader: Any,
    client: AdminApiClient,
    boundary: AdminUiBoundary,
    response_headers: dict[str, str],
    path: str,
) -> tuple[int, str, dict[str, str]]:
    """GET renders the log viewer page; POST is not allowed (405)."""
    if http_method != "GET":
        body_html = render_logs_page(
            {"error": {"code": "method_not_allowed", "message": "POST is not allowed on /logs"}},
            identity=identity,
            boundary=boundary,
        )
        return 405, body_html, response_headers

    # Parse query params from the request path for form state re-rendering.
    raw_path, _, query_string = path.partition("?")
    parsed_query: dict[str, str] = {}
    if query_string:
        for key, values in parse_qs(query_string, keep_blank_values=True).items():
            parsed_query[key] = values[0] if values else ""

    # Build the API path — preserve the /logs/<source> segment and query string.
    # handle_admin_get extracts query params from the path via _split_path_query.
    api_path = path  # full path with query string
    if not raw_path.startswith("/logs"):
        api_path = "/logs"

    # Proxy to handle_admin_get with log_reader.
    status, api_data = client.proxy(
        handle_admin_get,
        api_path,
        identity,
        read_model=read_model,
        feedback_queue=feedback_queue,
        feature_flags=feature_flags,
        env=env,
        rbac_secret=rbac_secret,
        auth_header=auth_header,
        log_reader=log_reader,
    )

    html_body = render_logs_page(
        api_data,
        identity=identity,
        boundary=boundary,
        query_params=parsed_query,
    )
    return status, html_body, response_headers


def _handle_audit(
    *,
    http_method: str,
    identity: Identity,
    auth_header: str | None,
    feature_flags: RuntimeFeatureFlags,
    handle_admin_get: HandleAdminGet,
    read_model: Any,
    feedback_queue: list[dict[str, Any]] | None,
    env: Mapping[str, str] | None,
    rbac_secret: str | None,
    client: AdminApiClient,
    boundary: AdminUiBoundary,
    response_headers: dict[str, str],
    path: str,
) -> tuple[int, str, dict[str, str]]:
    """GET renders the audit trail page or trace reconstruction page; POST → 405."""
    if http_method != "GET":
        body_html = render_audit_page(
            {"error": {"code": "method_not_allowed", "message": "POST is not allowed on /audit"}},
            identity=identity,
            boundary=boundary,
        )
        return 405, body_html, response_headers

    # Parse query params from the request path for form state re-rendering.
    raw_path, _, query_string = path.partition("?")
    parsed_query: dict[str, str] = {}
    if query_string:
        for key, values in parse_qs(query_string, keep_blank_values=True).items():
            parsed_query[key] = values[0] if values else ""

    # Build the API path — preserve the /audit/<trace_id> segment and query string.
    api_path = path

    # Proxy to handle_admin_get.
    status, api_data = client.proxy(
        handle_admin_get,
        api_path,
        identity,
        read_model=read_model,
        feedback_queue=feedback_queue,
        feature_flags=feature_flags,
        env=env,
        rbac_secret=rbac_secret,
        auth_header=auth_header,
    )

    # Determine if this is a trace reconstruction request (/audit/<trace_id>).
    rest = raw_path.removeprefix("/audit").strip("/")
    if rest:
        trace_id = rest.split("?")[0]
        html_body = render_trace_page(
            api_data,
            identity=identity,
            boundary=boundary,
            trace_id=trace_id,
        )
    else:
        html_body = render_audit_page(
            api_data,
            identity=identity,
            boundary=boundary,
            query_params=parsed_query,
        )
    return status, html_body, response_headers


def _handle_processes(
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
    process_supervisor: Any,
    client: AdminApiClient,
    boundary: AdminUiBoundary,
    response_headers: dict[str, str],
) -> tuple[int, str, dict[str, str]]:
    """GET renders process status; POST validates CSRF and proxies action PUT."""
    save_token = issue_csrf_token(identity, _PROCESSES_PATH, signing_key=rbac_secret)

    if http_method == "POST":
        if handle_admin_put is None:
            html_body = render_processes_page(
                {"error": {"code": "misconfigured", "message": "handle_admin_put not set"}},
                identity=identity,
                csrf_token=save_token,
                error_message="Process control is not configured",
            )
            return 500, html_body, response_headers

        valid, form_map = _validate_post_csrf(
            body, identity, _PROCESSES_PATH, rbac_secret=rbac_secret
        )
        if not valid:
            html_body = render_processes_page(
                {"error": {"code": "forbidden", "message": "CSRF token invalid"}},
                identity=identity,
                csrf_token=save_token,
                error_message="Invalid or missing CSRF token",
            )
            return 403, html_body, response_headers

        assert form_map is not None
        try:
            name, action = parse_processes_form(form_map)
        except ValueError as err:
            html_body = render_processes_page(
                {"error": {"code": "invalid_request", "message": str(err)}},
                identity=identity,
                csrf_token=save_token,
                error_message=str(err),
            )
            return 400, html_body, response_headers

        put_status, put_data = client.proxy_put(
            handle_admin_put,
            f"/processes/{name}/{action}",
            {},
            identity,
            feature_flags=feature_flags,
            config_store=config_store,
            env=env,
            rbac_secret=rbac_secret,
            auth_header=auth_header,
            process_supervisor=process_supervisor,
        )

        get_status, get_data = client.proxy(
            handle_admin_get,
            _PROCESSES_PATH,
            identity,
            read_model=read_model,
            feedback_queue=feedback_queue,
            feature_flags=feature_flags,
            env=env,
            rbac_secret=rbac_secret,
            auth_header=auth_header,
            config_store=config_store,
            process_supervisor=process_supervisor,
        )
        display = get_data if get_status == 200 else put_data

        if put_status == 200:
            html_body = render_processes_page(
                display,
                identity=identity,
                boundary=boundary,
                csrf_token=save_token,
                flash=f"Action '{action}' sent for {name}.",
                flash_kind="success",
            )
            return 200, html_body, response_headers

        error = put_data.get("error") if isinstance(put_data, dict) else None
        err_msg = error.get("message") if isinstance(error, dict) else "Process action failed"
        html_body = render_processes_page(
            display,
            identity=identity,
            boundary=boundary,
            csrf_token=save_token,
            error_message=str(err_msg),
        )
        return put_status, html_body, response_headers

    # GET
    status, api_data = client.proxy(
        handle_admin_get,
        _PROCESSES_PATH,
        identity,
        read_model=read_model,
        feedback_queue=feedback_queue,
        feature_flags=feature_flags,
        env=env,
        rbac_secret=rbac_secret,
        auth_header=auth_header,
        config_store=config_store,
        process_supervisor=process_supervisor,
    )
    html_body = render_processes_page(
        api_data,
        identity=identity,
        boundary=boundary,
        csrf_token=save_token,
    )
    return status, html_body, response_headers


def _handle_login(
    *,
    http_method: str,
    body: bytes | str | None,
    headers: Mapping[str, str] | None,
    feature_flags: RuntimeFeatureFlags,
    env: Mapping[str, str] | None,
    rbac_secret: str | None,
    session_store: Any,
    response_headers: dict[str, str],
) -> tuple[int, str, dict[str, str]]:
    """Handle GET/POST /login — render form or validate credentials + set cookie."""
    if http_method == "GET":
        csrf_token = issue_csrf_token(ANONYMOUS_IDENTITY, LOGIN_PATH, signing_key=rbac_secret)
        html = render_login_page(csrf_token=csrf_token)
        return 200, html, response_headers
    if http_method == "POST":
        session_ttl = _resolve_session_ttl(env)
        secure_cookie = _resolve_secure_cookie(env)
        status, html, extra_headers = handle_login_post(
            body,
            env=env,
            rbac_secret=rbac_secret,
            session_store=session_store,
            session_ttl=session_ttl,
            secure_cookie=secure_cookie,
            build_set_cookie=_build_set_cookie_header,
        )
        merged = dict(response_headers)
        merged.update(extra_headers)
        return status, html, merged
    # Other methods → 405
    body_html = render_login_page(csrf_token=issue_csrf_token(ANONYMOUS_IDENTITY, LOGIN_PATH, signing_key=rbac_secret))
    return 405, body_html, response_headers


def _handle_logout(
    *,
    http_method: str,
    body: bytes | str | None,
    headers: Mapping[str, str] | None,
    feature_flags: RuntimeFeatureFlags,
    env: Mapping[str, str] | None,
    rbac_secret: str | None,
    session_store: Any,
    response_headers: dict[str, str],
) -> tuple[int, str, dict[str, str]]:
    """Handle GET/POST /logout — GET returns 405, POST validates auth + CSRF."""
    if http_method == "GET":
        return 405, "Method Not Allowed", response_headers
    if http_method == "POST":
        # Resolve identity first (session cookie or Bearer).
        auth_header = _extract_auth_header(headers)
        cookie_header = _extract_cookie_header(headers)
        session_cookie = parse_cookie_header(cookie_header, SESSION_COOKIE_NAME)
        identity: Identity | None = None
        if feature_flags.rbac_enabled:
            identity = resolve_identity(
                auth_header,
                rbac_secret=rbac_secret,
                static_token=None,
                rbac_enabled=True,
                session_cookie=session_cookie,
                session_store=session_store,
            )
        else:
            identity = Identity(role=Role.ADMIN, tenant_id="default")

        if identity is None:
            csrf_token = issue_csrf_token(ANONYMOUS_IDENTITY, LOGIN_PATH, signing_key=rbac_secret)
            html = render_login_page(csrf_token=csrf_token, error_message="Authentication required")
            return 401, html, response_headers

        secure_cookie = _resolve_secure_cookie(env)
        status, html, extra_headers = handle_logout_post(
            body,
            identity=identity,
            rbac_secret=rbac_secret,
            session_store=session_store,
            session_cookie=session_cookie,
            secure_cookie=secure_cookie,
            build_clear_cookie=_build_clear_cookie_header,
        )
        merged = dict(response_headers)
        merged.update(extra_headers)
        return status, html, merged
    # Other methods → 405
    return 405, "Method Not Allowed", response_headers


def _extract_auth_header(headers: Mapping[str, str] | None) -> str | None:
    """Extract the Authorization header from request headers (case-insensitive)."""
    if headers is None:
        return None
    for key, value in headers.items():
        if key.lower() == "authorization":
            return value
    return None


def _extract_cookie_header(headers: Mapping[str, str] | None) -> str | None:
    """Extract the Cookie header from request headers (case-insensitive)."""
    if headers is None:
        return None
    for key, value in headers.items():
        if key.lower() == "cookie":
            return value
    return None


def _build_set_cookie_header(value: str, *, ttl: int, secure: bool) -> str:
    """Build a Set-Cookie header value with security attributes."""
    parts = [
        f"{SESSION_COOKIE_NAME}={value}",
        "Path=/",
        f"Max-Age={ttl}",
        "HttpOnly",
        "SameSite=Strict",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def _build_clear_cookie_header(*, secure: bool) -> str:
    """Build a Set-Cookie header value that clears the session cookie."""
    parts = [
        f"{SESSION_COOKIE_NAME}=",
        "Path=/",
        "Max-Age=0",
        "HttpOnly",
        "SameSite=Strict",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def _resolve_session_ttl(env: Mapping[str, str] | None) -> int:
    """Resolve the session TTL from the SESSION_TTL_SECONDS env var."""
    source: Mapping[str, str] = env if env is not None else os.environ
    raw = source.get("SESSION_TTL_SECONDS", "")
    try:
        return max(60, int(raw))
    except (ValueError, TypeError):
        return DEFAULT_SESSION_TTL_SECONDS


def _resolve_secure_cookie(env: Mapping[str, str] | None) -> bool:
    """Resolve whether the Secure cookie attribute should be set."""
    source: Mapping[str, str] = env if env is not None else os.environ
    return source.get("ADMIN_WEB_UI_SECURE_COOKIE", "").lower() in ("1", "true", "yes")


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
            body_html = render_error_page(
                413,
                "Request Too Large",
                "The request body exceeds the maximum allowed size.",
                identity=None,
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
        try:
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
                handle_config_probe=getattr(self.server, "handle_config_probe", None),  # type: ignore[attr-defined]
                process_supervisor=getattr(self.server, "process_supervisor", None),  # type: ignore[attr-defined]
                reports_aggregator=getattr(self.server, "reports_aggregator", None),  # type: ignore[attr-defined]
                log_reader=getattr(self.server, "log_reader", None),  # type: ignore[attr-defined]
                session_store=getattr(self.server, "session_store", None),  # type: ignore[attr-defined]
            )
        except Exception:
            traceback.print_exc(file=sys.stderr)
            html_body = render_error_page(
                500,
                "Internal Server Error",
                "An unexpected error occurred. Check server logs.",
                identity=None,
            )
            status = 500
            headers = {
                "Content-Type": "text/html; charset=utf-8",
                "Content-Security-Policy": CSP_HEADER,
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
            }
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
