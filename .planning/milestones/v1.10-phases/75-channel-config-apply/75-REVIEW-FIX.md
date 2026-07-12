---
phase: 75-channel-config-apply
fixed: 2026-07-10T08:43:50Z
source_review: 75-REVIEW.md
findings_fixed:
  critical: 1
  warning: 4
  info: 0
  total: 5
status: fixed
---

# Phase 75: Code Review Fix Report

**Fixed:** 2026-07-10T08:43:50Z
**Source:** `75-REVIEW.md`
**Status:** fixed

## Fixes Applied

### CR-01 — Empty / marker-less POST body silently wipes channel config

**Severity:** critical  
**Commit:** `435d31f` — `fix(75): harden channels SSR POST against wipe and oversized bodies`

**Change:**
- Added `_channels_post_body_usable` — requires at least one `qqbot.` / `wecom.` form field.
- Empty or marker-less POST returns `400` with validation error page; does not call `proxy_put`.

**Tests:**
- `test_empty_post_does_not_wipe_channel_config`

### WR-01 — SSR Save always clears channel `metadata`

**Severity:** warning  
**Commit:** `435d31f` — `fix(75): harden channels SSR POST against wipe and oversized bodies`

**Change:**
- Before PUT, GET current `/config/channels` and merge `data.*.metadata` via `_merge_channel_metadata_from_current`.

**Tests:**
- `test_post_preserves_existing_channel_metadata`

### WR-02 — QQ store load crashes on allowlist-mismatched `secret://` refs

**Severity:** warning  
**Commit:** `f7a3290` — `fix(75): soft-fail QQ host refs outside allowlist on store load`

**Change:**
- `_safe_host_ref` wraps `normalize_config_secret_ref`; on `InvalidSecretRefError` returns `None` so compose continues fail-closed for that ref.

**Tests:**
- `test_from_operator_doc_unknown_secret_uri_does_not_raise`

### WR-03 — WeCom `from_operator_doc` keeps non-string ref values

**Severity:** warning  
**Commit:** `8fdf21a` — `fix(75): coerce non-string WeCom from_operator_doc refs to None`

**Change:**
- `_optional_ref` accepts `str` only (strip blanks → `None`); non-strings become `None`.

**Tests:**
- `test_from_operator_doc_non_string_refs_become_none`

### WR-04 — Unbounded `Content-Length` read on channels POST

**Severity:** warning  
**Commit:** `435d31f` — `fix(75): harden channels SSR POST against wipe and oversized bodies`

**Change:**
- `MAX_CHANNELS_POST_BYTES = 64 KiB`; `do_POST` returns `413` for negative/oversized lengths without allocating the body.

**Tests:**
- `test_max_channels_post_bytes_constant`

## Verification

```text
python -m unittest services.admin-web-ui.tests.test_channels_form -q
# Ran 15 tests — OK

python -m unittest services.qqbot-service.tests.test_store_apply -q
# Ran 8 tests — OK

python -m unittest packages.channels.wecom.tests.test_from_operator_doc \
  services.wecom-service.tests.test_channel_wiring_dual_knob -q
# Ran 9 tests — OK
```

## Remaining

- **IN-01** — CSRF token not validated (deferred to Phase 78; out of fix scope).

---

_Fixed: 2026-07-10T08:43:50Z_
_Fixer: Claude (gsd-code-fixer)_
