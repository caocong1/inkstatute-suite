---
phase: 109-arena-service
plan: 04
status: complete
requirements: [SVC-06, SVC-08]
---

# Plan 04: Subprocess Control + Staggered Startup Semaphore — Summary

## Objective

Create `SubprocessController` (liveness check + per-run timeout + partial-result acceptance) and `StaggeredStartupSemaphore` (asyncio semaphore to prevent N agents calling `initialize()` simultaneously). Add `get_active_pids()` method to `ACPBackendAdapter` to expose subprocess PID tracking for orphan detection (used by GATE-06 in Plan 06).

## Tasks Completed

### Task 1: subprocess_control.py — Liveness check + per-run timeout + partial-result acceptance

**Files modified/created:**
- `packages/acp-client/src/inkstatute_acp_client/adapter.py` — Added `get_active_pids() -> set[int]` method to `ACPBackendAdapter` (lines 452-467). Iterates over `_sessions` dict, reads `client._transport.pid` for each `ACPClient`, collects non-`None` PIDs into a set.
- `services/arena-service/src/arena_service/subprocess_control.py` — New module with:
  - `PartialResult` — frozen slotted dataclass (`accepted`, `status`, `content`, `marked`, `metadata`).
  - `SubprocessController` — liveness check via `os.kill(pid, 0)`, per-run timeout via `asyncio.wait_for` with cleanup callback, partial-result acceptance for `timeout`/`failed`/`success` SlotResult statuses.
- `services/arena-service/src/arena_service/__init__.py` — Re-exports `PartialResult`, `SubprocessController`.
- `services/arena-service/tests/test_subprocess_control.py` — 13 tests covering all 11 behaviors (get_active_pids empty/populated, controller defaults, liveness alive/dead/no-sessions, timeout completes/expires+cleanup, partial-result timeout/failed/success, frozen slotted dataclass, no orphans after cleanup).

**Commit:** `feat(109-04): subprocess control — liveness, per-run timeout, partial-result acceptance + adapter get_active_pids`

### Task 2: staggered_startup.py — asyncio Semaphore for concurrent initialize limiting

**Files created:**
- `services/arena-service/src/arena_service/staggered_startup.py` — `StaggeredStartupSemaphore` class with:
  - `__init__(max_concurrent=2)` — creates `asyncio.Semaphore`.
  - `acquire()` — async context manager (`@asynccontextmanager`) that increments/decrements `current_concurrent`.
  - `__aenter__`/`__aexit__` — direct async context manager support.
  - `current_concurrent` property — tracks held permits.
  - `wrap_initialize(submit_run_fn)` — wraps a function to acquire the semaphore before calling; releases in `finally` block (exception-safe).
  - `run_staggered(submit_run_fn, requests)` — runs multiple requests via `asyncio.gather` with semaphore limiting.
- `services/arena-service/src/arena_service/__init__.py` — Re-exports `StaggeredStartupSemaphore`.
- `services/arena-service/tests/test_staggered_startup.py` — 11 tests covering all 9 behaviors (construction defaults, 2 acquires proceed, 3rd blocks, entry/exit order, current_concurrent tracking, wrap_initialize, 4 agents at most 2 concurrent, non-blocking of unrelated ops, exception safety, run_staggered completes all).

**Commit:** `feat(109-04): staggered startup semaphore — limit concurrent initialize to max_concurrent`

## Verification Results

- `test_subprocess_control.py`: 13 tests, all pass (exit 0)
- `test_staggered_startup.py`: 11 tests, all pass (exit 0)
- Full arena-service test suite: 118 tests, all pass (exit 0)
- acp-client test suite (adapter change): 107 tests, all pass (exit 0)

## Key Design Decisions

1. **`get_active_pids()` uses `getattr` for safe access** — The adapter accesses `client._transport` and `transport.pid` via `getattr` with `None` checks, avoiding hard coupling to `ACPClient` internals while still reading the real `StdioACPTransport.pid` property.

2. **`SubprocessController.run_with_timeout` re-raises `TimeoutError`** — After calling the cleanup callback (wired to `ArenaEngine.cancel()` in Plan 05), the `TimeoutError` is re-raised so callers can handle it. Cleanup failures are swallowed to avoid masking the timeout.

3. **`StaggeredStartupSemaphore` supports both `async with sem:` and `async with sem.acquire():`** — The `__aenter__`/`__aexit__` dunder methods and the `@asynccontextmanager acquire()` method both track `current_concurrent` accurately.

4. **`wrap_initialize` is exception-safe** — Uses `async with self:` which guarantees semaphore release even when the wrapped function raises, preventing deadlock from failed initializations.

## Artifacts Produced

- `arena_service.subprocess_control.SubprocessController` — liveness check + per-run timeout + partial-result acceptance
- `arena_service.subprocess_control.PartialResult` — frozen slotted partial result dataclass
- `arena_service.staggered_startup.StaggeredStartupSemaphore` — asyncio semaphore for staggered initialization
- `inkstatute_acp_client.adapter.ACPBackendAdapter.get_active_pids` — PID tracking method on the ACP adapter
- `tests/test_subprocess_control.py::SubprocessControlTests` — 13 tests
- `tests/test_staggered_startup.py::StaggeredStartupTests` — 11 tests

## Key Links (for Plan 05/06)

- `ACPBackendAdapter.get_active_pids()` is used by `SubprocessController.check_liveness()` and by GATE-06 orphan process tests (Plan 06).
- `SubprocessController.set_cleanup_callback()` will be wired to `ArenaEngine.cancel()` in Plan 05.
- `StaggeredStartupSemaphore.wrap_initialize()` will wrap `adapter.submit_run()` calls in Plan 05.
- `SubprocessController.accept_partial_result()` accepts `SlotResult` from `arena_engine.slot_runner` — partial results flow from engine → service.
