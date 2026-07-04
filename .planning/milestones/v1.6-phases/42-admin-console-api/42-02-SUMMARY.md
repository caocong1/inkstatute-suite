---
phase: 42
plan: 42-02
title: "Health/Status Views with Field Allowlist (Exclude Secrets) and Gate Status via Subprocess"
wave: 2
requirements:
  - ADMIN-02
  - SC3
status: complete
autonomous: true
---

# Plan 42-02 — Summary

## Tasks Completed

| Task ID | Description | Commit |
|---------|-------------|--------|
| 42-02-01 | `health.py` with positive field allowlist (`HEALTH_ALLOWED_FIELDS`) + `test_health.py` (19 tests) | `8619712` |
| 42-02-02 | `gates.py` with subprocess isolation (`run_gate_summary` via `subprocess.run`) + `test_gates.py` (11 tests) | `b16876d` |
| 42-02-03 | Wire `/health` and `/gates` routes in `api.py`, update `__init__.py` exports + `test_api.py` | `876e83b` |
| 42-02-04 | `test_health_allowlist_integration.py` — end-to-end allowlist + gates integration (12 tests) | `2fdd7a6` |

## Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| test_health.py | 19 | PASS |
| test_gates.py | 11 (1 skipped with SKIP_GATE_TESTS) | PASS |
| test_api.py | 10 (1 skipped with SKIP_GATE_TESTS) | PASS |
| test_health_allowlist_integration.py | 12 | PASS |
| **Admin Console API total** | **52** (2 skipped) | **PASS** |
| Full V2 gate suite (13 gates) | — | PASS (exit 0) |

## Files Created

- `services/admin-console-api/src/admin_console_api/health.py` — positive field allowlist (`HEALTH_ALLOWED_FIELDS`), `project_health()`, `collect_raw_health()`, `handle_health()`
- `services/admin-console-api/src/admin_console_api/gates.py` — `run_gate_summary()` via `subprocess.run` (300s timeout, `capture_output=True`), `handle_gates()`
- `services/admin-console-api/tests/test_health.py` — allowlist exclusion tests (19 tests)
- `services/admin-console-api/tests/test_gates.py` — subprocess isolation tests (11 tests)
- `services/admin-console-api/tests/test_health_allowlist_integration.py` — end-to-end integration tests (12 tests)

## Files Modified

- `services/admin-console-api/src/admin_console_api/api.py` — replaced `/health` and `/gates` 501 placeholders with `handle_health()` and `handle_gates()` calls
- `services/admin-console-api/src/admin_console_api/__init__.py` — added exports for `handle_health`, `project_health`, `HEALTH_ALLOWED_FIELDS`, `handle_gates`, `run_gate_summary`
- `services/admin-console-api/tests/test_api.py` — replaced 501 placeholder tests with 200 response tests + allowlist verification tests

## Key Implementation Details

### Health Allowlist (ADMIN-02)
- `HEALTH_ALLOWED_FIELDS` is a **positive filter** — only `service`, `status`, `version`, `secrets_configured`, `uptime_seconds`, `gate_count`, `gates_passed`, `gates_failed` are exposed.
- `HEALTH_EXCLUDED_FIELDS` documents the excluded fields for clarity, but the allowlist is the enforcement mechanism.
- `project_health()` silently drops any field not in the allowlist (no raise — health views should not crash).
- `collect_raw_health()` intentionally includes `secret_refs_configured`, `api_base_url`, and `config_path` in the raw dict to prove the allowlist excludes them.
- Only `secrets_configured: true/false` (boolean) is exposed as the secret-related field.

### Gate Subprocess Isolation (SC3)
- `run_gate_summary()` runs `scripts/run_v2_gates.py --json-summary` via `subprocess.run` with `capture_output=True` and `timeout=300`.
- No gate internals are imported in the admin-console-api process — the subprocess loads gate modules in a separate process.
- Timeout and JSON parse errors are handled gracefully (returns error dict, never raises).
- Raw stdout/stderr is never exposed in the API response.
- `run_v2_gates.py` already had `--json-summary` support — no modification needed.

## Deviations

1. **`test_gates_returns_200` uses mock**: The plan suggested either mocking `run_gate_summary` or skipping with `SKIP_GATE_TESTS`. The test mocks `run_gate_summary` AND is decorated with `@unittest.skipIf(SKIP_GATE_TESTS)` for fast-feedback mode, ensuring it passes in both modes.

2. **`gates_failed` calculation**: The plan specified `_count_gates(gates, exit_code)` helper for counting by exit code. `gates_failed` is computed as `len(gates) - _count_gates(gates, 0)` which is equivalent to counting non-zero exit codes and handles edge cases cleanly.

## Contract Freeze Verification

- No changes to `packages/platform-contract/` or `packages/platform-runtime/protocols.py`.
- No changes to `packages/platform-runtime/src/platform_runtime/feature_flags.py` — `admin_api_enabled` flag reused as-is.
- No changes to `scripts/run_v2_gates.py` — `--json-summary` flag already existed.
- `pyproject.toml` has `dependencies = []` — no new dependencies.
- All 13 existing V2 gates pass (exit 0).

## EXECUTION COMPLETE
