---
phase: 89-acp-backend-client
plan: 02
subsystem: backend
title: BackendAdapter 9-Method Implementation, Process Mode Enum, and Hermes Integration
tags: [backend-adapter, 9-method-protocol, process-mode, hermes, bootstrap-check]
requires:
  - phase: 89-01
    provides: ACP client + capability negotiation + event mapping
provides:
  - ACPBackendAdapter — 9-method BackendAdapter Protocol implementation using ACP client
  - ACPBackendConfig — frozen dataclass configuring ACP backend (command, env, process_mode, capabilities)
  - BackendProcessMode enum — per_session/pooled/remote in platform contract (only per_session implemented)
  - process_mode.py — ProcessModeConfig, validate_process_mode, is_mode_implemented, IMPLEMENTED_MODES, UNIMPLEMENTED_MODES
  - HERMES_COMPATIBILITY_MATRIX — v0.17.0–0.19.0+ capability lists
  - check_hermes_compatibility — semver comparison with below_minimum/untested detection
  - create_hermes_adapter — production entry point for hermes acp with HERMES_HOME injection
  - 17 integration tests covering all 9 Protocol methods with echo agent fixture
affects: [89-04]
key-files:
  - packages/acp-client/src/inkstatute_acp_client/adapter.py
  - packages/acp-client/src/inkstatute_acp_client/process_mode.py
  - packages/acp-client/src/inkstatute_acp_client/__init__.py
  - packages/platform-contract/src/platform_contract/agent_adapter.py
  - packages/platform-contract/src/platform_contract/__init__.py
  - packages/acp-client/tests/test_adapter.py
  - packages/contract-test-suite/fixtures/contract_freeze_baseline.json
key-decisions:
  - "BackendProcessMode is additive to agent_adapter.py — no existing field modified, contract freeze baseline updated"
  - "per_session mode: each submit_run spawns a new ACP subprocess (initialize → new_session → prompt → stream)"
  - "pooled/remote modes exist as enum values but raise NotImplementedError — reserved for V4 (SCALE-01..03)"
  - "Permission safety: terminal/execute_code approvals with decision='approved' are rejected → WAITING_FOR_USER"
  - "Hermes compatibility matrix covers v0.17.0–0.19.0+; untested versions (above minimum) are compatible with warning"
  - "create_hermes_adapter is the production entry point — sets HERMES_HOME env var for profile loading"
  - "Background asyncio task collects streaming events; stream_events polls buffer until terminal state"
patterns-established:
  - "ACPBackendAdapter follows Hermes adapter pattern: in-memory _runs/_events/_artifacts dicts"
  - "transport_factory parameter for testability (defaults to StdioACPTransport)"
  - "bootstrap_check spawns transport, initializes, checks compatibility, closes transport — no resource leak"
  - "Contract freeze baseline update for intentional additive contract changes"
  - "check_hermes_compatibility: untested != incompatible (version above minimum but not in matrix)"
requirements-completed: [ACP-02]
coverage:
  tests: 17
  test_files: 1
  total_acp_client_tests: 49
  gates: 29
  gate_status: all-green
duration: ~30min
completed: "2026-08-07"
status: complete
---

# Plan 89-02 Summary: BackendAdapter 9-Method Implementation, Process Mode Enum, and Hermes Integration

## What Was Built

Implemented the `ACPBackendAdapter` class that satisfies the `BackendAdapter` 9-method Protocol from `platform_runtime.protocols`, using the ACP client core from Plan 89-01. Added the `BackendProcessMode` enum to the platform contract (additive, only `per_session` implemented). Created the Hermes version compatibility matrix and `create_hermes_adapter` production entry point.

### Package Changes

```
packages/acp-client/src/inkstatute_acp_client/
├── adapter.py          # NEW — ACPBackendAdapter (9 methods), ACPBackendConfig, HERMES_COMPATIBILITY_MATRIX
├── process_mode.py     # NEW — ProcessModeConfig, validate_process_mode, is_mode_implemented
└── __init__.py         # UPDATED — 19 public API exports (was 9)

packages/platform-contract/src/platform_contract/
├── agent_adapter.py    # UPDATED — BackendProcessMode enum (additive)
└── __init__.py         # UPDATED — BackendProcessMode export

packages/acp-client/tests/
└── test_adapter.py     # NEW — 17 integration tests with echo agent fixture

packages/contract-test-suite/fixtures/
└── contract_freeze_baseline.json  # UPDATED — hashes for modified contract files
```

