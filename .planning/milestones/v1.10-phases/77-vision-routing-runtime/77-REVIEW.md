---
status: clean
phase: 77
phase_name: vision-routing-runtime
depth: standard
files_reviewed: 15
files_reviewed_list:
  - packages/operator-config/src/inkstatute_operator_config/validate.py
  - packages/operator-config/src/inkstatute_operator_config/schemas.py
  - packages/operator-config/tests/test_validate_document.py
  - packages/operator-config/tests/test_schemas.py
  - packages/operator-config/tests/test_store.py
  - services/admin-console-api/src/admin_console_api/config_api.py
  - services/admin-console-api/tests/test_config_vision.py
  - services/admin-console-api/tests/test_config_probe.py
  - packages/platform-runtime/src/platform_runtime/vision_router.py
  - packages/platform-runtime/src/platform_runtime/__init__.py
  - packages/platform-runtime/tests/test_vision_router.py
  - services/admin-web-ui/src/admin_web_ui/vision.py
  - services/admin-web-ui/src/admin_web_ui/server.py
  - services/admin-web-ui/src/admin_web_ui/dashboard.py
  - services/admin-web-ui/tests/test_vision_form.py
critical: 0
warning: 0
info: 0
total: 0
---

# Phase 77 Code Review — Vision Routing Runtime

## Summary

Reviewed the 15 source and test files changed across the four Phase 77 plans
(77-01 through 77-04) for bugs, security issues, and code quality. All package
test suites pass after the fixes.

- operator-config: 110 passed, 71 subtests passed
- platform-runtime: 399 passed, 3 skipped, 182 subtests passed
- admin-console-api: 262 passed, 1 skipped, 37 subtests passed
- admin-web-ui: 137 passed, 5 subtests passed

## Fixed during review

The following items were found and addressed automatically (up to 3 iterations
of review/fix/re-review). No remaining findings of `critical`, `warning`, or
`info` severity remain.

### 1. Wrapped section bodies did not enforce allowed keys

- **File:** `services/admin-console-api/src/admin_console_api/config_api.py`
- **Issue:** `_normalize_section_body` rejected unexpected keys for direct
  `vision`/`catalog` bodies but accepted the same keys when wrapped as
  `{"vision": {"api_key": ...}}`. The wrapped branch returned the inner dict
  without applying `_SECTION_ALLOWED_KEYS`.
- **Fix:** Apply the same allowed-key check to wrapped inner dicts before
  returning `section_value`.
- **Commit:** part of `fix(77): code review fixes for phase 77`

### 2. Unreachable probe-result branches in vision UI

- **File:** `services/admin-web-ui/src/admin_web_ui/vision.py`
- **Issue:** `_probe_result_html` branched on `result["code"]`
  (`missing_ref`, `network`), but the probe handler does not return a `code`
  field, so the specific `PROBE_RESULT_FAIL_MISSING_REF` and
  `PROBE_RESULT_FAIL_NETWORK` messages were dead code.
- **Fix:** Removed the `code` variable, unreachable branches, and the two unused
  constants.
- **Commit:** `fix(77): code review fixes for phase 77`

### 3. Unused empty-heading constants

- **File:** `services/admin-web-ui/src/admin_web_ui/vision.py`
- **Issue:** `EMPTY_HEADING` and `EMPTY_BODY` were defined and exported but
  never used.
- **Fix:** Removed the unused constants.
- **Commit:** `fix(77): remove unused empty-heading constants from vision.py`

### 4. Vision form rendered editable for RBAC-forbidden users

- **File:** `services/admin-web-ui/src/admin_web_ui/vision.py`
- **Issue:** `render_vision_page` only disabled the form for
  `operator_config_disabled`; a `forbidden` response from the API left controls
  enabled with an empty CSRF token.
- **Fix:** Set `read_only = True` for both `forbidden` and
  `operator_config_disabled` API error codes.
- **Commit:** `fix(77): render vision config form as read-only for RBAC forbidden users`

### 5. Vision POST did not disable form on forbidden

- **File:** `services/admin-web-ui/src/admin_web_ui/server.py`
- **Issue:** `_handle_vision` only set `read_only` on
  `operator_config_disabled`, so a `forbidden` POST response rendered an
  editable form.
- **Fix:** Set `read_only` when `code` is `forbidden` or
  `operator_config_disabled`.
- **Commit:** `fix(77): disable vision form on POST when forbidden`

### 6. Probe CSRF failure did not re-render vision page

- **File:** `services/admin-web-ui/src/admin_web_ui/server.py`
- **Issue:** `_handle_probe` always rendered the providers page on CSRF
  failure, even when `return_to=vision`.
- **Fix:** Parse `return_to` from the rejected body and re-render the Vision
  Config error page when it is `vision`.
- **Commit:** `fix(77): re-render vision page on probe CSRF failure`

### 7. Vision router assumed `turn.attachments` is always set

- **File:** `packages/platform-runtime/src/platform_runtime/vision_router.py`
- **Issue:** `has_image_attachments` and `_image_attachment_count` iterated
  `turn.attachments` directly; a `None` value would raise `TypeError`.
- **Fix:** Use `getattr(turn, "attachments", None) or []` defensively.
- **Commit:** `fix(77): harden vision router against None attachments`

### 8. Misaligned closing parenthesis in `validate.py`

- **File:** `packages/operator-config/src/inkstatute_operator_config/validate.py`
- **Issue:** The `issues.append(...)` for `unsupported_provider_kind` had an
  extra indented closing parenthesis.
- **Fix:** Normalized indentation.
- **Commit:** `fix(77): code review fixes for phase 77`

## Remaining findings

None. Final status: `clean`.
