---
phase: 73-operator-config-foundation
reviewed: 2026-07-10T07:36:31Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - packages/operator-config/src/inkstatute_operator_config/__init__.py
  - packages/operator-config/src/inkstatute_operator_config/errors.py
  - packages/operator-config/src/inkstatute_operator_config/schemas.py
  - packages/operator-config/src/inkstatute_operator_config/secrets.py
  - packages/operator-config/src/inkstatute_operator_config/validate.py
  - packages/operator-config/src/inkstatute_operator_config/store.py
  - packages/operator-config/src/inkstatute_operator_config/flags.py
  - packages/operator-config/pyproject.toml
  - packages/platform-runtime/src/platform_runtime/feature_flags.py
  - scripts/run_v2_gates.py
  - .gitignore
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: findings
---

# Phase 73: Code Review Report

**Reviewed:** 2026-07-10T07:36:31Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** findings

## Summary

Reviewed the Phase 73 operator-config foundation (`packages/operator-config/`), plus `operator_config_enabled` on `RuntimeFeatureFlags`, the V2 gate registration, and gitignore entries. Flag gating, atomic `.tmp` + `os.replace` writes, and Hermes path substring bans on the validate/save path are sound. The main defect is an incomplete raw-secret key ban-list: channel credential names that parallel the schema (`app_secret`, `encoding_aes_key`, `token_secret`) can be persisted under `metadata` when the flag is ON, breaking CFG-01 refs-only. Load also returns unvalidated documents, and payload parsing has several fail-open / silent-drop edge cases.

## Critical Issues

### CR-01: Incomplete raw-secret key ban-list allows persisting channel secrets in metadata

**File:** `packages/operator-config/src/inkstatute_operator_config/validate.py:44-56`
**Issue:** `FORBIDDEN_RAW_SECRET_KEYS` bans `api_key`, `token`, `password`, `bot_secret`, etc., but omits the non-`_ref` names that mirror this package’s own credential fields: `app_secret`, `encoding_aes_key`, and `token_secret`. Nested metadata walk only exact-matches keys, so a document like `QQBotChannelDoc(metadata={"app_secret": "<raw>"})` passes `validate_document` and is written by `OperatorConfigStore.save` when `operator_config_enabled` is True. Confirmed by runtime probe: raw `app_secret`, `encoding_aes_key`, and `token_secret` all persist to JSON. This violates CFG-01 (“secret refs only / never store raw secret values”).
**Fix:** Expand the ban-list to cover schema-parallel credential names (and prefer rejecting any metadata key that equals a known credential stem or ends with `_secret` without `_ref`):

```python
FORBIDDEN_RAW_SECRET_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "token",
        "token_secret",
        "password",
        "bot_secret",
        "app_secret",
        "encoding_aes_key",
        "aes_key",
        "client_secret",
        "raw_payload",
        "raw_body",
        "secret",
        "private_key",
    }
)
```

Add negative tests that attempt `save`/`validate_document` with each key under `channels.*.metadata` and assert `raw_secret_key_forbidden` with no value echo.

## Warnings

### WR-01: `load()` / `document_from_payload` never run `validate_document`

**File:** `packages/operator-config/src/inkstatute_operator_config/store.py:133-146`
**Issue:** `OperatorConfigStore.load` parses JSON into an `OperatorConfigDocument` and returns it without validation. A hand-edited or corrupted store file can contain Hermes path authority or raw secrets in `metadata` and still be returned as the InkStatute config SoT. `validate_document` would reject the same payload, but consumers of `load()` (Phase 75 apply path) will not see that failure unless they re-validate.
**Fix:** Validate after parse (fail-closed), or return a validated document only:

```python
def load(self) -> OperatorConfigDocument:
    if not self.path.is_file():
        return OperatorConfigDocument()
    # ... read + json.loads ...
    document = document_from_payload(payload)
    validate_document(document)
    return document
```

### WR-02: Non-string `*_ref` values crash with `AttributeError` instead of validation errors

**File:** `packages/operator-config/src/inkstatute_operator_config/secrets.py:39-43` (via `store.py:97-110`)
**Issue:** `document_from_payload` assigns `*_ref` fields with raw `dict.get` results and does not coerce/check types. A JSON number/bool/object in `app_id_ref` becomes a non-`str` on the dataclass. `normalize_config_secret_ref` then calls `.strip()` and raises `AttributeError`, which `_check_credential_refs` does not catch (only `InvalidSecretRefError`). Save/validate then fails with an unexpected exception instead of `OperatorConfigValidationError` / `invalid_secret_ref`.
**Fix:** Coerce or reject non-strings at the normalize boundary:

```python
def normalize_config_secret_ref(raw: str | None, *, field: str) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise InvalidSecretRefError(f"invalid secret reference shape for {field}")
    ref = raw.strip()
    # ...
```

Also coerce optional string fields in `document_from_payload` (or reject with `OperatorConfigStoreError`).

### WR-03: `document_from_payload` raises raw `ValueError` / silently drops bad providers

**File:** `packages/operator-config/src/inkstatute_operator_config/store.py:55-124`
**Issue:**
1. `metadata=dict(item.get("metadata") or {})` raises bare `ValueError` when `metadata` is a non-mapping string/list.
2. `schema_version=int(...)` raises bare `ValueError` on non-numeric input.
3. Provider entries that are not mappings are skipped with `if isinstance(item, Mapping)` — corrupt list items disappear with no error (silent data loss).

These bypass `OperatorConfigStoreError` and make load/parse failures inconsistent with the package error hierarchy.
**Fix:** Wrap coercions and reject bad shapes explicitly:

```python
def _as_object(value: object, label: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise OperatorConfigStoreError(f"{label} must be an object")
    return value

# providers: require every element to be a mapping
for index, item in enumerate(providers_raw):
    if not isinstance(item, Mapping):
        raise OperatorConfigStoreError(f"providers[{index}] must be an object")
```

### WR-04: Runtime `.tmp` sibling not gitignored

**File:** `.gitignore:20-22`
**Issue:** Ignore rules cover `.inkstatute/operator-config.json` and `operator-config.json`, but atomic writes use `operator-config.json.tmp` (`store.py:166`). A failed write that leaves the sibling (or a crash between `write_text` and cleanup) can leave a runtime config file that is not ignored and could be committed.
**Fix:** Add patterns for the temp sibling:

```gitignore
.inkstatute/operator-config.json
.inkstatute/operator-config.json.tmp
operator-config.json
operator-config.json.tmp
```

## Info

### IN-01: Frozen dataclasses still expose mutable `metadata` dicts

**File:** `packages/operator-config/src/inkstatute_operator_config/schemas.py:38`
**Issue:** `frozen=True` does not deep-freeze `metadata: dict`. Callers can mutate `doc.channels.qqbot.metadata` after construction (including between `validate_document` and `asdict` in `save`). Low practical risk in single-threaded hosts, but weakens the “immutable document” contract.
**Fix:** Document that metadata must be treated as immutable, or copy metadata at validate/save boundaries (`metadata=dict(metadata)` / `MappingProxyType`).

### IN-02: Comment vs regex mismatch for `secret://` segment count

**File:** `packages/operator-config/src/inkstatute_operator_config/secrets.py:19-23`
**Issue:** Comment says “one or more slash-separated segments”; the regex requires a first segment plus `(?:/…)+` (two or more). Docstring correctly says two+. Harmless but confusing for maintainers.
**Fix:** Align the comment with the docstring/regex (“two or more slash-separated safe segments”).

---

_Reviewed: 2026-07-10T07:36:31Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
