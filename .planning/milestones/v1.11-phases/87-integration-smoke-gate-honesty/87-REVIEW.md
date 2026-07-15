---
phase: 87-integration-smoke-gate-honesty
reviewed: 2026-07-15
status: clean
depth: standard
files_reviewed: 1
findings:
  critical: 0
  warning: 0
  info: 2
---

# Phase 87: Code Review

## Scope
- services/admin-web-ui/tests/test_smoke_e2e.py

## Findings

### Critical

None.

> **Note on original C-1 (retracted):** The initial review reported `test_console_smoke_e2e` as failing due to `/reports` and `/gates` hanging on subprocess-spawning `run_gate_summary()`. This was verified as a **false positive** — running the test suite directly confirms all 6 tests pass in ~4-6s with 0 failures. The `/reports` and `/gates` endpoints do not hang in the test environment. The original reviewer's claim of a `TimeoutError` could not be reproduced. C-1 is retracted.

### Warning

None.

> **Note on original W-1 (fixed):** The `_request` helper originally only caught `urllib.error.HTTPError`, not `urllib.error.URLError`/`TimeoutError`. **Fixed:** Added an `except urllib.error.URLError` branch that produces a clean `self.fail()` with the error reason, so network errors produce readable assertion failures instead of unhandled tracebacks. Verified: all 6 tests still pass after the fix.

### Info

#### I-1: Unused imports — 5 symbols imported but never referenced (FIXED)
- **File:** `services/admin-web-ui/tests/test_smoke_e2e.py`
- **Status:** Fixed — removed `issue_csrf_token`, `LogReader`, `build_read_model`, `Identity`, `Role` imports. The test extracts CSRF tokens from HTML forms and `create_server` constructs its own `LogReader`/read model internally.

#### I-2: `_write_log_lines` overwrites the contract log fixture
- **File:** `services/admin-web-ui/tests/test_smoke_e2e.py`
- **Description:** Both `_write_contract_log` and `_write_log_lines` write to the same path (`tmpdir / "events.jsonl"`). In `test_console_smoke_e2e`, the contract log is written first, audit checks pass, then `_write_log_lines` overwrites the file with plain log lines. This works because the audit checks complete before the overwrite, but is conceptually confusing. Not fixed — the ordering is intentional and the test passes; changing to a separate file path would require env reconfiguration mid-test which is more complex than the current approach.
- **Recommendation:** Consider using a distinct log file path in a future refactor if the test grows.

#### I-3: `httpd.server_close()` not called in cleanup
- **File:** `services/admin-web-ui/tests/test_smoke_e2e.py`
- **Description:** `_start` registers `httpd.shutdown` as cleanup but not `httpd.server_close()`. This is consistent with the existing `test_main.py` pattern. The OS reclaims the socket on process exit. Not fixed — matches established codebase convention.
- **Recommendation:** None — follow existing pattern.

## Summary

The test file `test_smoke_e2e.py` contains 6 test methods covering the full console smoke workflow. All 6 tests pass (verified twice: 5.881s and 4.237s, 0 failures). The primary `test_console_smoke_e2e` boots via `create_server`, logs in via POST /login with CSRF, hits all 12 surfaces (all 200), starts a wecom subprocess via POST /processes with CSRF, views scrubbed logs via GET /logs/contract_events, and audits /audit + /audit/trace-smoke-001.

The HUMAN GATE stamp (`not_live_acceptance=True`) is a genuine assertion verified with `self.assertIs`. The stdlib-only constraint is properly enforced via a self-source-scan test with dynamic string construction to avoid false positives. No security issues found — test secrets are clearly marked, no shell injection or path traversal, temp files cleaned via `TemporaryDirectory`.

Two minor improvements applied: removed 5 unused imports (I-1) and added `URLError` handling to `_request` for cleaner error reporting (W-1). All tests pass after fixes.
