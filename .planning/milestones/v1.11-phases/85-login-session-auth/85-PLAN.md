---
phase: 85-login-session-auth
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/rbac/src/rbac/session.py
  - packages/rbac/src/rbac/identity.py
  - packages/rbac/src/rbac/__init__.py
  - packages/rbac/tests/test_session.py
  - packages/rbac/tests/test_identity.py
  - services/admin-web-ui/src/admin_web_ui/auth.py
  - services/admin-web-ui/src/admin_web_ui/server.py
  - services/admin-web-ui/src/admin_web_ui/__main__.py
  - services/admin-web-ui/src/admin_web_ui/dashboard.py
  - services/admin-web-ui/src/admin_web_ui/logs.py
  - services/admin-web-ui/tests/test_auth_session.py
autonomous: true
requirements:
  - AUTH-01
  - AUTH-02
  - AUTH-03
  - AUTH-04
user_setup: []

must_haves:
  truths:
    - "issue_session_cookie(secret, sid, role, tenant_id, ttl_seconds, now) returns base64url(payload).base64url(hmac_sha256(secret, payload_b64)) where payload contains sid, role, tenant_id, iat, exp — same signing scheme as rbac.token.issue_token but with an added sid claim"
    - "verify_session_cookie(cookie_value, secret, session_store, now) returns a SessionRecord(role, tenant_id, sid, exp) only when the signature is valid (hmac.compare_digest), the sid exists in session_store, and exp > now; returns None on any failure (bad format, bad signature, unknown sid, expired)"
    - "SessionStore is a Protocol with create(role, tenant_id, ttl_seconds, now) -> sid, get(sid) -> SessionRecord | None, delete(sid) -> None; InMemorySessionStore implements it with a dict[str, SessionRecord] and thread-safe operations via a threading.Lock"
    - "InMemorySessionStore.create generates a fresh secrets.token_urlsafe(32) session ID (session fixation prevention — never reuses an existing sid), stores a SessionRecord, and returns the sid; delete removes the sid so subsequent verify_session_cookie calls for that sid return None (logout invalidation)"
    - "resolve_identity(auth_header, rbac_secret=..., rbac_enabled=True, session_cookie=..., session_store=...) tries the Bearer header first; only when the Bearer token is absent or invalid does it fall back to the session cookie via verify_session_cookie; both paths return the same Identity dataclass; when both are absent/invalid, returns None"
    - "Bearer header takes priority over session cookie — when a valid Bearer token is present, the session cookie is never examined (API path unchanged)"
    - "parse_cookie_header(cookie_header, name) extracts the value of the named cookie from a Cookie header string using http.cookies.SimpleCookie; returns None when the header is missing or the cookie name is absent"
    - "GET /login renders an HTML login form with username, password, and csrf_token fields; the CSRF token is issued with an anonymous Identity (Role.VIEWER, tenant_id='anonymous') bound to the /login route; no auth is required to view the login page"
    - "POST /login validates the CSRF token (anonymous identity, /login route), parses username and password from the form body, compares against ADMIN_USERNAME and ADMIN_PASSWORD env vars using hmac.compare_digest; on success creates a new session via session_store.create, issues a signed session cookie, sets Set-Cookie with HttpOnly; SameSite=Strict; Secure (when ADMIN_WEB_UI_SECURE_COOKIE is set or HTTPS detected); Max-Age=SESSION_TTL_SECONDS; Path=/, rotates the CSRF token, and returns 302 redirect to /"
    - "POST /login on invalid credentials returns 401 with the login form re-rendered and a new CSRF token; on missing/invalid CSRF returns 403 with the login form re-rendered and a new CSRF token; on missing username or password returns 400 with the login form re-rendered and a new CSRF token"
    - "POST /logout requires authentication (session cookie or Bearer token); validates CSRF token (authenticated identity, /logout route); deletes the session from session_store (logout invalidation); sets Set-Cookie with Max-Age=0 to clear the cookie; returns 302 redirect to /login"
    - "GET /logout returns 405 (logout must be POST to prevent CSRF via GET link/image)"
    - "handle_admin_web_ui_request special-cases /login and /logout before the standard RBAC auth step: /login is public (no auth required), /logout requires auth but is handled by a dedicated _handle_logout function rather than the generic guard pipeline"
    - "All other routes use the extended resolve_identity with session_cookie and session_store params so that browser sessions with a valid session cookie are authenticated without a Bearer header; the RbacGuard.check is still applied to every non-login/non-logout route (no route bypasses the guard)"
    - "SESSION_TTL_SECONDS env var controls session cookie TTL (default 28800 = 8 hours); ADMIN_USERNAME env var (default 'admin'); ADMIN_PASSWORD env var (no default — login disabled with a configuration error when unset)"
    - "The session cookie name is 'inkstatute_session'; the cookie value is the HMAC-signed string from issue_session_cookie"
    - "All dynamic content in the /login and /logout pages is HTML-escaped via html.escape; CSP header is set on every response; no inline JavaScript"
    - "session_store is created in __main__.create_server as an InMemorySessionStore instance and passed to handle_admin_web_ui_request via the AdminWebUiServer._dispatch method (same pattern as read_model, config_store, etc.)"
  artifacts:
    - "rbac.session.SessionRecord dataclass"
    - "rbac.session.SessionStore Protocol"
    - "rbac.session.InMemorySessionStore class"
    - "rbac.session.issue_session_cookie function"
    - "rbac.session.verify_session_cookie function"
    - "rbac.session.parse_cookie_header function"
    - "rbac.session.DEFAULT_SESSION_TTL_SECONDS constant"
    - "rbac.session.SESSION_COOKIE_NAME constant"
    - "rbac.identity.resolve_identity extended with session_cookie and session_store params"
    - "admin_web_ui.auth.render_login_page function"
    - "admin_web_ui.auth.render_logout_page function"
    - "admin_web_ui.auth.handle_login_post function"
    - "admin_web_ui.auth.handle_logout_post function"
    - "admin_web_ui.auth.ANONYMOUS_IDENTITY constant"
    - "admin_web_ui.auth.check_credentials function"
    - "admin_web_ui.server.handle_admin_web_ui_request /login and /logout route handling"
    - "admin_web_ui.server._handle_login function"
    - "admin_web_ui.server._handle_logout function"
    - "admin_web_ui.server._extract_cookie_header function"
    - "admin_web_ui.server._build_set_cookie_header function"
    - "admin_web_ui.server._resolve_session_ttl function"
    - "admin_web_ui.server._resolve_admin_credentials function"
    - "admin_web_ui.__main__.create_server session_store wiring"
    - "admin_web_ui.dashboard._page_template nav_items /login and /logout entries"
    - "admin_web_ui.logs._logs_page_template nav_items /login and /logout entries"
    - "test_session.py, test_identity.py (extended), test_auth_session.py"
  key_links:
    - "issue_session_cookie is called by handle_login_post on successful credential check to produce the Set-Cookie value"
    - "verify_session_cookie is called by resolve_identity when a Bearer header is absent and a session cookie is present"
    - "InMemorySessionStore.create is called by handle_login_post to create a new session with a fresh random sid (fixation prevention)"
    - "InMemorySessionStore.delete is called by handle_logout_post to invalidate the session (logout)"
    - "resolve_identity is called by handle_admin_web_ui_request with session_cookie and session_store for all non-login/non-logout routes"
    - "issue_csrf_token / validate_csrf_token (existing csrf.py) are reused for login/logout CSRF protection — login uses ANONYMOUS_IDENTITY, logout uses the authenticated identity"
    - "RbacGuard.check is applied to every non-login/non-logout route — no route bypasses the guard"
