---
phase: 74-admin-config-api-rbac
reviewed: 2026-07-10T08:08:42Z
fixed: 2026-07-10T08:10:33Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - services/admin-console-api/src/admin_console_api/config_api.py
  - services/admin-console-api/src/admin_console_api/api.py
  - services/admin-console-api/src/admin_console_api/__init__.py
  - services/admin-console-api/src/admin_console_api/routes.py
  - packages/rbac/src/rbac/matrix.py
  - scripts/run_v2_gates.py
  - services/admin-console-api/tests/test_config_api.py
  - services/admin-console-api/tests/test_read_only.py
  - services/admin-console-api/tests/test_rbac_integration.py
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: fixed
---

# Phase 74: Code Review Report

**Reviewed:** 2026-07-10T08:08:42Z
**Fixed:** 2026-07-10T08:10:33Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** fixed

## Summary

Phase 74's RBAC matrix/route wiring and auth→dispatch pipeline are sound: `/config` is ADMIN+OPERATOR-only, operational PUT correctly returns 405 after auth, and flag-OFF writes map through `OperatorConfigStore.save`. Review found two defects in `config_api.py` section PUT handling; both are fixed (see `74-REVIEW-FIX.md`).

## Critical Issues

### CR-01: Wrapped / full-document PUT bodies silently wipe config sections — FIXED

**File:** `services/admin-console-api/src/admin_console_api/config_api.py:104-126`
**Issue:** `_normalize_section_body` only unwrapped `providers`. Wrapped `{"channels": {…}}` or full-document bodies returned **200** while resetting the section to schema defaults.
**Fix applied:** Unwrap single-key `{section: object}` for object sections; reject bodies containing other `CONFIG_SECTIONS` keys with `400 invalid_config`. Regression tests cover wrap + full-document shapes.
**Commit:** `c2c4e13`

## Warnings

### WR-01: Client shape errors from `document_from_payload` mapped to HTTP 500 — FIXED

**File:** `services/admin-console-api/src/admin_console_api/config_api.py:69-83`
**Issue:** Malformed nested section payloads raised `OperatorConfigStoreError` and were returned as `500 config_store_error`.
**Fix applied:** Split load / `document_from_payload` / save exception handling; map payload shape StoreErrors to `400 invalid_config`; keep 500 for load/save I/O.
**Commit:** `3b3db57`

---

_Reviewed: 2026-07-10T08:08:42Z_
_Fixed: 2026-07-10T08:10:33Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
