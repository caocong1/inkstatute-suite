---
phase: 73-operator-config-foundation
fixed_at: 2026-07-10T07:40:01Z
review_path: .planning/phases/73-operator-config-foundation/73-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
deferred_info: 2
status: all_fixed
---

# Phase 73: Code Review Fix Report

**Fixed at:** 2026-07-10T07:40:01Z
**Source review:** `.planning/phases/73-operator-config-foundation/73-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope (CR + WR): 5
- Fixed: 5
- Skipped: 0
- Info deferred: 2 (IN-01, IN-02)

## Fixed Issues

### CR-01: Incomplete raw-secret key ban-list allows persisting channel secrets in metadata

**Files modified:** `packages/operator-config/src/inkstatute_operator_config/validate.py`, `packages/operator-config/tests/test_validate_document.py`, `packages/operator-config/tests/test_store.py`
**Commit:** `3e7ba68`
**Applied fix:** Expanded `FORBIDDEN_RAW_SECRET_KEYS` with schema-parallel stems (`app_secret`, `encoding_aes_key`, `token_secret`, plus `aes_key`, `client_secret`). Added validate + save negative tests asserting `raw_secret_key_forbidden` with no value echo.

### WR-01: `load()` / `document_from_payload` never run `validate_document`

**Files modified:** `packages/operator-config/src/inkstatute_operator_config/store.py`, `packages/operator-config/tests/test_store.py`
**Commit:** `325dd3b`
**Applied fix:** `OperatorConfigStore.load` now calls `validate_document` after parse (fail-closed). Added test that a hand-edited store with `metadata.app_secret` raises `OperatorConfigValidationError` without echoing the planted value.

### WR-02: Non-string `*_ref` values crash with `AttributeError`

**Files modified:** `packages/operator-config/src/inkstatute_operator_config/secrets.py`, `packages/operator-config/tests/test_secret_refs.py`
**Commit:** `c728cea`
**Applied fix:** `normalize_config_secret_ref` rejects non-`str` inputs with `InvalidSecretRefError` before `.strip()`. Tests cover number/bool/object/list and `validate_document` → `invalid_secret_ref`.

### WR-03: `document_from_payload` raises raw `ValueError` / silently drops bad providers

**Files modified:** `packages/operator-config/src/inkstatute_operator_config/store.py`, `packages/operator-config/tests/test_store.py`
**Commit:** `d3f438a`
**Applied fix:** Added `_as_object` / `_optional_str` / `_schema_version` helpers; reject non-object metadata, non-numeric `schema_version`, and non-object provider list items via `OperatorConfigStoreError` (no silent drops).

### WR-04: Runtime `.tmp` sibling not gitignored

**Files modified:** `.gitignore`, `packages/operator-config/tests/test_store.py`
**Commit:** `c3160c8`
**Applied fix:** Added `.inkstatute/operator-config.json.tmp` and `operator-config.json.tmp` ignore patterns; test asserts both are present in `.gitignore`.

## Deferred Info (out of critical_warning scope)

### IN-01: Frozen dataclasses still expose mutable `metadata` dicts

**File:** `packages/operator-config/src/inkstatute_operator_config/schemas.py:38`
**Reason:** Low practical risk in single-threaded hosts; deep-freeze / MappingProxyType would expand schema contract beyond Phase 73 empty-deps boundary. Defer to a later hardening pass if mutation between validate and save becomes a real concern.
**Original issue:** `frozen=True` does not deep-freeze `metadata: dict`.

### IN-02: Comment vs regex mismatch for `secret://` segment count

**File:** `packages/operator-config/src/inkstatute_operator_config/secrets.py:19-23`
**Reason:** Docstring already correct (“two or more”); comment-only mismatch is harmless for runtime. Deferred as low-value info cleanup.
**Original issue:** Comment says “one or more”; regex requires two+.

---

_Fixed: 2026-07-10T07:40:01Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