---

<objective>
Add username/password login with HMAC-signed session cookies to the admin web UI. Operators log in via `POST /login` (env-credential MVP: `ADMIN_USERNAME` / `ADMIN_PASSWORD`), receive an `inkstatute_session` cookie that is HMAC-signed with `RBAC_TOKEN_SECRET`, and are authenticated on subsequent requests via cookie fallback when no Bearer header is present. `POST /logout` invalidates the session. Both login and logout are CSRF-protected, and the session ID is rotated on every login (session fixation prevention). Cookie auth and Bearer auth both resolve to a single `Identity` and pass through the same `RbacGuard`.

Purpose: Enable browser-based operator sessions without requiring API token management, while preserving the existing Bearer-token API path unchanged.

Output: A `session.py` module in the rbac package (session store + signed cookie issue/verify), extended `resolve_identity` with cookie fallback, login/logout pages and handlers in admin-web-ui, and automated tests.
</objective>

<execution_context>
@$HOME/.codeium/windsurf/gsd-core/workflows/execute-plan.md
@$HOME/.codeium/windsurf/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/85-login-session-auth/85-CONTEXT.md
@packages/rbac/src/rbac/token.py
@packages/rbac/src/rbac/identity.py
@packages/rbac/src/rbac/guard.py
@packages/rbac/src/rbac/roles.py
@packages/rbac/src/rbac/matrix.py
@packages/rbac/src/rbac/__init__.py
@packages/rbac/tests/test_identity.py
@packages/rbac/tests/test_token.py
@services/admin-web-ui/src/admin_web_ui/server.py
@services/admin-web-ui/src/admin_web_ui/csrf.py
@services/admin-web-ui/src/admin_web_ui/dashboard.py
@services/admin-web-ui/src/admin_web_ui/logs.py
@services/admin-web-ui/src/admin_web_ui/api_client.py
@services/admin-web-ui/src/admin_web_ui/__main__.py
@services/admin-web-ui/src/admin_web_ui/boundary.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Session store + HMAC-signed session cookie in rbac package</name>
  <files>
    packages/rbac/src/rbac/session.py
    packages/rbac/src/rbac/identity.py
    packages/rbac/src/rbac/__init__.py
    packages/rbac/tests/test_session.py
    packages/rbac/tests/test_identity.py
  </files>
  <read_first>
    packages/rbac/src/rbac/token.py
    packages/rbac/src/rbac/identity.py
    packages/rbac/src/rbac/roles.py
    packages/rbac/src/rbac/__init__.py
    packages/rbac/tests/test_identity.py
    packages/rbac/tests/test_token.py
  </read_first>
  <action>
    ### Create `packages/rbac/src/rbac/session.py`

    ```python
    """HMAC-signed session cookies with server-side session store (Phase 85).

    Session cookies are ``base64url(payload_json).base64url(hmac_sha256(secret,
    payload_b64))`` — the same signing scheme as ``rbac.token`` but with an
    added ``sid`` claim.  The server-side ``SessionStore`` maps the session ID
    to a ``SessionRecord`` so that logout can invalidate the session by
    deleting the entry.  Verification requires both a valid signature AND a
    live store entry — a self-contained cookie alone is never sufficient.

    The ``SessionStore`` Protocol is extensible: ``InMemorySessionStore`` is
    the MVP implementation; future implementations (Redis, DB) can be
    swapped without changing call sites.
    """

    from __future__ import annotations

    import base64
    import hashlib
    import hmac
    import json
    import secrets
    import threading
    import time
    from dataclasses import dataclass
    from http.cookies import SimpleCookie
    from typing import Any, Protocol

    from .roles import Role

    DEFAULT_SESSION_TTL_SECONDS = 28800  # 8 hours
    SESSION_COOKIE_NAME = "inkstatute_session"


    class SessionStore(Protocol):
        """Extensible session store interface.

        MVP: ``InMemorySessionStore`` (dict + lock).  Future: Redis, DB.
        """

        def create(
            self, *, role: Role, tenant_id: str, ttl_seconds: int, now: int
        ) -> str:
            """Create a new session with a fresh random sid; return the sid."""
            ...

        def get(self, sid: str) -> "SessionRecord | None":
            """Return the session record for *sid*, or None if not found / expired."""
            ...

        def delete(self, sid: str) -> None:
            """Delete the session for *sid* (logout invalidation)."""
            ...


    @dataclass(frozen=True, slots=True)
    class SessionRecord:
        """Server-side session record stored in the SessionStore."""

        sid: str
        role: str
        tenant_id: str
        created_at: int
        expires_at: int


    class InMemorySessionStore:
        """In-memory dict-backed session store (MVP).

        Thread-safe via a ``threading.Lock`` — safe for ``ThreadingHTTPServer``.
        """

        def __init__(self) -> None:
            self._sessions: dict[str, SessionRecord] = {}
            self._lock = threading.Lock()

        def create(
            self, *, role: Role, tenant_id: str, ttl_seconds: int, now: int
        ) -> str:
            sid = secrets.token_urlsafe(32)
            record = SessionRecord(
                sid=sid,
                role=role.value if isinstance(role, Role) else str(role),
                tenant_id=tenant_id,
                created_at=int(now),
                expires_at=int(now) + int(ttl_seconds),
            )
            with self._lock:
                self._sessions[sid] = record
            return sid

        def get(self, sid: str) -> SessionRecord | None:
            with self._lock:
                record = self._sessions.get(sid)
                if record is None:
                    return None
                if record.expires_at <= int(time.time()):
                    del self._sessions[sid]
                    return None
                return record

        def delete(self, sid: str) -> None:
            with self._lock:
                self._sessions.pop(sid, None)
    ```

    Define `_b64url_encode` / `_b64url_decode` (copy from token.py — or import them; **decision:** copy to keep session.py self-contained and avoid coupling to token.py internals).

    Define `issue_session_cookie`:
    ```python
    def issue_session_cookie(
        secret: str,
        sid: str,
        *,
        role: Role | str,
        tenant_id: str,
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        now: int | None = None,
    ) -> str:
        """Issue an HMAC-SHA256 signed session cookie value.

        Returns ``base64url(payload).base64url(signature)`` where payload
        contains ``sid``, ``role``, ``tenant_id``, ``iat``, ``exp``.
        """
    ```
    - `iat = int(now if now is not None else time.time())`
    - `exp = iat + int(ttl_seconds)`
    - `role_value = role.value if isinstance(role, Role) else str(role)`
    - payload dict: `{"sid": sid, "role": role_value, "tenant_id": tenant_id, "iat": iat, "exp": exp}`
    - `payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)`
    - `payload_b64 = _b64url_encode(payload_json.encode("utf-8"))`
    - `sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()`
    - return `f"{payload_b64}.{_b64url_encode(sig)}"`

    Define `verify_session_cookie`:
    ```python
    def verify_session_cookie(
        cookie_value: str,
        secret: str,
        session_store: SessionStore | None,
        now: int | None = None,
    ) -> SessionRecord | None:
        """Verify a session cookie's signature and store presence.

        Returns a ``SessionRecord`` only when: the format is valid, the
        signature matches (``hmac.compare_digest``), the ``sid`` exists in
        ``session_store``, and ``exp > now``.  Returns ``None`` on any
        failure — never raises.
        """
    ```
    - `now_int = int(now if now is not None else time.time())`
    - If `cookie_value` is not a str or `cookie_value.count(".") != 1` → return None.
    - Split into `payload_b64, sig_b64`. Decode both via `_b64url_decode` (return None on decode error).
    - Recompute `expected_sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()`.
    - If `not hmac.compare_digest(provided_sig, expected_sig)` → return None.
    - Parse `payload = json.loads(payload_json)`. On error → return None.
    - Extract `sid, role, tenant_id, iat, exp` (return None on KeyError/TypeError/ValueError).
    - If `exp <= now_int` → return None.
    - If `session_store is None` → return None (store is required for invalidation).
    - `record = session_store.get(sid)` — if None → return None (session invalidated or expired).
    - Return `record`.

    Define `parse_cookie_header`:
    ```python
    def parse_cookie_header(cookie_header: str | None, name: str) -> str | None:
        """Extract the value of cookie *name* from a Cookie header string.

        Returns ``None`` when the header is missing or the cookie is absent.
        """
    ```
    - If `cookie_header is None` → return None.
    - Use `http.cookies.SimpleCookie`: `c = SimpleCookie(); c.load(cookie_header)`.
    - `morsel = c.get(name)` — if None → return None.
    - Return `morsel.value`.

    Add `__all__` with all public names: `DEFAULT_SESSION_TTL_SECONDS`, `SESSION_COOKIE_NAME`, `SessionStore`, `SessionRecord`, `InMemorySessionStore`, `issue_session_cookie`, `verify_session_cookie`, `parse_cookie_header`.

    ### Modify `packages/rbac/src/rbac/identity.py`

    Extend `resolve_identity` with two new optional params: `session_cookie: str | None = None` and `session_store: Any = None`.

    In the `rbac_enabled=True` branch, **after** the Bearer token attempt fails (returns None or `identity is None`), add the session cookie fallback:

    ```python
    if rbac_enabled:
        # Bearer header takes priority (API path unchanged).
        token = _strip_bearer(auth_header)
        if token is not None and rbac_secret is not None:
            try:
                claims = verify_token(token, rbac_secret, now=now)
            except RbacTokenError:
                claims = None
            if claims is not None:
                try:
                    role = Role(claims.role)
                except ValueError:
                    role = None
                if role is not None:
                    return Identity(role=role, tenant_id=claims.tenant_id)
        # Bearer absent or invalid — try session cookie fallback (browser sessions).
        if session_cookie is not None and rbac_secret is not None and session_store is not None:
            from .session import verify_session_cookie
            record = verify_session_cookie(session_cookie, rbac_secret, session_store, now=now)
            if record is not None:
                try:
                    role = Role(record.role)
                except ValueError:
                    role = None
                if role is not None:
                    return Identity(role=role, tenant_id=record.tenant_id)
        return None
    ```

    **Key change:** the existing code returns None immediately when the Bearer token is invalid. The new code falls through to the cookie check when the Bearer token is absent or invalid. Import `verify_session_cookie` lazily inside the function (same pattern as the existing `admin_console_api.auth` lazy import) so the rbac package remains importable standalone when session.py is not needed.

    Update the docstring to document the session cookie fallback and Bearer priority.

    ### Modify `packages/rbac/src/rbac/__init__.py`

    Add to imports:
    ```python
    from .session import (
        DEFAULT_SESSION_TTL_SECONDS,
        SESSION_COOKIE_NAME,
        InMemorySessionStore,
        SessionRecord,
        SessionStore,
        issue_session_cookie,
        parse_cookie_header,
        verify_session_cookie,
    )
    ```

    Add all the new names to `__all__`.

    ### Tests: `packages/rbac/tests/test_session.py`

    Create tests following the `test_token.py` pattern:

    1. **test_issue_and_verify_session_cookie:** Issue a cookie with `issue_session_cookie("s", "sid-1", role=Role.ADMIN, tenant_id="t1", now=1000)`. Create an `InMemorySessionStore`, call `store.create(role=Role.ADMIN, tenant_id="t1", ttl_seconds=28800, now=1000)` — but this generates a *different* sid. **Instead:** call `store.create` first to get a sid, then `issue_session_cookie("s", sid, role=Role.ADMIN, tenant_id="t1", now=1000)`, then `verify_session_cookie(cookie, "s", store, now=1500)`. Assert the returned `SessionRecord` has `role == "admin"`, `tenant_id == "t1"`, `sid == sid`.
    2. **test_verify_rejects_bad_signature:** Tamper with the signature (flip last char). Assert `verify_session_cookie` returns None.
    3. **test_verify_rejects_unknown_sid:** Issue a cookie with a sid that is not in the store. Assert `verify_session_cookie` returns None.
    4. **test_verify_rejects_expired:** Issue a cookie with `ttl_seconds=100, now=1000`. Verify at `now=1200`. Assert None.
    5. **test_verify_rejects_deleted_session:** Create a session, issue a cookie, verify (success), then `store.delete(sid)`, verify again → None (logout invalidation).
    6. **test_verify_rejects_no_store:** Pass `session_store=None`. Assert None.
    7. **test_verify_rejects_malformed:** Pass `"not-a-cookie"`, `"a.b.c"`, `""`, `None`. Assert None for all.
    8. **test_in_memory_store_create_generates_unique_sids:** Call `store.create` twice with the same args. Assert the two sids are different (random, fixation prevention).
    9. **test_in_memory_store_get_expired_cleans_up:** Create with `ttl_seconds=100, now=1000`. Call `store.get(sid)` at `now=1200` (use a mock or direct time manipulation — **decision:** since `InMemorySessionStore.get` uses `time.time()` internally, inject by making `get` accept an optional `now` param OR test via `verify_session_cookie` with `now=1200` which calls `store.get` — but `store.get` uses real time. **Decision:** add an optional `now: int | None = None` param to `InMemorySessionStore.get` that defaults to `time.time()` when None, used by `verify_session_cookie` which passes `now`. Update `SessionStore.get` Protocol to accept `now: int | None = None`). Assert the record is None and the session was removed from the dict.
    10. **test_parse_cookie_header:** `"inkstatute_session=abc.def; other=x"` → `parse_cookie_header(..., "inkstatute_session")` returns `"abc.def"`. Missing name → None. None header → None.
    11. **test_parse_cookie_header_multiple:** `"a=1; inkstatute_session=xyz; b=2"` → returns `"xyz"`.
    12. **test_issue_session_cookie_format:** Assert the cookie has exactly one `.` and both parts are valid base64url.

    **Update `SessionStore.get` and `InMemorySessionStore.get` signatures** to accept `now: int | None = None`:
    ```python
    def get(self, sid: str, *, now: int | None = None) -> SessionRecord | None:
        now_int = int(now if now is not None else time.time())
        ...
        if record.expires_at <= now_int:
            del self._sessions[sid]
            return None
    ```
    Update `verify_session_cookie` to pass `now=now_int` to `session_store.get(sid, now=now_int)`.

    ### Tests: `packages/rbac/tests/test_identity.py` (extend)

    Add a new test class `ResolveIdentitySessionCookieTests`:

    1. **test_session_cookie_fallback_when_no_bearer:** Create a store, `store.create(role=Role.ADMIN, tenant_id="t1", ttl_seconds=28800, now=1000)` → sid. `issue_session_cookie("s", sid, role=Role.ADMIN, tenant_id="t1", now=1000)` → cookie. `resolve_identity(None, rbac_secret="s", rbac_enabled=True, session_cookie=cookie, session_store=store, now=1500)`. Assert Identity(role=ADMIN, tenant_id="t1").
    2. **test_bearer_takes_priority_over_cookie:** Create a valid Bearer token AND a valid session cookie. Call `resolve_identity(f"Bearer {token}", rbac_secret="s", rbac_enabled=True, session_cookie=cookie, session_store=store, now=1500)`. Assert the returned Identity matches the Bearer token's claims (not the cookie's).
    3. **test_session_cookie_used_when_bearer_invalid:** Pass an invalid Bearer header (`"Bearer garbage"`) and a valid session cookie. Assert the cookie identity is returned.
    4. **test_session_cookie_invalid_returns_none:** Pass a valid Bearer-absent (`None`) with an invalid cookie (`"tampered"`) and a valid store. Assert None.
    5. **test_no_bearer_no_cookie_returns_none:** `resolve_identity(None, rbac_secret="s", rbac_enabled=True, session_cookie=None, session_store=store, now=1500)` → None.
    6. **test_session_cookie_no_store_returns_none:** Pass a valid cookie but `session_store=None`. Assert None.
    7. **test_session_cookie_unknown_role_returns_none:** Create a session with a role string that is not a valid Role enum value (manually insert into store dict or use a custom store). Assert None.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/rbac/src python -m unittest rbac.tests.test_session rbac.tests.test_identity -v</automated>
    <automated>PYTHONPATH=packages/rbac/src python -m unittest discover -s packages/rbac/tests -v</automated>
    <manual>Confirm that resolve_identity still passes all existing Bearer-token tests (no regression) and that the session cookie fallback only activates when Bearer is absent or invalid.</manual>
  </verify>
