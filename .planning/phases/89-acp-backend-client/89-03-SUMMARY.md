---
phase: 89-acp-backend-client
plan: 03
subsystem: backend
title: Subprocess Lifecycle Management — Per-Session Cleanup, Timeout Recovery, Crash Restart, Orphan Detection
tags: [subprocess, lifecycle, per-session, orphan-detection, timeout, crash-restart]
requires:
  - phase: 89-01
    provides: ACP client
provides:
  - SubprocessLifecycleManager — per-session subprocess lifecycle (register, touch, cleanup, cleanup_all, check_timeouts, detect_crash, restart_if_needed)
  - SubprocessInfo — dataclass tracking pid, session_id, started_at, last_activity, process
  - assert_no_orphans — test helper that verifies no orphan PIDs survive cleanup + grace period
  - atexit handler — best-effort SIGKILL of surviving processes at interpreter exit
  - async context manager — cleanup_all on __aexit__
  - 13 lifecycle tests covering session-end, timeout, crash, restart, orphan detection, context manager, atexit
affects: [89-04]
key-files:
  - packages/acp-client/src/inkstatute_acp_client/lifecycle.py
  - packages/acp-client/tests/test_lifecycle.py
  - packages/acp-client/src/inkstatute_acp_client/__init__.py
key-decisions:
  - "Session-end recovery: SIGTERM → wait 5s → SIGKILL → wait 2s → remove from registry"
  - "Timeout recovery: check_timeouts compares time.monotonic() - last_activity > timeout_seconds"
  - "Crash restart: detect_crash checks process.returncode is not None; restart_if_needed respawns within max_restarts limit"
  - "Orphan detection: assert_no_orphans records PIDs before cleanup, calls cleanup_all, waits grace period, checks os.kill(pid, 0)"
  - "atexit handler is idempotent and registered at construction time — best-effort SIGKILL via os.kill"
  - "test_orphan_detection_raises uses subprocess.Popen (not asyncio) to spawn a SIGTERM-ignoring process, registered with process=None so cleanup can only os.kill SIGTERM — process survives and is detected as orphan"
  - "No changes to ACPClient or StdioACPTransport — lifecycle.py is purely additive"
patterns-established:
  - "SubprocessLifecycleManager as additive wrapper — no modifications to existing client/transport"
  - "Graceful degradation: SIGTERM first, SIGKILL as fallback, ProcessLookupError caught silently"
  - "Restart counting: _restart_counts dict tracks per-lifecycle_id restart attempts"
  - "Context manager pattern for guaranteed cleanup on scope exit"
  - "Orphan detection test pattern: SIGTERM-ignoring process via Popen + process=None registration"
requirements-completed: [ACP-06]
coverage:
  tests: 13
  test_files: 1
  total_acp_client_tests: 62
  gates: 29
  gate_status: all-green
duration: ~25min
completed: "2026-08-07"
status: complete
---

# Plan 89-03 Summary: Subprocess Lifecycle Management

## What Was Built

Created `packages/acp-client/src/inkstatute_acp_client/lifecycle.py` — the `SubprocessLifecycleManager` class that controls per-session subprocess lifecycle for ACP per-session mode. This is the safety net that makes `per_session` mode production-usable at single-firm scale (≤50 lawyers).

### Package Changes

```
packages/acp-client/src/inkstatute_acp_client/
├── lifecycle.py          # NEW — SubprocessLifecycleManager, SubprocessInfo, assert_no_orphans
└── __init__.py           # UPDATED — 22 public API exports (was 19)

packages/acp-client/tests/
└── test_lifecycle.py     # NEW — 13 tests covering all lifecycle controls
```

### Key Components

1. **SubprocessLifecycleManager** — Manages per-session subprocess lifecycle:
   - `register(lifecycle_id, pid, process, session_id)` — tracks a subprocess
   - `touch(lifecycle_id)` — updates last_activity timestamp
   - `cleanup(lifecycle_id)` — session-end recovery: SIGTERM → wait 5s → SIGKILL → wait 2s → remove
   - `cleanup_all()` — cleanup every registered subprocess
   - `check_timeouts()` — find inactive subprocesses and clean them up
   - `detect_crash(lifecycle_id)` — check if process exited unexpectedly
   - `restart_if_needed(lifecycle_id, restart_command, env)` — respawn within max_restarts limit
   - `get_active_pids()` — list all registered PIDs
   - `__aenter__` / `__aexit__` — async context manager (cleanup_all on exit)
   - `_atexit_cleanup()` — best-effort SIGKILL at interpreter exit

