---
phase: 86-product-polish
reviewed: 2026-07-15T08:30:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - services/admin-web-ui/src/admin_web_ui/dashboard.py
  - services/admin-web-ui/src/admin_web_ui/server.py
  - services/admin-web-ui/src/admin_web_ui/channels.py
  - services/admin-web-ui/src/admin_web_ui/providers.py
  - services/admin-web-ui/src/admin_web_ui/catalog.py
  - services/admin-web-ui/src/admin_web_ui/vision.py
  - services/admin-web-ui/src/admin_web_ui/logs.py
  - services/admin-web-ui/src/admin_web_ui/audit.py
  - services/admin-web-ui/src/admin_web_ui/auth.py
  - services/admin-web-ui/src/admin_web_ui/processes.py
  - services/admin-web-ui/tests/test_dashboard.py
  - services/admin-web-ui/tests/test_server.py
  - services/admin-web-ui/tests/test_auth_session.py
  - services/admin-web-ui/tests/test_startup_script.py
  - services/admin-web-ui/tests/test_env_docs.py
  - scripts/start-console.sh
  - .env.example
findings:
  critical: 0
  warning: 1
  info: 4
  total: 5
status: issues_found
wr01_fixed: 2026-07-15T09:05:00Z
wr01_fix_verification: "267 unittest pass (was 266; +1 regression test test_config_renderers_mark_active_nav_on_success_path)"
---

# Phase 86: Code Review Report

**Reviewed:** 2026-07-15T08:30:00Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Phase 86 (Product Polish) delivers dedicated SSR error pages (404/500/413), responsive CSS fixes, nav active-state highlighting, auth-aware Login/Logout nav items, a one-click startup script, and complete env documentation. The implementation is generally solid — HTML escaping is consistently applied, the 500 handler correctly logs tracebacks to stderr only (no stack trace leak to browser), CSP headers are present on all responses including error pages, and the startup script uses strict bash mode with proper trap cleanup.