</task>

<task type="auto">
  <name>Task 2: Login/logout pages, handlers, and session wiring in admin-web-ui</name>
  <files>
    services/admin-web-ui/src/admin_web_ui/auth.py
    services/admin-web-ui/src/admin_web_ui/server.py
    services/admin-web-ui/src/admin_web_ui/__main__.py
    services/admin-web-ui/src/admin_web_ui/dashboard.py
    services/admin-web-ui/src/admin_web_ui/logs.py
    services/admin-web-ui/tests/test_auth_session.py
  </files>
  <read_first>
    services/admin-web-ui/src/admin_web_ui/server.py
    services/admin-web-ui/src/admin_web_ui/csrf.py
    services/admin-web-ui/src/admin_web_ui/dashboard.py
    services/admin-web-ui/src/admin_web_ui/logs.py
    services/admin-web-ui/src/admin_web_ui/__main__.py
    services/admin-web-ui/src/admin_web_ui/boundary.py
    packages/rbac/src/rbac/session.py
    packages/rbac/src/rbac/identity.py
    packages/rbac/src/rbac/token.py
    services/admin-web-ui/tests/test_dashboard_audit.py
  </read_first>
  <action>
    ### Create `services/admin-web-ui/src/admin_web_ui/auth.py`

    ```python
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
    import os
    from typing import Any, Mapping
    from urllib.parse import parse_qs

    from rbac import Identity, Role

    from .csrf import issue_csrf_token, validate_csrf_token
    from .dashboard import _page_template, _esc

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
    ```

    Define `check_credentials(username, password, env) -> bool`:
    - Read `ADMIN_USERNAME` from env (default `"admin"`).
    - Read `ADMIN_PASSWORD` from env (default `""` — empty means login disabled).
    - If `ADMIN_PASSWORD` is empty → return False (login disabled when password not configured).
    - Compare username and password using `hmac.compare_digest` (constant-time for both).

    Define `render_login_page(*, csrf_token, error_message=None) -> str`:
    - Render an HTML form with:
      - `<form method="POST" action="/login">`
      - `<input type="hidden" name="csrf_token" value="{_esc(csrf_token)}">`
      - `<input type="text" name="username" autocomplete="username">`
      - `<input type="password" name="password" autocomplete="current-password">`
      - `<button type="submit">Log in</button>`
    - If `error_message` is not None, render an error `<p class="error">` above the form.
    - Use `_page_template("Login", body, identity=None)` — no nav identity shown on login page.
    - **Decision:** The login page uses a minimal page template without nav links (the user is not authenticated yet). Add a `nav_links=""` override — **simplest:** pass `identity=None` and let `_page_template` render nav as-is (nav links are static, not auth-gated). This is acceptable — nav links are harmless on the login page.

    Define `render_logout_page(*, csrf_token, identity, error_message=None) -> str`:
    - Render a logout confirmation form:
      - `<form method="POST" action="/logout">`
      - `<input type="hidden" name="csrf_token" value="{_esc(csrf_token)}">`
      - `<button type="submit">Log out</button>`
    - If `error_message` is not None, render an error paragraph.
    - Use `_page_template("Logout", body, identity=identity)`.

    Define `handle_login_post(body, *, env, rbac_secret, session_store, session_ttl, secure_cookie) -> tuple[int, str, dict[str, str]]`:
    - Parse form body via `parse_qs` (same pattern as `_validate_post_csrf`).
    - Extract `csrf_token` from form.
    - Validate CSRF: `validate_csrf_token(token, ANONYMOUS_IDENTITY, LOGIN_PATH, signing_key=rbac_secret)`. If invalid → return `(403, render_login_page(csrf_token=fresh_token, error_message="CSRF token invalid"), headers)`.
    - Extract `username` and `password` from form (single value, stripped).
    - If username or password is missing/empty → return `(400, render_login_page(...), headers)`.
    - Call `check_credentials(username, password, env)`. If False → return `(401, render_login_page(csrf_token=fresh_token, error_message="Invalid username or password"), headers)`.
    - On success:
      - `now = int(time.time())`
      - `sid = session_store.create(role=Role.ADMIN, tenant_id="default", ttl_seconds=session_ttl, now=now)`
      - `cookie_value = issue_session_cookie(rbac_secret, sid, role=Role.ADMIN, tenant_id="default", ttl_seconds=session_ttl, now=now)`
      - `set_cookie = _build_set_cookie_header(cookie_value, ttl=session_ttl, secure=secure_cookie)`
      - `response_headers["Set-Cookie"] = set_cookie`
      - Return `(302, "", {**response_headers, "Location": "/"})` — 302 redirect to `/`.
    - **Note:** `fresh_token` is always `issue_csrf_token(ANONYMOUS_IDENTITY, LOGIN_PATH, signing_key=rbac_secret)` — rotated on every response (login CSRF prevention: token is single-use).

    Define `handle_logout_post(body, *, identity, rbac_secret, session_store, session_cookie, secure_cookie) -> tuple[int, str, dict[str, str]]`:
    - Parse form body, extract `csrf_token`.
    - Validate CSRF: `validate_csrf_token(token, identity, LOGOUT_PATH, signing_key=rbac_secret)`. If invalid → return `(403, render_logout_page(csrf_token=fresh_token, identity=identity, error_message="CSRF token invalid"), headers)`.
    - Extract `sid` from the session cookie (parse the cookie value to get the sid — use `verify_session_cookie` which returns a `SessionRecord` with `sid`, or parse the payload directly). **Decision:** call `verify_session_cookie(session_cookie, rbac_secret, session_store)` to get the `SessionRecord`; if it returns a record, call `session_store.delete(record.sid)`. If it returns None (already invalid), that's fine — idempotent logout.
    - Set `Set-Cookie` with `Max-Age=0` to clear the cookie: `_build_clear_cookie_header(secure=secure_cookie)`.
    - Return `(302, "", {**response_headers, "Location": "/login", "Set-Cookie": clear_cookie})`.

    Import `issue_session_cookie`, `verify_session_cookie`, `SESSION_COOKIE_NAME` from `rbac.session` (via `rbac` package re-export).

    ### Modify `services/admin-web-ui/src/admin_web_ui/server.py`

    1. Add imports:
       ```python
       from rbac import (
           InMemorySessionStore,
           SESSION_COOKIE_NAME,
           parse_cookie_header,
           issue_session_cookie,
           verify_session_cookie,
       )
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
       ```

    2. Add `_LOGIN_PATH = "/login"` and `_LOGOUT_PATH = "/logout"` constants (or import from auth.py).

    3. Add `_extract_cookie_header(headers)`:
       ```python
       def _extract_cookie_header(headers: Mapping[str, str] | None) -> str | None:
           if headers is None:
               return None
           for key, value in headers.items():
               if key.lower() == "cookie":
                   return value
           return None
       ```

    4. Add `_build_set_cookie_header(value, ttl, secure)`:
       ```python
       def _build_set_cookie_header(value: str, *, ttl: int, secure: bool) -> str:
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
       ```

    5. Add `_build_clear_cookie_header(secure)`:
       ```python
       def _build_clear_cookie_header(*, secure: bool) -> str:
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
       ```

    6. Add `_resolve_session_ttl(env)`:
       ```python
       def _resolve_session_ttl(env: Mapping[str, str] | None) -> int:
           source = env if env is not None else os.environ
           raw = source.get("SESSION_TTL_SECONDS", "")
           try:
               return max(60, int(raw))
           except (ValueError, TypeError):
               return DEFAULT_SESSION_TTL_SECONDS
       ```
       Import `DEFAULT_SESSION_TTL_SECONDS` from rbac.

    7. Add `_resolve_secure_cookie(env)`:
       ```python
       def _resolve_secure_cookie(env: Mapping[str, str] | None) -> bool:
           source = env if env is not None else os.environ
           return source.get("ADMIN_WEB_UI_SECURE_COOKIE", "").lower() in ("1", "true", "yes")
       ```

    8. **In `handle_admin_web_ui_request`**, add `session_store: Any = None` to the signature (after `log_reader`).

    9. **Before Step 2 (route resolution)** — or immediately after Step 1 (feature flag gate) — add login/logout route handling:

       ```python
       # Step 1b — login/logout routes (handled before RBAC auth)
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
       ```

       **Note:** `secret` is resolved at the top of the function already (line ~270). Move the `secret = _resolve_rbac_secret(env, rbac_secret)` call to before the login/logout check, or resolve it inside `_handle_login` / `_handle_logout`. **Decision:** resolve `secret` early (right after Step 1 feature flag gate, before Step 2) so it's available for login/logout and the standard auth flow.

    10. **In Step 3 (RBAC auth)**, extend the `resolve_identity` call to pass `session_cookie` and `session_store`:

        ```python
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
        ```

        The rest of the auth flow (401 on None, RbacGuard.check) is unchanged — cookie-authenticated requests now get an Identity and pass through the same guard.

    11. Add `_handle_login` function:
        ```python
        def _handle_login(
            *, http_method, body, headers, feature_flags, env, rbac_secret,
            session_store, response_headers,
        ) -> tuple[int, str, dict[str, str]]:
        ```
        - If `http_method == "GET"`:
          - `csrf_token = issue_csrf_token(ANONYMOUS_IDENTITY, LOGIN_PATH, signing_key=rbac_secret)`
          - `html = render_login_page(csrf_token=csrf_token)`
          - return `(200, html, response_headers)`
        - If `http_method == "POST"`:
          - `session_ttl = _resolve_session_ttl(env)`
          - `secure_cookie = _resolve_secure_cookie(env)`
          - Delegate to `handle_login_post(body, env=env, rbac_secret=rbac_secret, session_store=session_store, session_ttl=session_ttl, secure_cookie=secure_cookie)` — but pass `response_headers` so Set-Cookie/Location can be added. **Decision:** have `handle_login_post` return `(status, html, extra_headers)` and merge `extra_headers` into `response_headers` in `_handle_login`.
          - Return the merged `(status, html, response_headers)`.
        - Other methods → 405.

    12. Add `_handle_logout` function:
        ```python
        def _handle_logout(
            *, http_method, body, headers, feature_flags, env, rbac_secret,
            session_store, response_headers,
        ) -> tuple[int, str, dict[str, str]]:
        ```
        - If `http_method == "GET"` → 405 (logout must be POST).
        - If `http_method == "POST"`:
          - Resolve identity first (session cookie or Bearer) — reuse the same auth logic. If identity is None → 401 (redirect to /login or render login page with error). **Decision:** render login page with error and 401.
          - `secure_cookie = _resolve_secure_cookie(env)`
          - Extract session cookie from headers for sid extraction.
          - Delegate to `handle_logout_post(body, identity=identity, rbac_secret=rbac_secret, session_store=session_store, session_cookie=session_cookie, secure_cookie=secure_cookie)`.
          - Merge extra headers, return.
        - Other methods → 405.

    13. Add `/login` and `/logout` to `_POST_ROUTES`:
        ```python
        _POST_ROUTES = frozenset({
            _CHANNELS_PATH,
            _PROVIDERS_PATH,
            _PROBE_PATH,
            _CATALOG_PATH,
            _VISION_PATH,
            _PROCESSES_PATH,
            _LOGIN_PATH,
            _LOGOUT_PATH,
        })
        ```
        **But:** the existing POST guard at line ~252 rejects POST on routes not in `_POST_ROUTES` *before* auth. Since `/login` and `/logout` are now handled in Step 1b (before Step 2 route resolution and the POST guard), they bypass that check. **Decision:** Move the login/logout handling to Step 1b (before the `_POST_ROUTES` check) so they are dispatched first. Do NOT add them to `_POST_ROUTES` — they have their own method handling in `_handle_login` / `_handle_logout`.

    14. **In `AdminWebUiServer._dispatch`**, add `session_store` to the `handle_admin_web_ui_request` call:
        ```python
        session_store=getattr(self.server, "session_store", None),
        ```

    ### Modify `services/admin-web-ui/src/admin_web_ui/__main__.py`

    In `create_server`, after creating `rbac_secret`:
    ```python
    from rbac import InMemorySessionStore
    session_store = InMemorySessionStore()
    ```
    And set on the server:
    ```python
    httpd.session_store = session_store
    ```
    Place it alongside the other `httpd.*` attribute assignments (after `httpd.rbac_secret = rbac_secret`).

    ### Modify `services/admin-web-ui/src/admin_web_ui/dashboard.py`

    1. In `_page_template`, add to `nav_items` (at the end):
       ```python
       ("/login", "Login"),
       ("/logout", "Logout"),
       ```

    2. In `render_dashboard`, add to `title_map`:
       ```python
       "login": "Login",
       "logout": "Logout",
       ```

    ### Modify `services/admin-web-ui/src/admin_web_ui/logs.py`

    In `_logs_page_template` (or the equivalent nav_items list), add to `nav_items` (at the end):
    ```python
    ("/login", "Login"),
    ("/logout", "Logout"),
    ```

    ### Tests: `services/admin-web-ui/tests/test_auth_session.py`

    Create tests following the `test_dashboard_audit.py` pattern. Use a helper to build a request with an `InMemorySessionStore` and env with `ADMIN_USERNAME` / `ADMIN_PASSWORD` set:

    ```python
    def _env_with_credentials(**overrides):
        env = {
            "ADMIN_WEB_UI_ENABLED": "true",
            "RBAC_ENABLED": "true",
            "RBAC_TOKEN_SECRET": "test-secret",
            "ADMIN_USERNAME": "admin",
            "ADMIN_PASSWORD": "s3cret",
        }
        env.update(overrides)
        return env
    ```

    1. **test_get_login_renders_form:** `handle_admin_web_ui_request("/login", {}, method="GET", ...)`. Assert 200, HTML contains `<form`, `name="username"`, `name="password"`, `name="csrf_token"`, "Login".
    2. **test_get_login_has_csrf_token:** Assert the HTML contains a non-empty `value="..."` for the csrf_token hidden input.
    3. **test_post_login_success_sets_cookie_and_redirects:** POST with valid csrf_token + username=admin + password=s3cret. Assert 302, `Location: /`, `Set-Cookie` header contains `inkstatute_session=`, `HttpOnly`, `SameSite=Strict`.
    4. **test_post_login_invalid_credentials:** POST with wrong password. Assert 401, HTML contains "Invalid username or password", new csrf_token present.
    5. **test_post_login_missing_csrf:** POST without csrf_token. Assert 403, HTML contains "CSRF".
    6. **test_post_login_invalid_csrf:** POST with a tampered csrf_token. Assert 403.
    7. **test_post_login_missing_username:** POST with csrf but no username. Assert 400.
    8. **test_post_login_password_not_configured:** env without `ADMIN_PASSWORD`. Assert 401 (login disabled).
    9. **test_session_cookie_authenticates_subsequent_request:** Login successfully, extract the cookie value from Set-Cookie, then make a GET / request with `Cookie: inkstatute_session={cookie_value}` and no Bearer header. Assert 200 (authenticated via cookie).
    10. **test_bearer_takes_priority_over_cookie:** Login to get a cookie, then make a GET / request with both a valid Bearer token AND the session cookie. Assert the identity matches the Bearer token's role/tenant (not the session's).
    11. **test_session_cookie_invalid_returns_401:** GET / with a tampered cookie and no Bearer. Assert 401.
    12. **test_post_logout_invalidates_session:** Login, get cookie. POST /logout with valid csrf_token + cookie. Assert 302, `Location: /login`, `Set-Cookie` contains `Max-Age=0`. Then GET / with the old cookie → 401 (session invalidated).
    13. **test_get_logout_returns_405:** GET /logout. Assert 405.
    14. **test_post_logout_requires_auth:** POST /logout without any auth (no cookie, no Bearer). Assert 401.
    15. **test_post_logout_invalid_csrf:** Login, then POST /logout with tampered csrf. Assert 403.
    16. **test_session_fixation_prevention:** Login twice with the same credentials. Assert the two Set-Cookie values are different (new sid each login).
    17. **test_cookie_attributes_httponly_samesite:** Login, assert Set-Cookie contains `HttpOnly` and `SameSite=Strict`.
    18. **test_cookie_attributes_secure_when_flag_set:** env with `ADMIN_WEB_UI_SECURE_COOKIE=true`. Login, assert Set-Cookie contains `Secure`.
    19. **test_cookie_attributes_no_secure_by_default:** Default env. Login, assert Set-Cookie does NOT contain `Secure`.
    20. **test_login_page_html_escaped:** Inject `<script>` into the error message path (invalid credentials with username `<script>`). Assert HTML contains `&lt;script&gt;` not `<script>`.
    21. **test_session_ttl_from_env:** env with `SESSION_TTL_SECONDS=3600`. Login, assert Set-Cookie contains `Max-Age=3600`.
    22. **test_csp_header_on_login_page:** GET /login. Assert response headers contain the CSP header.
    23. **test_nav_links_include_login_logout:** GET / (authenticated). Assert HTML contains `<a href="/login"` and `<a href="/logout"`.
    24. **test_rbac_guard_still_applies_to_cookie_auth:** Login as ADMIN (cookie), then access a route that ADMIN is denied (e.g. none — ADMIN has access to all). **Instead:** create a session with OPERATOR role (manually via store) and access `/gates` (ADMIN-only). Assert 403. This verifies cookie auth goes through RbacGuard.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.admin_web_ui.tests.test_auth_session -v</automated>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.admin_web_ui.tests.test_main -v</automated>
    <automated>PYTHONPATH=packages/rbac/src:services/admin-console-api/src python3 scripts/scan_rbac_annotations.py</automated>
    <manual>Confirm that login/logout pages render with CSP headers, all dynamic content is HTML-escaped, and the session cookie has HttpOnly + SameSite=Strict attributes. Confirm that a browser session (cookie only, no Bearer) can access protected pages and that logout invalidates the session.</manual>
  </verify>
