"""Login and logout pages + handlers for the admin web UI (Phase 85).

GET /login renders a username/password form with a CSRF token (anonymous
identity).  POST /login validates the CSRF token, checks credentials
against ADMIN_USERNAME / ADMIN_PASSWORD env vars, creates a session via
SessionStore, and sets a signed session cookie.  POST /logout deletes the
session and clears the cookie.  Both flows rotate the CSRF token after
completion.
"""

from __future__ import annotations

import hmac
import time
from typing import Any, Mapping
from urllib.parse import parse_qs

from rbac import Identity, Role
from rbac.session import (
    SESSION_COOKIE_NAME,
    issue_session_cookie,
    verify_session_cookie,
)

from .csrf import issue_csrf_token, validate_csrf_token
from .dashboard import _esc, _page_template

__all__ = [
    "ANONYMOUS_IDENTITY",
    "LOGIN_PATH",
    "LOGOUT_PATH",
    "check_credentials",
    "render_login_page",
    "render_logout_page",
    "handle_login_post",
    "handle_logout_post",
]

LOGIN_PATH = "/login"
LOGOUT_PATH = "/logout"

# Pre-auth CSRF identity for the login form.  The CSRF token is bound to
# the /login route, so it cannot be replayed on other routes.  An attacker
# cannot forge the token without RBAC_TOKEN_SECRET.
ANONYMOUS_IDENTITY = Identity(role=Role.VIEWER, tenant_id="anonymous")


def check_credentials(
    username: str, password: str, env: Mapping[str, str] | None
) -> bool:
    """Compare username/password against env-configured admin credentials.

    Uses ``hmac.compare_digest`` for constant-time comparison.  Returns
    ``False`` when ``ADMIN_PASSWORD`` is not configured (login disabled).
    """
    source: Mapping[str, str] = env if env is not None else {}
    expected_user = source.get("ADMIN_USERNAME", "admin")
    expected_pass = source.get("ADMIN_PASSWORD", "")
    if not expected_pass:
        return False  # login disabled when password not configured
    user_ok = hmac.compare_digest(username, expected_user)
    pass_ok = hmac.compare_digest(password, expected_pass)
    return user_ok and pass_ok


def render_login_page(
    *, csrf_token: str, error_message: str | None = None
) -> str:
    """Render the HTML login form with a CSRF token and optional error."""
    error_html = ""
    if error_message is not None:
        error_html = f'    <p class="error">{_esc(error_message)}</p>\n'
    body = f"""{error_html}    <form method="POST" action="{LOGIN_PATH}" class="card">
      <div class="field">
        <label for="username">Username</label>
        <input type="text" id="username" name="username" autocomplete="username" required>
      </div>
      <div class="field">
        <label for="password">Password</label>
        <input type="password" id="password" name="password" autocomplete="current-password" required>
      </div>
      <input type="hidden" name="csrf_token" value="{_esc(csrf_token)}">
      <button type="submit" class="btn-primary">Log in</button>
    </form>"""
    return _page_template("Login", body, identity=None)


def render_logout_page(
    *, csrf_token: str, identity: Identity, error_message: str | None = None
) -> str:
    """Render the HTML logout confirmation form with a CSRF token."""
    error_html = ""
    if error_message is not None:
        error_html = f'    <p class="error">{_esc(error_message)}</p>\n'
    body = f"""{error_html}    <form method="POST" action="{LOGOUT_PATH}" class="card">
      <p>Confirm logout?</p>
      <input type="hidden" name="csrf_token" value="{_esc(csrf_token)}">
      <button type="submit" class="btn-primary">Log out</button>
    </form>"""
    return _page_template("Logout", body, identity=identity)


def _fresh_login_csrf(rbac_secret: str | None) -> str:
    return issue_csrf_token(ANONYMOUS_IDENTITY, LOGIN_PATH, signing_key=rbac_secret)