### Key Components

1. **ACPBackendAdapter** — Implements all 9 BackendAdapter Protocol methods:
   - `backend_id()` — returns configured backend identifier
   - `capabilities()` — returns AdapterCapabilitySet from last negotiation (or default with stream_event_support=True)
   - `bootstrap_check()` — spawns transport, calls initialize, checks version compatibility, returns BootstrapStatus
   - `submit_run()` — spawns per-session subprocess, initializes, creates session, prompts, starts background event collection
   - `get_run()` — returns Run state or raises KeyError
   - `stream_events()` — async generator yielding events in seq order until terminal state
   - `cancel_run()` — calls client.cancel, updates run to CANCELLED
   - `submit_approval()` — rejects auto-approval of terminal/execute_code permissions (→ WAITING_FOR_USER)
   - `collect_artifacts()` — returns stored artifacts (possibly empty)

2. **BackendProcessMode enum** — `PER_SESSION`, `POOLED`, `REMOTE` in platform contract. Only `PER_SESSION` is implemented; `POOLED` and `REMOTE` raise `NotImplementedError` when used.

3. **process_mode.py** — `ProcessModeConfig` (frozen dataclass), `validate_process_mode()` (raises NotImplementedError for unimplemented modes), `is_mode_implemented()`, `IMPLEMENTED_MODES`, `UNIMPLEMENTED_MODES`.

4. **Hermes compatibility matrix** — `HERMES_COMPATIBILITY_MATRIX` maps v0.17.0–0.19.0 to capability lists. `check_hermes_compatibility()` performs semver comparison: below minimum → incompatible, above minimum but not in matrix → untested (compatible with warning).

5. **create_hermes_adapter()** — Production entry point for `hermes acp`. Creates `ACPBackendConfig` with `backend_id="hermes"`, `HERMES_HOME` env injection, and the compatibility matrix.

## Deviations

1. **Contract freeze baseline update:** The contract freeze test (`test_contract_freeze.py`) detects SHA-256 hash changes to contract surface files. Adding `BackendProcessMode` to `agent_adapter.py` and exporting it from `__init__.py` intentionally modified these files (additive). The baseline hashes in `contract_freeze_baseline.json` were updated to reflect the new content. This follows the same pattern used in Phase 88 when unified events were added to the contract.

## Self-Check: PASSED

- [x] All 7 tasks executed and committed
- [x] All acceptance_criteria verified PASS
- [x] ACPBackendAdapter implements all 9 BackendAdapter Protocol methods
- [x] BackendProcessMode enum with per_session implemented, pooled/remote marked unimplemented
- [x] Hermes integration with bootstrap_check and version compatibility matrix
- [x] All tests pass with echo agent fixture (17 adapter tests + 32 client tests = 49 total)
- [x] 29 gates green (contract freeze baseline updated for additive change)
- [x] `python -m pytest packages/acp-client/tests/ -x` passes (49 tests)
- [x] `python scripts/run_v2_gates.py` passes (all 29 gates green)
- [x] `python -m compileall packages/acp-client/src` exits 0
- [x] `python -m compileall packages/platform-contract/src` exits 0
- [x] submit_approval never auto-approves terminal/execute_code permissions
- [x] No test requires network or external agents — all use echo agent fixture
- [x] create_hermes_adapter sets HERMES_HOME env var

## Commit Hashes

| Task | Commit | Description |
|------|--------|-------------|
| 89-02-01 | (verification-only) | Reversibility checkpoint — 29 gates green, additive confirmed |
| 89-02-02 | 676ed74 | Add BackendProcessMode enum to platform contract (additive) |
| 89-02-03 | f3f889a | Create process_mode.py — per_session implemented, pooled/remote unimplemented |
| 89-02-04 | 49af009 | Create ACPBackendAdapter — 9-method BackendAdapter Protocol implementation |
| 89-02-05 | d7ffac9 | Add Hermes compatibility matrix, check_hermes_compatibility, create_hermes_adapter |
| 89-02-06 | bc304d3 | Create test_adapter.py — 17 integration tests with echo agent |
| 89-02-07 | c6d6792 | Update __init__.py with adapter and process_mode exports |
| baseline | aaf9940 | Update contract freeze baseline for additive change |