One Warning-level defect was found: three config page renderers (`channels.py`, `providers.py`, `catalog.py`) pass `active_path` on their **error** code path but NOT on their **success** code path. This means the nav active-state highlighting (POLISH-02's core feature) only works when these pages render errors — the exact opposite of the intended behavior. On normal page views (the common case), the current page's nav item is not highlighted. The test suite does not catch this because `TestNavActiveState` tests `_page_template` directly rather than through the `render_*_page` functions.

No Critical issues were found. The privacy/scrubbing constraint (no stack traces or secrets to browser) is properly enforced. The stdlib-only constraint is respected. Gate honesty language is preserved.

## Warnings

### WR-01: Missing `active_path` on success render path in channels.py, providers.py, catalog.py

**Status:** FIXED 2026-07-15T09:05:00Z
**Fix verification:** 267 unittest pass (was 266; +1 regression test `test_config_renderers_mark_active_nav_on_success_path` in `test_dashboard.py::TestNavActiveState`). The new test calls `render_channels_page`, `render_providers_page`, and `render_catalog_page` on the success path and asserts the active nav link has `class="nav-link active"` + `aria-current="page"`.

**File:** `services/admin-web-ui/src/admin_web_ui/channels.py:361`, `services/admin-web-ui/src/admin_web_ui/providers.py:499`, `services/admin-web-ui/src/admin_web_ui/catalog.py:280`
**Issue:** All three config page renderers have two code paths in `render_*_page`:
1. **Error path** — passes `active_path` to `_page_template` (correct)
2. **Success/normal path** — does NOT pass `active_path` to `_page_template` (bug)

This means the nav active-state highlighting (POLISH-02's core deliverable) only works when these pages render an error response. On normal page views — the common case — the current page's nav item is NOT highlighted with `class="nav-link active"` or `aria-current="page"`.

Specific lines:
- `channels.py:361`: `return _page_template(PAGE_TITLE, body, identity)` — missing `active_path="/config/channels"`
- `providers.py:499`: `return _page_template(PAGE_TITLE, body, identity)` — missing `active_path="/config/providers"`
- `catalog.py:280`: `return _page_template(PAGE_TITLE, body, identity)` — missing `active_path="/config/catalog"`

The test suite does not catch this because `TestNavActiveState.test_active_link_has_aria_current` tests `_page_template` directly (not through `render_*_page`), and no integration test verifies `active_path` propagation through the config page renderers.

**Fix:**
```python
# channels.py:361
return _page_template(PAGE_TITLE, body, identity, active_path="/config/channels")

# providers.py:499
return _page_template(PAGE_TITLE, body, identity, active_path="/config/providers")

# catalog.py:280
return _page_template(PAGE_TITLE, body, identity, active_path="/config/catalog")
```

## Info

### IN-01: `head_extras` parameter injected into `<head>` without escaping

**File:** `services/admin-web-ui/src/admin_web_ui/dashboard.py:113`
**Issue:** The `head_extras` parameter is interpolated directly into the `<head>` block (`{head_extras}`) without any escaping. This is by design — it needs to inject a `<meta http-equiv="refresh">` tag for the logs page auto-polling. Currently safe because `head_extras` is only passed by `logs.py`'s `_logs_page_template` with a static string. However, the function signature and docstring do not warn that this parameter accepts raw HTML and must never receive user-controlled data. If user-controlled data ever flows into `head_extras`, it would be an XSS vector that bypasses CSP (the meta tag is in `<head>` before the CSP header is enforced by the browser).
**Fix:** Add a docstring note to `_page_template`: `head_extras: Raw HTML to inject into <head>. MUST NOT contain user-controlled data — this bypasses HTML escaping by design.`

### IN-02: Inconsistent `_esc` implementations across modules

**File:** `services/admin-web-ui/src/admin_web_ui/logs.py:30-37`, `services/admin-web-ui/src/admin_web_ui/processes.py:37-44`
**Issue:** `logs.py` and `processes.py` define their own `_esc` function using manual `.replace()` calls that escape `&`, `<`, `>`, `"` but NOT single quotes (`'`). Meanwhile, `dashboard.py` uses `html.escape(str(value))` which (with default `quote=True`) escapes all five characters including `'`. The custom implementations are safe for current usage (all attributes use double quotes), but the inconsistency is a latent risk if single-quoted attributes are introduced later. `channels.py`, `providers.py`, `catalog.py`, and `vision.py` use `html.escape(str(value), quote=True)` which is the safest variant.
**Fix:** Replace the custom `_esc` in `logs.py` and `processes.py` with `html.escape(str(value), quote=True)` for consistency, or import `_esc` from `dashboard.py`.

### IN-03: `test_500_on_uncaught_exception` tests `render_error_page` directly, not the `_dispatch` exception path

**File:** `services/admin-web-ui/tests/test_server.py:412-421`
**Issue:** The test named `test_500_on_uncaught_exception` calls `render_error_page(500, ...)` directly rather than triggering an actual exception through `handle_admin_web_ui_request` or `_dispatch`. It verifies that `render_error_page` can produce a 500 page, but does NOT verify that the `_dispatch` try/except actually catches exceptions and calls `render_error_page`. A real bug in the `_dispatch` error handling (e.g., the try block not wrapping the right code, or the except block having a typo) would not be caught. The companion test `test_500_try_except_exists_in_dispatch` provides source-level string checking, which gives partial coverage but cannot verify runtime behavior.
**Fix:** Add a test that passes a `handle_admin_get` callable that raises an exception, then verifies the response is a 500 with the generic error page (not a crash or stack trace leak).

### IN-04: 404 handler renders with `identity=None` before RBAC auth

**File:** `services/admin-web-ui/src/admin_web_ui/server.py:292-298`
**Issue:** The 404 handler is reached at line 291 (route resolution) before the RBAC auth step at line 317. It renders `render_error_page(404, ..., identity=None)`, so an authenticated user hitting an unknown route sees the anonymous nav (Login link instead of Logout) and no identity bar. This is a minor UX issue, not a security concern — the user remains authenticated for other requests. The 500 handler in `_dispatch` has the same pattern (`identity=None`), which is correct since the exception may occur before or after auth resolution.
**Fix:** This is an acceptable design trade-off (early 404 before auth avoids unnecessary auth work for non-existent routes). If improved UX is desired, move the 404 check after auth resolution and pass the resolved identity.

---

_Reviewed: 2026-07-15T08:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
