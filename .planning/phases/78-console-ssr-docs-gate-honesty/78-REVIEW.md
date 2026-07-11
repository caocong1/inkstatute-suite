---
phase: 78-console-ssr-docs-gate-honesty
reviewed: 2026-07-11T21:35:36Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - services/admin-web-ui/src/admin_web_ui/server.py
  - services/admin-web-ui/src/admin_web_ui/dashboard.py
  - services/admin-web-ui/src/admin_web_ui/channels.py
  - services/admin-web-ui/src/admin_web_ui/providers.py
  - services/admin-web-ui/src/admin_web_ui/catalog.py
  - services/admin-web-ui/src/admin_web_ui/vision.py
  - services/admin-web-ui/src/admin_web_ui/api_client.py
  - services/admin-web-ui/src/admin_web_ui/csrf.py
  - services/admin-web-ui/src/admin_web_ui/boundary.py
  - services/admin-web-ui/tests/test_dashboard.py
  - services/admin-web-ui/tests/test_channels_form.py
  - services/admin-web-ui/tests/test_providers_form.py
  - services/admin-web-ui/tests/test_catalog_form.py
  - services/admin-web-ui/tests/test_vision_form.py
  - services/admin-console-api/src/admin_console_api/api.py
  - services/admin-console-api/src/admin_console_api/config_api.py
  - services/admin-console-api/src/admin_console_api/probe.py
  - packages/operator-config/src/inkstatute_operator_config/flags.py
  - services/admin-web-ui/README.md
  - runbook/OPERATOR_CONFIG_RUNBOOK.md
  - .planning/phases/78-console-ssr-docs-gate-honesty/78-UI-SPEC.md
findings:
  critical: 1
  warning: 0
  info: 0
  total: 1
status: issues_found
---

# Phase 78: Code Review Report

**Reviewed:** 2026-07-11T21:35:36Z
**Depth:** standard
**Files Reviewed:** 21
**Status:** issues_found

## Summary

Phase 78 delivers the SSR operator config console (`/config/*`) with CSRF tokens, gate-honesty notices, and operator docs. The implementation correctly escapes dynamic output and does not use inline scripts. However, the Content-Security-Policy sent on every response forbids inline styles, while every page renders its CSS through an inline `<style>` block in `_page_template`. This breaks the console's styling in any browser that enforces CSP. The README and UI-SPEC contract repeat the same overly strict CSP, so the policy and documentation need to be aligned.

## Critical Issues

### CR-01: CSP blocks inline SSR style blocks, breaking the UI

**File:** `services/admin-web-ui/src/admin_web_ui/server.py:73`
**Issue:** `CSP_HEADER` is set to `default-src 'self'; script-src 'self'; style-src 'self'`. The SSR templates in `dashboard.py`, `channels.py`, `providers.py`, `catalog.py`, and `vision.py` all embed CSS in inline `<style>` blocks (e.g. `dashboard.py` `_page_template` lines 500-570). A `style-src 'self'` directive does not allow inline `<style>` blocks, so browsers that enforce CSP will drop the console's CSS. The README and UI-SPEC contract quote the same CSP, so the docs are inconsistent with the implementation.

**Fix:**

1. Update `CSP_HEADER` in `services/admin-web-ui/src/admin_web_ui/server.py` to allow inline styles while keeping inline scripts forbidden:

```python
CSP_HEADER = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
```

2. Update `services/admin-web-ui/README.md` line 7 to quote the same CSP string.
3. Update `.planning/phases/78-console-ssr-docs-gate-honesty/78-UI-SPEC.md` line 276 to `style-src 'self' 'unsafe-inline'`. The "no inline scripts" and "no `innerHTML` of untrusted data" invariants remain valid.

---

_Reviewed: 2026-07-11T21:35:36Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
