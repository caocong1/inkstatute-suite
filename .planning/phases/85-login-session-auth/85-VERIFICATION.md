# Phase 85 — Login & Session Auth — Verification

**Status: PASSED**

## Summary

Phase 85 adds username/password login with HMAC-signed session cookies to the
admin web UI. Operators log in via `POST /login` (env-credential MVP:
`ADMIN_USERNAME` / `ADMIN_PASSWORD`), receive an `inkstatute_session` cookie
that is HMAC-signed with `RBAC_TOKEN_SECRET`, and are authenticated on
subsequent requests via cookie fallback when no Bearer header is present.
`POST /logout` invalidates the session. Both login and logout are
CSRF-protected, and the session ID is rotated on every login (session fixation
prevention).

## Tasks Completed

### Task 1: Session store + HMAC-signed session cookie in rbac package

- **Created** `packages/rbac/src/rbac/session.py`:
  - `SessionStore` Protocol with `create`, `get`, `delete` methods
  - `InMemorySessionStore` — thread-safe dict-backed store with `threading.Lock`
  - `SessionRecord` frozen dataclass (sid, role, tenant_id, created_at, expires_at)
  - `issue_session_cookie` — HMAC-SHA256 signed cookie with sid/role/tenant_id/iat/exp claims
  - `verify_session_cookie` — validates signature + store presence + expiry (never raises)
  - `parse_cookie_header` — extracts named cookie from Cookie header via `SimpleCookie`
  - `DEFAULT_SESSION_TTL_SECONDS` (28800 = 8 hours), `SESSION_COOKIE_NAME` ("inkstatute_session")

- **Modified** `packages/rbac/src/rbac/identity.py`:
  - Extended `resolve_identity` with `session_cookie` and `session_store` params
  - Bearer header takes priority; cookie fallback only when Bearer is absent or invalid
  - Lazy import of `verify_session_cookie` to keep rbac standalone-importable

- **Modified** `packages/rbac/src/rbac/__init__.py`:
  - Re-exported all session symbols

- **Created** `packages/rbac/tests/test_session.py` — 20 tests
- **Extended** `packages/rbac/tests/test_identity.py` — 7 new session cookie tests

### Task 2: Login/logout pages, handlers, and session wiring in admin-web-ui

- **Created** `services/admin-web-ui/src/admin_web_ui/auth.py`:
  - `ANONYMOUS_IDENTITY` — pre-auth CSRF identity (Role.VIEWER, tenant_id="anonymous")
  - `check_credentials` — constant-time comparison via `hmac.compare_digest`
  - `render_login_page` / `render_logout_page` — HTML-escaped forms with CSRF tokens
  - `handle_login_post` — CSRF validation, credential check, session creation, cookie issuance
  - `handle_logout_post` — CSRF validation, session deletion, cookie clearing

- **Modified** `services/admin-web-ui/src/admin_web_ui/server.py`:
  - Added `/login` and `/logout` route handling (Step 1b, before standard RBAC auth)
  - `_handle_login` / `_handle_logout` dedicated functions
  - `_extract_cookie_header`, `_build_set_cookie_header`, `_build_clear_cookie_header`
  - `_resolve_session_ttl`, `_resolve_secure_cookie` helpers
  - Extended `resolve_identity` call with `session_cookie` and `session_store` params
  - Mint short-lived Bearer token for downstream admin-console-api when cookie auth is used
  - `session_store` param added to `handle_admin_web_ui_request` and `_dispatch`

- **Modified** `services/admin-web-ui/src/admin_web_ui/__main__.py`:
  - Created `InMemorySessionStore` and wired it to `httpd.session_store`

- **Modified** `services/admin-web-ui/src/admin_web_ui/dashboard.py`:
  - Added `/login` and `/logout` nav items + title_map entries

- **Modified** `services/admin-web-ui/src/admin_web_ui/logs.py`:
  - Added `/login` and `/logout` nav items

- **Created** `services/admin-web-ui/tests/test_auth_session.py` — 24 tests

## Verification Results

### Task 1 Verification

```
PYTHONPATH=packages/rbac/src:packages/rbac/tests python -m unittest test_session test_identity -v
→ Ran 40 tests in 0.003s — OK

PYTHONPATH=<full> python -m unittest discover -s packages/rbac/tests -v
→ Ran 87 tests in 1.565s — OK
```

### Task 2 Verification

```
PYTHONPATH=<full>:services/admin-web-ui/tests python -m unittest test_auth_session -v
→ Ran 24 tests in 0.004s — OK

PYTHONPATH=<full>:services/admin-web-ui/tests python -m unittest test_main -v
→ Ran 3 tests in 1.019s — OK

PYTHONPATH=<full> python3 scripts/scan_rbac_annotations.py
→ OK: all 9 admin API endpoints have RBAC annotations
```

### Regression Tests

```
PYTHONPATH=<full>:services/admin-web-ui/tests python -m unittest test_dashboard_logs test_dashboard_reports test_dashboard_audit test_server test_main test_dashboard -v
→ Ran 90 tests in 1.040s — OK
```

## Post-Conditions Check

1. **RBAC CI scan passes** — exit 0, all 9 endpoints annotated ✅
2. **All new tests pass** — test_session (20), test_identity extended (7 new), test_auth_session (24) ✅
3. **Existing tests still pass** — 87 rbac tests, 90 admin-web-ui regression tests ✅
4. **No new dependencies** — stdlib only (http.cookies, secrets, threading, hmac) ✅
5. **Bearer priority preserved** — test_bearer_takes_priority_over_cookie ✅
6. **Single Identity, single guard** — cookie auth goes through RbacGuard ✅
7. **Session fixation prevention** — test_session_fixation_prevention (different sids) ✅
8. **Logout invalidation** — test_post_logout_invalidates_session (old cookie rejected) ✅
9. **CSRF protection** — login (anonymous identity, /login route), logout (authenticated, /logout), GET /logout → 405 ✅
10. **Cookie security attributes** — HttpOnly, SameSite=Strict, Path=/, Max-Age=TTL always; Secure conditional ✅
11. **CSP compliance** — CSP header set on every response, HTML-escaped content, no inline JS ✅
12. **Env credentials** — ADMIN_USERNAME (default "admin"), ADMIN_PASSWORD (no default = disabled), SESSION_TTL_SECONDS (default 28800), hmac.compare_digest ✅

## Commits

1. `feat(85): session store + HMAC-signed session cookie in rbac package`
2. `feat(85): login/logout pages, handlers, and session wiring in admin-web-ui`
