---
phase: 68-host-skeleton-safety-baseline
fixed_at: 2026-07-10T04:32:46.329Z
review_path: .planning/phases/68-host-skeleton-safety-baseline/68-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 68: Code Review Fix Report

**Fixed at:** 2026-07-10T04:32:46.329Z
**Source review:** `.planning/phases/68-host-skeleton-safety-baseline/68-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (WR-01, WR-02, WR-03, IN-01, IN-03; IN-02 left open as optional later-phase follow-up)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### WR-01: Mutable `REF_TO_VALUE_ENV` can redirect secret resolution

**Files modified:** `services/qqbot-service/src/qqbot_service/secrets.py`
**Commit:** `2c19b87`
**Applied fix:** Wrapped the allowlist in `MappingProxyType` and typed it as `Mapping[str, str]` so importers cannot reassign entries and redirect `secret://` resolution.

### WR-02: `from_env` stores arbitrary `*_REF` strings — raw secrets can sit on config

**Files modified:** `services/qqbot-service/src/qqbot_service/secrets.py`, `services/qqbot-service/src/qqbot_service/config.py`, `services/qqbot-service/tests/test_secret_refs.py`
**Commit:** `d2ffda4`
**Applied fix:** Added `normalize_config_secret_ref` / `InvalidSecretRefError` that accept only blank, `env:NAME`, known `secret://qqbot/…` paths, or bare env-key identifiers; `from_env` uses it for all `*_REF` fields. Errors never echo rejected values. Tests plant raw secret material in `*_REF` and assert rejection without retention.

### WR-03: Whitespace in refs is kept by `from_env` then silently fails resolve

**Files modified:** `services/qqbot-service/src/qqbot_service/secrets.py`, `services/qqbot-service/tests/test_secret_refs.py`
**Commit:** `2f591a6`
**Applied fix:** Strip in `normalize_config_secret_ref` (already part of WR-02 path) and at the top of `resolve_secret_ref`. Whitespace-only refs become `None`; padded valid refs normalize cleanly. Added strip/whitespace tests for config and resolve.

### IN-01: `BackendAdapter` freeze checks count only, not method names

**Files modified:** `services/qqbot-service/tests/test_host_safety_baseline.py`
**Commit:** `d263b2f`
**Applied fix:** Added `BACKEND_ADAPTER_METHODS` frozenset (9 Protocol methods) and asserted exact name set alongside `len == 9`.

### IN-03: Dead `ImportError` skip after Plan 02 merge

**Files modified:** `services/qqbot-service/tests/test_host_safety_baseline.py`
**Commit:** `cb373d6`
**Applied fix:** Removed try/except skip; import `QQBotHostConfig` unconditionally.

## Skipped Issues

None in scope.

## Remaining open findings

### IN-02: AST / substring isolation misses dynamic imports

**File:** `services/qqbot-service/tests/test_no_wecom_import.py:12-22`
**Reason:** Optional later-phase follow-up (importlib / `__import__` bans or import-hook smoke). Left open to avoid expanding Phase 68 scope; acceptable parity limitation per review.

## Test results

Host suite after fixes (`PYTHONPATH=services/qqbot-service/src:packages/platform-runtime/src:packages/platform-contract/src`):

```text
python -m unittest discover -s services/qqbot-service/tests -p 'test_*.py' -v
Ran 28 tests in 0.004s
OK
```

---

_Fixed: 2026-07-10T04:32:46.329Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
