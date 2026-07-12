---
phase: 75-channel-config-apply
reviewed: 2026-07-10T08:40:39Z
fixed: 2026-07-10T08:43:50Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - packages/platform-runtime/src/platform_runtime/feature_flags.py
  - scripts/run_v2_gates.py
  - services/admin-console-api/src/admin_console_api/config_api.py
  - services/qqbot-service/src/qqbot_service/config.py
  - services/qqbot-service/src/qqbot_service/wiring.py
  - packages/channels/wecom/src/inkstatute_channels_wecom/config.py
  - services/wecom-service/src/wecom_service/channel_wiring.py
  - services/wecom-service/src/wecom_service/__init__.py
  - services/admin-web-ui/src/admin_web_ui/channels.py
  - services/admin-web-ui/src/admin_web_ui/api_client.py
  - services/admin-web-ui/src/admin_web_ui/dashboard.py
  - services/admin-web-ui/src/admin_web_ui/server.py
findings:
  critical: 1
  warning: 4
  info: 1
  total: 6
status: fixed
fix_report: .planning/phases/75-channel-config-apply/75-REVIEW-FIX.md
---

# Phase 75: Code Review Report

**Reviewed:** 2026-07-10T08:40:39Z
**Fixed:** 2026-07-10T08:43:50Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** fixed

## Summary

Dual-knob effective API, QQ/WeCom store-wins apply, and Channel Config SSR are largely coherent. Review found one critical silent-wipe footgun on empty SSR POST plus four warnings; all CRITICAL+WARNING findings are fixed (see `75-REVIEW-FIX.md`). CSRF remains deferred to Phase 78 (IN-01).

## Critical Issues

### CR-01: Empty / marker-less POST body silently wipes channel config — FIXED

**File:** `services/admin-web-ui/src/admin_web_ui/server.py`
**Issue:** Empty POST reached `parse_channels_form` → PUT and wiped all channel refs / disabled hosts.
**Fix applied:** `_channels_post_body_usable` requires at least one `qqbot.` / `wecom.` field; empty/marker-less POST returns `400` without calling `handle_admin_put`.
**Commit:** `435d31f`

## Warnings

### WR-01: SSR Save always clears channel `metadata` — FIXED

**File:** `services/admin-web-ui/src/admin_web_ui/server.py` / `channels.py`
**Issue:** Form parse hard-coded `metadata: {}`, wiping API-set metadata on Save.
**Fix applied:** POST path GETs current channels and merges `data.*.metadata` into the PUT payload before proxy.
**Commit:** `435d31f`

### WR-02: QQ store load crashes on operator-config-valid `secret://` refs outside host allowlist — FIXED

**File:** `services/qqbot-service/src/qqbot_service/config.py`
**Issue:** `from_operator_doc` re-allowlisted refs and raised `InvalidSecretRefError`, aborting host compose.
**Fix applied:** `_safe_host_ref` catches `InvalidSecretRefError` and returns `None` (fail closed for live IO, compose continues).
**Commit:** `f7a3290`

### WR-03: WeCom `from_operator_doc` keeps non-string ref values — FIXED

**File:** `packages/channels/wecom/src/inkstatute_channels_wecom/config.py`
**Issue:** Non-string Mapping values could land on `str | None` ref fields.
**Fix applied:** `_optional_ref` accepts strings only; otherwise `None`.
**Commit:** `8fdf21a`

### WR-04: Unbounded `Content-Length` read on channels POST — FIXED

**File:** `services/admin-web-ui/src/admin_web_ui/server.py`
**Issue:** `do_POST` read arbitrary `Content-Length` into memory.
**Fix applied:** `MAX_CHANNELS_POST_BYTES` (64 KiB); oversized/negative length returns `413` without full read.
**Commit:** `435d31f`

## Info

### IN-01: CSRF token rendered but never validated (deferred Phase 78) — OPEN

**File:** `services/admin-web-ui/src/admin_web_ui/server.py`
**Issue:** Hidden `csrf_token` is not server-validated. Explicit Phase 78 deferral.
**Fix:** Deferred — not in Phase 75 fix scope.

---

_Reviewed: 2026-07-10T08:40:39Z_
_Fixed: 2026-07-10T08:43:50Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
