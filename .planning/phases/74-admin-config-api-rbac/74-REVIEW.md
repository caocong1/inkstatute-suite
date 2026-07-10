---
phase: 74-admin-config-api-rbac
reviewed: 2026-07-10T08:08:42Z
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
status: issues_found
---

# Phase 74: Code Review Report

**Reviewed:** 2026-07-10T08:08:42Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 74's RBAC matrix/route wiring and auth→dispatch pipeline are sound: `/config` is ADMIN+OPERATOR-only, operational PUT correctly returns 405 after auth, and flag-OFF writes map through `OperatorConfigStore.save`. The critical defect is in section-body normalization — wrapped or full-document-shaped PUT bodies for non-`providers` sections return **200 while silently resetting the section to schema defaults** (data loss). Client shape errors from `document_from_payload` are also mis-mapped to HTTP 500.

## Critical Issues

### CR-01: Wrapped / full-document PUT bodies silently wipe config sections

**File:** `services/admin-console-api/src/admin_console_api/config_api.py:104-126`
**Issue:** `_normalize_section_body` only unwraps `providers`. For `channels` / `catalog` / `vision`, any JSON object is accepted as the section value. A common client shape `{"channels": {…}}` or a full-document body (`channels`+`providers`+`catalog`+`vision`) is stored under `payload["channels"]` as nested/wrong structure. `document_from_payload` then fills missing `qqbot`/`wecom` (etc.) with defaults and `store.save` succeeds with **200**, wiping previously configured refs. Reproduced: seed channels → PUT wrapped body → GET shows `enabled=false`, `app_id_ref=null`.
**Fix:** Normalize object sections like providers: unwrap a single-key `{section: <object>}` once; reject bodies that look like multi-section documents (other `CONFIG_SECTIONS` keys present) with `400 invalid_config`. Add regression tests for wrapped channels and full-document-shaped PUT.

```python
def _normalize_section_body(section: str, body: Any) -> tuple[Any, dict[str, Any] | None]:
    if section == "providers":
        # existing list / {"providers": [...]} handling
        ...

    if not isinstance(body, Mapping):
        return None, _error("invalid_config", f"{section} section body must be a JSON object")

    foreign = (CONFIG_SECTIONS - {section}) & set(body.keys())
    if foreign:
        return None, _error(
            "invalid_config",
            f"{section} body must be the section value only (unexpected keys: {sorted(foreign)})",
        )

    if set(body.keys()) == {section} and isinstance(body[section], Mapping):
        return dict(body[section]), None

    return dict(body), None
```

## Warnings

### WR-01: Client shape errors from `document_from_payload` mapped to HTTP 500

**File:** `services/admin-console-api/src/admin_console_api/config_api.py:69-83`
**Issue:** Malformed section payloads that pass the shallow Mapping/list check (e.g. `{"qqbot": "bad"}`, `providers: ["not-obj"]`, `{"provider_id": 123}`) raise `OperatorConfigStoreError` inside `document_from_payload`. The handler maps all `OperatorConfigStoreError` to `500 config_store_error`, treating client input faults as server failures. True I/O failures from `store.load`/`save` should remain 500; parse/shape faults should be `400 invalid_config`.
**Fix:** Catch shape/parse failures around `document_from_payload` (and optionally classify StoreError messages that are field-shape diagnostics) and return 400; keep 500 only for load/save I/O StoreErrors. Add tests asserting 400 for nested bad shapes.

```python
try:
    current = store.load()
except OperatorConfigValidationError as exc:
    return 400, _error("invalid_config", str(exc))
except OperatorConfigStoreError as exc:
    return 500, _error("config_store_error", _safe_store_message(exc))

try:
    payload = document_to_payload(current)
    payload[section] = section_value
    updated = document_from_payload(payload)
except OperatorConfigStoreError as exc:
    return 400, _error("invalid_config", str(exc))

try:
    store.save(updated, feature_flags=feature_flags)
except OperatorConfigDisabledError:
    ...
except OperatorConfigValidationError as exc:
    return 400, _error("invalid_config", str(exc))
except OperatorConfigStoreError as exc:
    return 500, _error("config_store_error", _safe_store_message(exc))
```

---

_Reviewed: 2026-07-10T08:08:42Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
