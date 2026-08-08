---
phase: 109-arena-service
plan: 06
status: complete
requirements: [GATE-05, GATE-06]
---

# Plan 06: Gate Integration — GATE-05 Permission Safety + GATE-06 Orphan Process - Summary

## Objective

Create the two CI gate tests for Phase 109: GATE-05 (permission safety — verify `_DANGEROUS_PERMISSION_KINDS` preserved, no batch approve, dangerous kinds rejected) and GATE-06 (orphan process — zero PID residue after cancel). Register both gates in `scripts/run_v2_gates.py`, add `services/arena-service/src` to the compileall gate, and update the gate count baseline from 36 to 38 in `test_gate_coverage.py`.

## Tasks Completed

### Task 1: GATE-05 — Permission safety gate test + gate registration

**Files created/modified:**
- `services/arena-service/tests/test_permission_safety_gate.py` (new) — 8 tests in `PermissionSafetyGateTests`
- `scripts/run_v2_gates.py` (modified) — added `arena_service_src` path variable, `arena-permission-safety` gate, `services/arena-service/src` to compileall

**Tests implemented (8):**
1. `test_dangerous_kinds_preserved` — `_DANGEROUS_PERMISSION_KINDS` equals `frozenset({"terminal", "execute_code"})`
2. `test_no_batch_approve_endpoint` — no operation in `OPERATIONS` contains "batch" or "bulk"; `check_no_batch_approve(ArenaServiceApp)` returns True
3. `test_no_auto_approve_dangerous` — `check_no_auto_approve_dangerous(app_module)` returns True
4. `test_terminal_rejected` — terminal kind with approved decision is rejected (WAITING_FOR_USER)
5. `test_execute_code_rejected` — execute_code kind with approved decision is rejected (WAITING_FOR_USER)
6. `test_read_file_approved` — read_file kind with approved decision is approved normally
7. `test_operations_no_batch_bulk` — OPERATIONS has no batch/bulk operation names
8. `test_dangerous_kinds_imported_not_redefined` — permission_safety module imports (not redefines) `_DANGEROUS_PERMISSION_KINDS`

**Commit:** `feat(109-06): GATE-05 permission safety gate test + gate registration + compileall coverage`

### Task 2: GATE-06 — Orphan process gate test + gate registration + baseline update

**Files created/modified:**
- `services/arena-service/tests/test_orphan_process.py` (new) — 11 tests in `OrphanProcessGateTests` with `PidsTrackingMockAdapter` helper
- `scripts/run_v2_gates.py` (modified) — added `arena-orphan-process` gate and `arena-service` gate (full test suite)
- `packages/contract-test-suite/tests/test_gate_coverage.py` (modified) — baseline updated from 36 to 38

**Tests implemented (11):**
1. `test_zero_pid_residue_after_cancel` — all adapters' `get_active_pids()` return empty set after cancel
2. `test_pids_tracked_before_cancel` — PIDs are non-empty before cancel
3. `test_all_pids_gone_after_cancel` — all recorded PIDs are gone after cancel
4. `test_multiple_adapters_all_cleaned` — 3 adapters all cleaned up (zero residue)
5. `test_cancel_unknown_arena_no_crash` — cancel of non-existent arena raises catchable KeyError
6. `test_no_pid_accumulation_across_cycles` — create → cancel → create → cancel leaves no PIDs
7. `test_cancel_calls_cancel_run_and_shutdown` — both `cancel_run()` and `shutdown()` called during cancel
8. `test_event_buffer_cleared_after_cancel` — `event_buffer.clear_arena()` results in empty buffer
9. `test_gate_count_at_least_38` — `run_v2_gates.py` defines at least 38 gates
10. `test_gate_coverage_baseline_38` — gate coverage baseline is 38
11. `test_arena_service_src_covered` — `services/arena-service/src` is covered by at least one gate

**Commit:** `feat(109-06): GATE-06 orphan process gate test + arena-service gate + baseline 36 to 38`

## Gate Registration Summary

Three new gates added to `scripts/run_v2_gates.py`:

| Gate | Command | Purpose |
|---|---|---|
| `arena-permission-safety` | `unittest services/arena-service/tests/test_permission_safety_gate.py` | GATE-05: permission safety invariants |
| `arena-orphan-process` | `unittest services/arena-service/tests/test_orphan_process.py` | GATE-06: zero PID residue after cancel |
| `arena-service` | `unittest discover -s services/arena-service/tests` | Full arena-service test suite |

All three gates include `arena_service_src` in PYTHONPATH along with `acp_client_src`, `acp_event_bridge_src`, `platform_src`, `platform_runtime_src`, and `arena_engine_src`.

**Compileall gate:** `services/arena-service/src` added to the compileall command path arguments.

**Gate count:** 36 (Phase 107 baseline) → 39 (36 + 3 new arena gates). Baseline in `test_gate_coverage.py` updated to 38 (minimum threshold).

## Verification Results

- `test_permission_safety_gate.py`: 8 tests, all pass (exit 0)
- `test_orphan_process.py`: 11 tests, all pass (exit 0)
- `test_gate_coverage.py`: 3 tests, all pass (exit 0)
- Full arena-service test suite: 137 tests, all pass (exit 0)
- `compileall services/arena-service/src`: success (exit 0)
- Gate count: 39 gates (>= 38 baseline)

## Key Design Decisions

- **PidsTrackingMockAdapter**: A test-specific mock adapter that wraps the BackendAdapter Protocol with PID simulation. Each `submit_run` assigns a mock PID; `cancel_run` and `shutdown` clear PIDs. This mirrors the real `ACPBackendAdapter.get_active_pids()` pattern without requiring real subprocesses.
- **Cancel unknown arena**: `ArenaEngine.cancel()` raises `KeyError` for unknown arena IDs — the test verifies this is a catchable exception, not an unhandled crash.
- **Event buffer clearing**: The test verifies `ArenaEventBuffer.clear_arena()` produces an empty buffer, simulating the cancel handler's cleanup step.
- **Gate count baseline**: Set to 38 (not 39) as specified in the plan — the baseline is a minimum threshold, and 39 >= 38 satisfies the assertion.
