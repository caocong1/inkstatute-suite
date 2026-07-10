---
phase: 68-host-skeleton-safety-baseline
reviewed: 2026-07-10T04:29:30Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - services/qqbot-service/pyproject.toml
  - services/qqbot-service/README.md
  - services/qqbot-service/src/qqbot_service/__init__.py
  - services/qqbot-service/src/qqbot_service/config.py
  - services/qqbot-service/src/qqbot_service/secrets.py
  - services/qqbot-service/tests/__init__.py
  - services/qqbot-service/tests/test_host_skeleton.py
  - services/qqbot-service/tests/test_secret_refs.py
  - services/qqbot-service/tests/test_no_wecom_import.py
  - services/qqbot-service/tests/test_host_safety_baseline.py
  - scripts/run_v2_gates.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 68: Code Review Report

**Reviewed:** 2026-07-10T04:29:30Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 68 delivers a thin empty-deps `qqbot-service` host with refs-only config, process-edge resolve, ADAPTER-04 isolation tests, and V2 gate wiring (27 gates). Core layout and gate registration look sound: no `wecom_src` on the host gate, no hardcoded secrets, `resolve_secret_ref` does not read `os.environ`, and host unittests (23) pass.

Three warnings remain before later phases wire live IO: the secret map is a mutable public dict (runtime redirect of resolution), `from_env` accepts arbitrary strings into `*_ref` fields (raw secret material can land on config via mis-set `*_REF` env vars), and whitespace around refs is preserved then silently fail-closed at resolve. Recommend `--fix` for the warnings before Phase 69/70 composition.

## Warnings

### WR-01: Mutable `REF_TO_VALUE_ENV` can redirect secret resolution

**File:** `services/qqbot-service/src/qqbot_service/secrets.py:14-19`
**Issue:** The process-edge allowlist is a module-level mutable `dict` exported via `__all__`. Any importer can reassign entries and change which env key a `secret://` ref resolves to (verified: mutating `REF_TO_VALUE_ENV["secret://qqbot/app-secret"]` returns the hijacked mapping value). For a secret resolver this weakens integrity of the documented map.
**Fix:** Freeze the map and stop treating it as a writable public API:

```python
from types import MappingProxyType

REF_TO_VALUE_ENV: Mapping[str, str] = MappingProxyType(
    {
        "secret://qqbot/app-id": "INKSTATUTE_QQBOT_APP_ID",
        "secret://qqbot/app-secret": "INKSTATUTE_QQBOT_CLIENT_SECRET",
        "secret://qqbot/token": "INKSTATUTE_QQBOT_TOKEN",
        "secret://qqbot/bot-secret": "INKSTATUTE_QQBOT_BOT_SECRET",
    }
)
```

### WR-02: `from_env` stores arbitrary `*_REF` strings — raw secrets can sit on config

**File:** `services/qqbot-service/src/qqbot_service/config.py:27-35`
**Issue:** SAFE-02 / README claim that config stores references only is not enforced. `from_env` copies `INKSTATUTE_QQBOT_*_REF` values verbatim. Planting the raw secret into a `*_REF` key (common operator mistake) stores secret material on `QQBotHostConfig` and in `asdict` output. Existing tests only plant *value* env keys (`INKSTATUTE_QQBOT_BOT_SECRET`, etc.), so this gap is untested.
**Fix:** Validate ref shape in `from_env` (and/or a shared helper): accept only `None`/empty, `env:NAME`, known `secret://qqbot/…` paths, or bare env-key identifiers — reject other strings (fail closed / raise a non-secret-bearing error). Add a test that plants `INKSTATUTE_QQBOT_BOT_SECRET_REF=<raw secret>` and asserts the value is rejected or not retained on the config object.

### WR-03: Whitespace in refs is kept by `from_env` then silently fails resolve

**File:** `services/qqbot-service/src/qqbot_service/config.py:31-34`, `services/qqbot-service/src/qqbot_service/secrets.py:35-47`
**Issue:** `from_env` does not `.strip()` REF values. A padded ref such as `"  secret://qqbot/app-id  "` is stored on config, but `resolve_secret_ref` does not match `secret://` after leading spaces and returns `None` (fail closed). Operators get a silent “secret missing” failure instead of a clear config error.
**Fix:** Strip REF strings in `from_env` (and optionally strip once at the top of `resolve_secret_ref`). Prefer rejecting whitespace-only / malformed refs explicitly when validating (see WR-02).

## Info

### IN-01: `BackendAdapter` freeze checks count only, not method names

**File:** `services/qqbot-service/tests/test_host_safety_baseline.py:34-36`
**Issue:** `ChannelAdapter` asserts both `len == 6` and an exact named frozenset; `BackendAdapter` only asserts `len == 9`. A rename/swap that preserves count would not fail the host baseline.
**Fix:** Mirror the ChannelAdapter pattern with an explicit `BACKEND_ADAPTER_METHODS` frozenset (aligned with `packages/channels/qqbot/tests/test_v1_8_safety_baseline.py` if present).

### IN-02: AST / substring isolation misses dynamic imports

**File:** `services/qqbot-service/tests/test_no_wecom_import.py:12-22`
**Issue:** Same limitation as the package suite: `__import__("wecom_service")`, `importlib.import_module(...)`, and string-built imports are invisible to `ast.Import` / `ast.ImportFrom`. Acceptable for Phase 68 parity, but not a complete ADAPTER-04 runtime guarantee.
**Fix:** Optional follow-up: also ban `importlib` / `__import__` usage in host production modules, or add an import-hook smoke in later wiring phases.

### IN-03: Dead `ImportError` skip after Plan 02 merge

**File:** `services/qqbot-service/tests/test_host_safety_baseline.py:52-57`
**Issue:** `test_host_config_enabled_defaults_false_when_available` still skips if `QQBotHostConfig` cannot be imported. After Plan 02, that path is obsolete and could hide a broken package export.
**Fix:** Remove the try/except and import `QQBotHostConfig` unconditionally.

---

_Reviewed: 2026-07-10T04:29:30Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
