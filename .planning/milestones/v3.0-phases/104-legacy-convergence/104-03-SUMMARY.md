---
phase: 104
plan: 03
title: Freeze Multi-Agent Adapter + Gate System Update
status: complete
created: 2026-08-08
---

# Plan 104-03 Summary: Freeze Multi-Agent Adapter + Gate System Update

## What Was Done

### 1. Frozen multi-agent-adapter

Created `packages/multi-agent-adapter/FROZEN.md` designating the package as
experimental and frozen. The package code and tests are preserved for reference;
no production consumers exist; no new features should be added. The package
remains in the gate system to ensure it compiles.

Updated `packages/multi-agent-adapter/src/inkstatute_multi_agent_adapter/__init__.py`
module docstring with a `.. deprecated:: Phase 104` note referencing the
FROZEN.md file.

### 2. Verified gate system

Confirmed `scripts/run_v2_gates.py` state:
- **All 4 retired gates removed**: `codex-backend` (104-01), `hermes-contract-layer`,
  `lawyer-web-chat`, `web-sse-channel` (104-02) — none appear in the gate list.
- **compileall paths clean**: No retired package paths
  (`packages/backends/hermes/src`, `packages/backends/codex/src`,
  `services/hermes-contract-layer/src`, `services/lawyer-web-chat/src`,
  `services/web-sse-channel/src`) appear in the compileall command.
- **All new packages have gates**: `acp-client`, `skill-index`, `agent-core`,
  `ui-core`, `gateway` all have gates.
- **multi-agent-adapter gate retained**: The gate still exists (frozen, not removed).
- **Gate-coverage meta-test passes**: All `packages/*/src` and `services/*/src`
  directories on disk are covered by at least one gate.

### 3. Created test file

Created `packages/agent-core/tests/test_phase104_gate_system.py` with 7 tests:
- `test_multi_agent_adapter_frozen_md_exists` — verifies FROZEN.md exists with
  experimental/frozen designation
- `test_multi_agent_adapter_still_compiles` — verifies all .py files in the
  package compile via `py_compile.compile(..., doraise=True)`
- `test_no_removed_gates_in_run_v2_gates` — verifies none of the 4 retired gate
  names appear in the gate list
- `test_compileall_does_not_include_retired_paths` — verifies no retired
  package/service src paths appear in the compileall command
- `test_new_packages_have_gates` — verifies acp-client, skill-index, agent-core,
  ui-core, gateway all have gates
- `test_multi_agent_adapter_gate_exists` — verifies the multi-agent-adapter gate
  still exists
- `test_all_remaining_packages_have_gates` — verifies gate-coverage meta-test
  logic: all packages/*/src and services/*/src directories are covered

## Verification Results

| Check | Result |
|---|---|
| New test file (7 tests) | 7 passed, 19 subtests passed |
| Full agent-core suite | 902 passed, 5 skipped |
| Full V2 gate suite (34 gates) | Exit code 0 — all green |
| Gate count | 34 gates (baseline maintained) |
| agent-core gate test count | 907 (was 900, +7 new tests) |

## Files Created

- `packages/multi-agent-adapter/FROZEN.md`
- `packages/agent-core/tests/test_phase104_gate_system.py`
- `.planning/phases/104-legacy-convergence/104-03-SUMMARY.md`

## Files Modified

- `packages/multi-agent-adapter/src/inkstatute_multi_agent_adapter/__init__.py`
  (added deprecation note to module docstring)

## must_haves Verification

- ✅ `packages/multi-agent-adapter/FROZEN.md` exists with experimental designation
- ✅ multi-agent-adapter package still compiles (not deleted)
- ✅ All 4 retired gates are removed from run_v2_gates.py
- ✅ compileall gate does not include retired package paths
- ✅ gate-coverage meta-test passes — all on-disk packages have gates
- ✅ Full gate suite passes with exit code 0
