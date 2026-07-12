---
phase: 74-admin-config-api-rbac
fixed: 2026-07-10T08:10:33Z
source_review: 74-REVIEW.md
findings_fixed:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: fixed
---

# Phase 74: Code Review Fix Report

**Fixed:** 2026-07-10T08:10:33Z
**Source:** `74-REVIEW.md`
**Status:** fixed

## Fixes Applied

### CR-01 — Silent wipe on wrapped / full-document PUT bodies

**Severity:** critical  
**Commit:** `c2c4e13` — `fix(74): prevent silent wipe on wrapped config PUT bodies`

**Change:**
- `_normalize_section_body` now unwraps single-key `{section: <object>}` for object sections (parity with providers).
- Bodies that include other `CONFIG_SECTIONS` keys are rejected with `400 invalid_config` (no store write).
- Providers unwrap also rejects foreign section keys.

**Tests:**
- `test_wrapped_channels_body_unwraps_without_wipe`
- `test_full_document_shaped_channels_put_rejected`

### WR-01 — Client shape errors returned as HTTP 500

**Severity:** warning  
**Commit:** `3b3db57` — `fix(74): map config section shape errors to 400`

**Change:**
- `handle_config_put` separates `store.load`, `document_from_payload`, and `store.save` exception paths.
- `OperatorConfigStoreError` from `document_from_payload` → `400 invalid_config`.
- Load/save I/O StoreErrors remain `500 config_store_error`.

**Tests:**
- `test_nested_shape_errors_return_400_not_500` (channels / providers / catalog cases)

## Verification

```text
python -m unittest services.admin-console-api.tests.test_config_api -q
# Ran 11 tests — OK
```

## Remaining

None — all CRITICAL and WARNING findings from `74-REVIEW.md` are fixed.

---

_Fixed: 2026-07-10T08:10:33Z_
_Fixer: Claude (gsd-code-fixer)_
