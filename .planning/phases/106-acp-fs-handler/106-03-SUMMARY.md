---
phase: 106-acp-fs-handler
plan: 03
status: complete
requirements: [GATE-04]
---

# Plan 03: GATE-04 — fs Sandbox Escape Gate Integration - Summary

## What Was Built
- Added the `fs-sandbox-escape` gate (GATE-04) to `scripts/run_v2_gates.py`, placed immediately after the existing `acp-client` gate in the `_gates()` return tuple
- The gate runs `packages/acp-client/tests/test_fs_sandbox.py` (12 tests covering all 5 sandbox escape vectors plus positive reads and boundary cases) with pythonpath `(acp_client_src, platform_src, platform_runtime_src)`
- Updated the gate-count baseline in `packages/contract-test-suite/tests/test_gate_coverage.py` from `>= 19` to `>= 35`, with an updated docstring referencing the Phase 106 baseline

## Tasks Completed
- [x] Task 1: Add fs-sandbox-escape gate + update gate count baseline

## Verification Results
- `python scripts/run_v2_gates.py --list | grep fs-sandbox-escape` → outputs `fs-sandbox-escape` (gate exists)
- Gate count: `python scripts/run_v2_gates.py --list | wc -l` → 35 (34 existing + 1 new)
- `test_gate_count_meets_baseline` asserts `>= 35` and passes (3/3 tests OK in test_gate_coverage.py)
- `fs-sandbox-escape` gate passes: 12 tests run, all OK
- `gate-coverage-meta-test` passes: all packages/*/src and services/*/src directories covered, no new uncovered directories
- Full gate run: all gates green up to `qqbot-channel`, which has a pre-existing failure (`test_recall01_c2c_over_window_wakeup_omits_msg_id_on_wire`) unrelated to this plan — confirmed by stashing changes and reproducing the same failure

## Artifacts Produced
- `fs-sandbox-escape` Gate entry in `scripts/run_v2_gates.py` `_gates()` return tuple (line 127-131)
- Updated `test_gate_count_meets_baseline` assertion in `packages/contract-test-suite/tests/test_gate_coverage.py` (19 → 35, line 58-60)

## Notes
- The plan's `<action>` specified the gate command as `(py, "-m", "unittest", "packages.acp_client.tests.test_fs_sandbox")` using dotted module notation. This does not work because the directory is `packages/acp-client` (hyphen, not underscore) and there are no `__init__.py` files making `packages` a proper package. The command was adapted to use the file path form `(py, "-m", "unittest", "packages/acp-client/tests/test_fs_sandbox.py")`, matching the pattern used by the existing `gate-coverage-meta-test` gate. This achieves the same result — running `test_fs_sandbox.py` — and passes all 12 tests.
- The `qqbot-channel` gate has a pre-existing failure (`test_recall01_c2c_over_window_wakeup_omits_msg_id_on_wire`) that is unrelated to this plan. It was confirmed pre-existing by stashing the plan's changes and reproducing the identical failure. This failure does not affect the fs-sandbox-escape gate or the gate-count baseline meta-test.