</task>

</tasks>

<post_conditions>
After both tasks are complete:

1. **RBAC CI scan passes:** `PYTHONPATH=packages/rbac/src:services/admin-console-api/src python3 scripts/scan_rbac_annotations.py` exits 0. (No new admin-console-api routes are added — /login and /logout are admin-web-ui-only routes, not in ROUTE_PREFIXES.)
2. **All new tests pass:** `test_session.py` (rbac), `test_identity.py` (rbac, extended), `test_auth_session.py` (admin-web-ui).
3. **Existing tests still pass:** `test_token.py`, `test_guard.py`, `test_matrix.py`, `test_roles.py`, `test_package_invariants.py`, `test_scan_rbac.py`, `test_dashboard_audit.py`, `test_dashboard_logs.py`, `test_dashboard_reports.py`, `test_main.py` — no regressions from the `identity.py` / `server.py` / `dashboard.py` changes.
4. **No new dependencies:** `dependencies = []` in all `pyproject.toml` files; no new third-party imports. `http.cookies.SimpleCookie` and `secrets` are stdlib.
5. **Bearer priority preserved:** When a valid Bearer header is present, the session cookie is never examined — the API path is unchanged. A test explicitly verifies this.
6. **Single Identity, single guard:** Both Bearer and cookie auth resolve to the same `Identity` dataclass and pass through the same `RbacGuard.check` — no route bypasses the guard (except /login which is public and /logout which has its own auth check).
7. **Session fixation prevention:** Every successful login generates a fresh `secrets.token_urlsafe(32)` session ID — never reuses an existing sid. A test verifies two logins produce different cookies.
8. **Logout invalidation:** `session_store.delete(sid)` removes the session so subsequent `verify_session_cookie` calls return None. A test verifies the old cookie is rejected after logout.
9. **CSRF protection:** Login uses an anonymous-identity CSRF token bound to `/login`; logout uses the authenticated-identity CSRF token bound to `/logout`. Both tokens are rotated after the respective action. GET /logout returns 405 (no CSRF via GET).
10. **Cookie security attributes:** `HttpOnly`, `SameSite=Strict`, `Path=/`, `Max-Age=TTL` are always set; `Secure` is set only when `ADMIN_WEB_UI_SECURE_COOKIE` is enabled (HTTPS deployments).
11. **CSP compliance:** The /login and /logout pages use only HTML-escaped content; no inline `<script>` tags; CSP header set on every response.
12. **Env credentials:** `ADMIN_USERNAME` (default "admin") and `ADMIN_PASSWORD` (no default — login disabled when unset) are read from env. `SESSION_TTL_SECONDS` (default 28800) controls cookie TTL. All compared with `hmac.compare_digest` (constant-time).
</post_conditions>
