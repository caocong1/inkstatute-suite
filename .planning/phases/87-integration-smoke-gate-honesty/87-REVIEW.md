---
phase: 87-integration-smoke-gate-honesty
reviewed: 2026-07-15
status: findings_found
depth: standard
files_reviewed: 1
findings:
  critical: 1
  warning: 1
  info: 3
---

# Phase 87: Code Review

## Scope
- services/admin-web-ui/tests/test_smoke_e2e.py

## Findings

### Critical

#### C-1: `test_console_smoke_e2e` fails — `/reports` and `/gates` surfaces hang, causing TimeoutError
- **File:** `services/admin-web-ui/tests/test_smoke_e2e.py`
- **Lines:** 277-284 (surface loop), 35-48 (`_SURFACES` list), 102 (5-second timeout in `_request`)
- **Description:** The primary test method `test_console_smoke_e2e` iterates over all 12 surfaces in `_SURFACES` and asserts each returns HTTP 200. However, `/reports` and `/gates` both call `run_gate_summary()` (in `admin_console_api/gates.py` and `admin_console_api/reports.py`), which spawns a subprocess running `scripts/run_v2_gates.py --json-summary` with a 300-second timeout. In the test environment — where `PYTHONPATH` is set to include all cross-package source directories (required for `create_server` imports) — this subprocess **hangs indefinitely** (confirmed: does not return even after 30 seconds; completes in 1.3s when `PYTHONPATH` is unset). The test's `_request` helper uses a 5-second HTTP timeout (`timeout=5`), so both `/reports` and `/gates` raise `TimeoutError`. This exception is not caught by the `_request` helper (it only catches `urllib.error.HTTPError`), so it propagates as an unhandled exception and the test **fails**.

  Verified by running the full test suite:
  ```
  test_console_smoke_e2e FAILED (TimeoutError: timed out)
  test_smoke_evidence_stamps_not_live_acceptance PASSED
  test_smoke_uses_only_stdlib_http_client PASSED
  test_smoke_login_csrf_required PASSED
  test_smoke_process_start_and_log_viewing PASSED
  test_smoke_process_post_without_csrf_rejected PASSED
  ```

  The 87-01-SUMMARY.md claims "test_console_smoke_e2e passes" — this claim is **false**. The verification report (commit `a238122`) also claims "verification passed (8/8)" which is inaccurate for this test.

- **Recommendation:** Either (a) remove `/reports` and `/gates` from the `_SURFACES` list in the smoke test (these endpoints spawn subprocess-isolated gate runs that are inherently slow and not suitable for a 5-second HTTP smoke), or (b) mock `run_gate_summary` / `reports_aggregator` so the subprocess is not spawned during the smoke test, or (c) increase the timeout for these specific surfaces to accommodate the subprocess. Option (a) or (b) is preferred — a smoke test should not spawn nested test suites.

### Warning

#### W-1: `_request` helper does not catch `URLError` / `TimeoutError` / `ConnectionError`
- **File:** `services/admin-web-ui/tests/test_smoke_e2e.py`
- **Lines:** 101-114
- **Description:** The `_request` method only catches `urllib.error.HTTPError`. Network-level errors (`urllib.error.URLError`, `TimeoutError`, `ConnectionRefusedError`) propagate as unhandled exceptions, producing an uninformative traceback instead of a clean assertion failure. This is directly related to C-1: the `TimeoutError` from `/reports` and `/gates` crashes the test instead of being captured as a non-200 status that the surface loop could report clearly. The existing `test_main.py` pattern (L57-61) has the same gap, but `test_main.py` does not hit endpoints that spawn subprocesses.
- **Recommendation:** Add a `except urllib.error.URLError as exc:` (or `except OSError`) branch that returns a sentinel status (e.g., 0 or -1) and the error message, so the surface loop's `assertEqual(status, 200)` produces a readable failure identifying which surface failed and why.

### Info