2. **SubprocessInfo** — Dataclass with `pid`, `session_id`, `started_at`, `last_activity`, `process` fields.

3. **assert_no_orphans(manager, grace_seconds)** — Test helper that:
   - Records PIDs before cleanup
   - Calls `cleanup_all()`
   - Waits `grace_seconds`
   - Checks `os.kill(pid, 0)` for each PID — raises `RuntimeError` if any still alive

### Test Coverage (13 tests)

| Test | What it verifies |
|------|-----------------|
| `test_register_and_cleanup` | Spawn → register → cleanup → PID removed and dead |
| `test_cleanup_all_removes_everything` | 3 processes spawned, all cleaned up |
| `test_no_orphans_after_cleanup` | `assert_no_orphans` does not raise after proper cleanup |
| `test_orphan_detection_raises` | `assert_no_orphans` raises `RuntimeError` when process survives cleanup |
| `test_timeout_recovery` | `check_timeouts` cleans up inactive process after timeout |
| `test_crash_detection` | Externally killed process detected as crashed |
| `test_restart_after_crash` | `restart_if_needed` spawns new alive process after crash |
| `test_max_restarts_exceeded` | `restart_if_needed` returns `None` when max_restarts=0 |
| `test_context_manager_cleans_up` | `async with` cleans up all processes on exit |
| `test_multiple_sessions_no_leak` | 5 processes spawned and all cleaned up — no orphans |
| `test_touch_updates_last_activity` | `touch` updates `last_activity` timestamp |
| `test_atexit_handler_registered` | `_atexit_registered` is `True` after construction |
| `test_touch_raises_keyerror` | `touch` on unregistered ID raises `KeyError` |

## Deviations

1. **test_orphan_detection_raises uses subprocess.Popen:** The plan specified spawning the echo agent and registering it to test orphan detection. However, `assert_no_orphans` calls `cleanup_all` internally, which successfully kills echo agent processes (they respond to SIGTERM). To test that `assert_no_orphans` actually raises when a process survives cleanup, the test uses `subprocess.Popen` to spawn a process that ignores SIGTERM, and registers it with `process=None` (so cleanup can only `os.kill` SIGTERM, which the process ignores). This is a test implementation detail — the `assert_no_orphans` API and behavior match the plan specification exactly.

## Self-Check: PASSED

- [x] All 4 tasks executed and committed
- [x] All acceptance_criteria verified PASS
- [x] lifecycle.py with per-session subprocess management
- [x] Session-end cleanup (terminate → wait → kill)
- [x] Timeout recovery (watchdog via check_timeouts)
- [x] Crash restart detection (detect_crash + restart_if_needed)
- [x] Orphan detection tests (assert no orphan PIDs)
- [x] All tests pass with echo agent
- [x] 29 gates green
- [x] `python -m pytest packages/acp-client/tests/ -x` passes (62 tests)
- [x] `python scripts/run_v2_gates.py` passes (all 29 gates green)
- [x] `python -m compileall packages/acp-client/src` exits 0
- [x] `python -m unittest discover -s packages/acp-client/tests` passes (62 tests)
- [x] atexit handler registered at construction time
- [x] Context manager cleans up on __aexit__
- [x] No test requires network or external agents — all use echo agent fixture
- [x] No changes to ACPClient or StdioACPTransport — lifecycle.py is purely additive

## Commit Hashes

| Task | Commit | Description |
|------|--------|-------------|
| 89-03-01 | (verification-only) | Reversibility checkpoint — echo agent spawn/kill/detect verified |
| 89-03-02 | fa485c5 | Create SubprocessLifecycleManager — session-end, timeout, crash recovery, orphan detection |
| 89-03-03 | 260833e | 13 lifecycle tests — session-end, timeout, crash, restart, orphan detection, context manager, atexit |
| 89-03-04 | 08d6e78 | Export SubprocessLifecycleManager, SubprocessInfo, assert_no_orphans from package __init__ |