def handle_login_post(
    body: bytes | str | None,
    *,
    env: Mapping[str, str] | None,
    rbac_secret: str | None,
    session_store: Any,
    session_ttl: int,
    secure_cookie: bool,
    build_set_cookie: Any,
) -> tuple[int, str, dict[str, str]]:
    """Handle POST /login — validate CSRF, check credentials, set session cookie.

    Returns ``(status, html, extra_headers)`` where ``extra_headers`` may
    contain ``Set-Cookie`` and ``Location`` for redirects.
    """
    extra_headers: dict[str, str] = {}
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body or "")
    form_map = parse_qs(text, keep_blank_values=True)

    # Extract csrf_token.
    raw = form_map.get("csrf_token")
    csrf_token: str | None = None
    if raw is not None:
        if isinstance(raw, list):
            values = [str(v).strip() for v in raw if str(v).strip()]
            if len(values) == 1:
                csrf_token = values[0]
        else:
            csrf_token = str(raw).strip() or None

    fresh_token = _fresh_login_csrf(rbac_secret)

    # Validate CSRF.
    if csrf_token is None or not validate_csrf_token(
        csrf_token, ANONYMOUS_IDENTITY, LOGIN_PATH, signing_key=rbac_secret
    ):
        return 403, render_login_page(csrf_token=fresh_token, error_message="CSRF token invalid"), extra_headers

    # Extract username and password.
    username_raw = form_map.get("username")
    password_raw = form_map.get("password")
    username = ""
    if username_raw is not None:
        if isinstance(username_raw, list):
            username = str(username_raw[0]).strip() if username_raw else ""
        else:
            username = str(username_raw).strip()
    password = ""
    if password_raw is not None:
        if isinstance(password_raw, list):
            password = str(password_raw[0]).strip() if password_raw else ""
        else:
            password = str(password_raw).strip()

    if not username or not password:
        return 400, render_login_page(csrf_token=fresh_token, error_message="Username and password are required"), extra_headers

    # Check credentials.
    if not check_credentials(username, password, env):
        return 401, render_login_page(csrf_token=fresh_token, error_message="Invalid username or password"), extra_headers

    # Success — create session and set cookie.
    now = int(time.time())
    sid = session_store.create(role=Role.ADMIN, tenant_id="default", ttl_seconds=session_ttl, now=now)
    cookie_value = issue_session_cookie(
        rbac_secret or "", sid, role=Role.ADMIN, tenant_id="default", ttl_seconds=session_ttl, now=now
    )
    extra_headers["Set-Cookie"] = build_set_cookie(cookie_value, ttl=session_ttl, secure=secure_cookie)
    extra_headers["Location"] = "/"
    return 302, "", extra_headers


def handle_logout_post(
    body: bytes | str | None,
    *,
    identity: Identity,
    rbac_secret: str | None,
    session_store: Any,
    session_cookie: str | None,
    secure_cookie: bool,
    build_clear_cookie: Any,
) -> tuple[int, str, dict[str, str]]:
    """Handle POST /logout — validate CSRF, delete session, clear cookie.

    Returns ``(status, html, extra_headers)``.
    """
    extra_headers: dict[str, str] = {}
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body or "")
    form_map = parse_qs(text, keep_blank_values=True)

    raw = form_map.get("csrf_token")
    csrf_token: str | None = None
    if raw is not None:
        if isinstance(raw, list):
            values = [str(v).strip() for v in raw if str(v).strip()]
            if len(values) == 1:
                csrf_token = values[0]
        else:
            csrf_token = str(raw).strip() or None

    fresh_token = issue_csrf_token(identity, LOGOUT_PATH, signing_key=rbac_secret)

    if csrf_token is None or not validate_csrf_token(
        csrf_token, identity, LOGOUT_PATH, signing_key=rbac_secret
    ):
        return 403, render_logout_page(csrf_token=fresh_token, identity=identity, error_message="CSRF token invalid"), extra_headers

    # Delete the session (idempotent — fine if already invalid).
    if session_cookie is not None and session_store is not None and rbac_secret is not None:
        record = verify_session_cookie(session_cookie, rbac_secret, session_store)
        if record is not None:
            session_store.delete(record.sid)

    extra_headers["Set-Cookie"] = build_clear_cookie(secure=secure_cookie)
    extra_headers["Location"] = LOGIN_PATH
    return 302, "", extra_headers