#### I-1: Unused imports — 5 symbols imported but never referenced
- **File:** `services/admin-web-ui/tests/test_smoke_e2e.py`
- **Lines:** 22-25
- **Description:** The following imports are never used in the test body:
  - `issue_csrf_token` (line 22) — the test extracts CSRF tokens from HTML forms instead of issuing them directly
  - `LogReader` (line 23) — `create_server` constructs its own `LogReader` internally
  - `build_read_model` (line 24) — `create_server` constructs its own read model internally
  - `Identity` (line 25) — not referenced
  - `Role` (line 25) — not referenced

  These were included per the plan's step 1 instructions but are not needed. They do not cause test failures but add noise and may confuse future maintainers into thinking the test uses them.
- **Recommendation:** Remove the five unused imports.

#### I-2: `_write_log_lines` overwrites the contract log fixture
- **File:** `services/admin-web-ui/tests/test_smoke_e2e.py`
- **Lines:** 200-207 (writes to `tmpdir / "events.jsonl"`), 305 (called after audit checks in `test_console_smoke_e2e`)
- **Description:** Both `_write_contract_log` and `_write_log_lines` write to the same path: `tmpdir / "events.jsonl"` (the `INKSTATUTE_CONTRACT_LOG_PATH`). In `test_console_smoke_e2e`, the contract log is written first (line 270), audit checks pass (lines 286-297), then `_write_log_lines` overwrites the file with plain log lines (line 305). This works because the audit checks complete before the overwrite, but it is conceptually confusing — the same file serves as both the contract event log and the log viewer source, and the overwrite destroys the contract fixture. A separate file path for log lines would be clearer.
- **Recommendation:** Use a distinct file path for `_write_log_lines` (e.g., a separate log file), or document why the overwrite is intentional.

#### I-3: `httpd.server_close()` not called in cleanup
- **File:** `services/admin-web-ui/tests/test_smoke_e2e.py`
- **Lines:** 82 (`self.addCleanup(httpd.shutdown)`)
- **Description:** `_start` registers `httpd.shutdown` as cleanup (which stops the `serve_forever` loop) but does not call `httpd.server_close()` (which closes the listening socket). This leaves the socket open until the process exits. This is consistent with the existing pattern in `test_main.py` (L45) and the OS reclaims the socket on process exit, so the practical impact is minimal. Noting for completeness.
- **Recommendation:** Consider adding `self.addCleanup(httpd.server_close)` after `httpd.shutdown` for thoroughness, though this matches the existing test pattern.

## Summary

The test file `test_smoke_e2e.py` contains 6 test methods covering the full console smoke workflow. Five of the six tests pass. However, the primary and most important test — `test_console_smoke_e2e` — **fails** due to a critical design flaw: it includes `/reports` and `/gates` in its surface coverage list, but both endpoints spawn subprocess-isolated gate runs (`run_gate_summary()`) that hang in the test's `PYTHONPATH`-augmented environment. The 5-second HTTP timeout in `_request` is far too short for these subprocess-spawning endpoints, and the helper's exception handling only covers `HTTPError`, not `URLError`/`TimeoutError`, so the failure manifests as an unhandled exception rather than a clean assertion failure.

The remaining five tests are well-structured: `test_smoke_evidence_stamps_not_live_acceptance` correctly asserts the HUMAN GATE stamp with `self.assertIs(evidence["not_live_acceptance"], True)` (genuine assertion, not a no-op); `test_smoke_uses_only_stdlib_http_client` uses dynamic string construction to avoid self-referential false positives; `test_smoke_login_csrf_required` and `test_smoke_process_post_without_csrf_rejected` verify CSRF enforcement; `test_smoke_process_start_and_log_viewing` verifies process start and log scrubbing. The stdlib-only constraint is honored (urllib only, no requests/httpx/aiohttp). No security issues were found — test secrets are clearly marked, no shell injection or path traversal, temp files are cleaned via `TemporaryDirectory` context managers.

The 87-01-SUMMARY.md claim that "test_console_smoke_e2e passes" is inaccurate. The phase verification should be re-run after fixing C-1.
