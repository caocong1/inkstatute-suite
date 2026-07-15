# Phase 85: Login Session Auth — Validation Criteria

**Phase:** 85 — Login Session Auth
**Requirements:** AUTH-01, AUTH-02, AUTH-03, AUTH-04
**Date:** 2026-07-14

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` (stdlib) |
| **Config file** | none — stdlib unittest |
| **Quick run command** | `PYTHONPATH=packages/rbac/src python -m unittest rbac.tests.test_session rbac.tests.test_identity -v && PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.admin_web_ui.tests.test_auth_session -v` |
| **Full suite command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest discover -s packages/rbac/tests services/admin-web-ui/tests -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command (new + extended test modules)
- **After every plan wave:** Run full suite command + RBAC CI scan
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## AUTH-01: Operator login via username/password with signed session cookie

### Criterion 1: Login page renders

- [ ] `GET /login` returns HTTP 200 with an HTML form containing `name="username"`, `name="password"`, and `name="csrf_token"` fields.
- [ ] The form `method` is `POST` and `action` is `/login`.
- [ ] The CSRF token hidden input has a non-empty `value` attribute.
- [ ] The login page sets the CSP header (`Content-Security-Policy`) on the response.
- [ ] No authentication is required to view the login page (public route).

### Criterion 2: Successful login sets session cookie and redirects

- [ ] `POST /login` with valid `csrf_token`, `username`, and `password` returns HTTP 302 with `Location: /`.
- [ ] The response includes a `Set-Cookie` header containing `inkstatute_session=<signed_value>`.
- [ ] The cookie value has exactly one `.` separating base64url payload and signature (same format as RBAC tokens).
- [ ] The `Set-Cookie` header includes `Path=/`.
- [ ] The `Set-Cookie` header includes `Max-Age=<SESSION_TTL_SECONDS>`.
- [ ] After login, a `GET /` request with the session cookie (no Bearer header) returns 200 — the cookie authenticates the request.

### Criterion 3: Failed login returns 401 with re-rendered form

- [ ] `POST /login` with incorrect password returns HTTP 401.
- [ ] The response HTML contains an error message ("Invalid username or password").
- [ ] The re-rendered form includes a fresh CSRF token (rotated after the attempt).
- [ ] No `Set-Cookie` header is set on failed login.

### Criterion 4: Login disabled when password not configured

- [ ] When `ADMIN_PASSWORD` env var is unset (or empty), `POST /login` with any credentials returns 401.
- [ ] `check_credentials` returns `False` when `ADMIN_PASSWORD` is empty.

### Criterion 5: Credential comparison is constant-time

- [ ] `check_credentials` uses `hmac.compare_digest` for both username and password comparison.
- [ ] No plaintext password is logged or included in error messages.

### Criterion 6: Logout invalidates the session

- [ ] `POST /logout` with a valid session cookie and CSRF token returns 302 with `Location: /login`.
- [ ] The response includes a `Set-Cookie` header with `Max-Age=0` (clears the cookie).
- [ ] After logout, a `GET /` request with the old session cookie returns 401 — the session is invalidated server-side.
- [ ] `InMemorySessionStore.delete(sid)` removes the session record so `verify_session_cookie` returns `None`.

### Criterion 7: GET /logout returns 405

- [ ] `GET /logout` returns HTTP 405 (logout must be POST to prevent CSRF via GET link/image).

---

## AUTH-02: Session cookie coexists with Bearer token auth

### Criterion 8: Bearer header takes priority over session cookie

- [ ] When a request has both a valid Bearer token and a valid session cookie, `resolve_identity` returns the Identity from the Bearer token (not the cookie).
- [ ] A test explicitly verifies that the Bearer token's role/tenant are returned, not the session's.
- [ ] The session cookie is never examined when a valid Bearer header is present.

### Criterion 9: Cookie auth is fallback for browser sessions

- [ ] When no Bearer header is present but a valid session cookie is present, `resolve_identity` returns the Identity from the session cookie.
- [ ] A `GET /` request with only a session cookie (no Authorization header) returns 200.
- [ ] When both Bearer and cookie are absent/invalid, `resolve_identity` returns `None` → 401.

### Criterion 10: Both paths resolve to a single Identity

- [ ] Bearer auth and cookie auth both return the same `Identity` dataclass (`role: Role, tenant_id: str`).
- [ ] Both paths pass through the same `RbacGuard.check(identity.role, _guard_path(route_path))`.
- [ ] No route bypasses the guard — `/login` is public (handled before auth), `/logout` has its own auth check; all other routes go through the standard RBAC pipeline.

### Criterion 11: Cookie auth respects RBAC guard

- [ ] A session with OPERATOR role accessing `/gates` (ADMIN-only) returns 403 — the guard applies to cookie-authenticated requests.
- [ ] A session with ADMIN role accessing `/gates` returns 200.

### Criterion 12: Invalid Bearer falls through to cookie

- [ ] When the Bearer header is present but invalid (e.g. `"Bearer garbage"`) and a valid session cookie is present, `resolve_identity` returns the cookie Identity (graceful fallback).

---

## AUTH-03: Session cookie signing, TTL, and store

### Criterion 13: HMAC-signed with RBAC_TOKEN_SECRET

- [ ] `issue_session_cookie(secret, sid, ...)` produces `base64url(payload).base64url(hmac_sha256(secret, payload_b64))`.
- [ ] The payload contains `sid`, `role`, `tenant_id`, `iat`, `exp` (sorted compact JSON).
- [ ] `verify_session_cookie` uses `hmac.compare_digest` for constant-time signature comparison.
- [ ] A tampered signature is rejected (returns `None`).

### Criterion 14: Configurable TTL

- [ ] `SESSION_TTL_SECONDS` env var controls the session cookie TTL (default 28800 = 8 hours).
- [ ] The `Set-Cookie` header `Max-Age` matches `SESSION_TTL_SECONDS`.
- [ ] `issue_session_cookie` `ttl_seconds` param sets the `exp` claim (`iat + ttl_seconds`).
- [ ] An expired session cookie (`exp <= now`) is rejected by `verify_session_cookie`.

### Criterion 15: Session store interface is extensible

- [ ] `SessionStore` is a `Protocol` with `create`, `get`, `delete` methods.
- [ ] `InMemorySessionStore` implements the Protocol with a `dict[str, SessionRecord]` and `threading.Lock`.
- [ ] The store is injected into `handle_admin_web_ui_request` via the `session_store` param (no global state).
- [ ] Future implementations (Redis, DB) can replace `InMemorySessionStore` without changing call sites.

### Criterion 16: Store presence required for verification

- [ ] `verify_session_cookie` returns `None` when `session_store` is `None` (a self-contained cookie is never sufficient — server-side invalidation requires the store).
- [ ] `verify_session_cookie` returns `None` when the `sid` is not in the store (session invalidated by logout or expiry).

### Criterion 17: Session fixation prevention

- [ ] `InMemorySessionStore.create` generates a fresh `secrets.token_urlsafe(32)` session ID on every call.
- [ ] Two consecutive logins with the same credentials produce different session cookies (different `sid`).
- [ ] The `sid` is never reused — `create` always generates a new random value.

### Criterion 18: Cookie attributes

- [ ] The `Set-Cookie` header always includes `HttpOnly`.
- [ ] The `Set-Cookie` header always includes `SameSite=Strict`.
- [ ] The `Set-Cookie` header always includes `Path=/`.
- [ ] The `Set-Cookie` header includes `Secure` only when `ADMIN_WEB_UI_SECURE_COOKIE` env var is set to `1`/`true`/`yes`.
- [ ] By default (no `ADMIN_WEB_UI_SECURE_COOKIE`), `Secure` is NOT included (HTTP dev deployments).

### Criterion 19: Cookie parsing

- [ ] `parse_cookie_header("inkstatute_session=abc.def; other=x", "inkstatute_session")` returns `"abc.def"`.
- [ ] `parse_cookie_header(None, "inkstatute_session")` returns `None`.
- [ ] `parse_cookie_header("other=x", "inkstatute_session")` returns `None` (cookie absent).

---

## AUTH-04: CSRF protection for login/logout

### Criterion 20: Login CSRF token issued on GET /login

- [ ] `GET /login` renders a form with a `csrf_token` hidden input.
- [ ] The CSRF token is issued with `ANONYMOUS_IDENTITY` (Role.VIEWER, tenant_id="anonymous") bound to the `/login` route.
- [ ] The CSRF token is signed with `RBAC_TOKEN_SECRET` (via `signing_key=rbac_secret`).

### Criterion 21: Login CSRF validated on POST /login

- [ ] `POST /login` without a `csrf_token` field returns 403.
- [ ] `POST /login` with a tampered `csrf_token` returns 403.
- [ ] `POST /login` with a valid `csrf_token` (issued for `/login` route) passes CSRF validation and proceeds to credential check.
- [ ] A CSRF token issued for a different route (e.g. `/config/channels`) is rejected on `/login` (route binding).

### Criterion 22: CSRF token rotated after login

- [ ] After a successful login, the response does not reuse the pre-login CSRF token.
- [ ] After a failed login, the re-rendered form includes a fresh CSRF token (rotated on every response).
- [ ] The pre-login CSRF token is single-use — replaying it on a second POST /login should fail (the token itself is stateless/HMAC, so rotation means the *form* always gets a new token; the old token is technically still valid until exp, but the pattern ensures a fresh token per render).

### Criterion 23: Logout CSRF protection

- [ ] `POST /logout` requires a valid CSRF token bound to the `/logout` route and the authenticated identity.
- [ ] `POST /logout` without a CSRF token returns 403.
- [ ] `POST /logout` with a tampered CSRF token returns 403.
- [ ] `GET /logout` returns 405 (cannot be triggered via GET link/image — CSRF protection).

### Criterion 24: Logout requires authentication

- [ ] `POST /logout` without any auth (no session cookie, no Bearer) returns 401.
- [ ] `POST /logout` with a valid session cookie but no CSRF token returns 403 (authenticated but CSRF-failed).

---

## Security and Privacy Validation

### Criterion 25: HTML escaping on login/logout pages

- [ ] All dynamic content in the `/login` and `/logout` HTML pages is HTML-escaped via `html.escape()` or the `_esc()` helper.
- [ ] A test with `<script>alert(1)</script>` in the username field asserts the HTML contains `&lt;script&gt;` not `<script>`.
- [ ] Error messages are HTML-escaped before rendering.

### Criterion 26: CSP header on all responses

- [ ] `GET /login` response includes the `Content-Security-Policy` header.
- [ ] `POST /login` response (both success and failure) includes the CSP header.
- [ ] `POST /logout` response includes the CSP header.
- [ ] No inline `<script>` tags in any login/logout page.

### Criterion 27: No secrets in responses

- [ ] The `RBAC_TOKEN_SECRET` value is never included in any response body or header.
- [ ] The `ADMIN_PASSWORD` value is never included in any response body or error message.
- [ ] The session cookie signature is not logged.
- [ ] Error messages are generic ("Invalid username or password") — do not distinguish between "user not found" and "wrong password".

---

## Regression Validation

### Criterion 28: Existing Bearer token tests pass

- [ ] All existing `test_identity.py` Bearer-token tests pass unchanged (no regression from the `resolve_identity` signature extension).
- [ ] `test_token.py` passes unchanged.
- [ ] `test_guard.py` passes unchanged.
- [ ] `test_matrix.py` passes unchanged.

### Criterion 29: Existing admin-web-ui tests pass

- [ ] `test_dashboard_audit.py` passes unchanged.
- [ ] `test_dashboard_logs.py` passes unchanged.
- [ ] `test_dashboard_reports.py` passes unchanged.
- [ ] `test_main.py` passes unchanged (server creation with new `session_store` attribute).

### Criterion 30: RBAC CI scan passes

- [ ] `PYTHONPATH=packages/rbac/src:services/admin-console-api/src python3 scripts/scan_rbac_annotations.py` exits 0.
- [ ] No new routes added to `ROUTE_PREFIXES` (login/logout are admin-web-ui-only, not admin-console-api routes).

### Criterion 31: No new dependencies

- [ ] `dependencies = []` in all `pyproject.toml` files.
- [ ] No new third-party imports — `http.cookies.SimpleCookie`, `secrets`, `threading` are all stdlib.
