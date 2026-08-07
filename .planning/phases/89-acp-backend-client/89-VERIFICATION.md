---
phase: 89
status: passed
verified_at: 2026-08-07T15:30:00Z
verifier: gsd-verifier
---

# Phase 89 Verification

## Goal Achievement

**Phase Goal:** 平台能以 Python ACP client 驱动任意 ACP agent 作为后端，`hermes acp` 生产可用，并有第二个 ACP 后端跑通同一契约以证明可替换性；子进程生命周期受控

**Score:** 6/6 must-haves verified

## Must-Have Verification

| # | Must-Have | Status | Evidence |
|---|-----------|--------|----------|
| 1 | `packages/acp-client` implements `BackendAdapter` 9-method Protocol, locks ACP v1, negotiates at `initialize`; agents lacking required capabilities are explicitly rejected | ✅ PASS | `adapter.py` has `ACPBackendAdapter` with all 9 methods; `capability_negotiation.py` has `negotiate()` that raises `CapabilityMismatchError` on missing caps; `test_adapter.py` test_bootstrap_check_capability_mismatch passes; 70 tests total |
| 2 | `backend_id="hermes"` works via `hermes acp`: create session, send prompt, receive streaming `session/update`, cancel, close; includes Hermes version compatibility matrix and `bootstrap_check` | ✅ PASS | `create_hermes_adapter()` sets HERMES_HOME env; `HERMES_COMPATIBILITY_MATRIX` covers v0.17.0–0.19.0+; `check_hermes_compatibility()` does semver comparison; `test_adapter.py` has test_create_hermes_adapter + test_hermes_compatibility_matrix |
| 3 | Second ACP backend passes the same test path, proving `backend_id` swap needs no caller code changes | ✅ PASS | `test_second_backend.py` has 8 tests; `run_full_cycle()` function is identical for both echo and codex-acp backends; `test_same_caller_code_different_backends` passes; configurable echo agent simulates codex-acp with thought chunks, elicitation, permissions |
| 4 | Subprocess lifecycle controlled: session-end cleanup, timeout recovery, crash restart, no orphan processes; tests assert no orphans | ✅ PASS | `lifecycle.py` has `SubprocessLifecycleManager` with session-end, timeout, crash recovery, orphan detection; `test_lifecycle.py` has 13 tests including `assert_no_orphans` verification; `atexit` handler + context manager |
| 5 | Contract exposes `backend_process_mode` (`per_session` / `pooled` / `remote`); only `per_session` implemented, others exist but raise `NotImplementedError` | ✅ PASS | `BackendProcessMode` enum in `platform_contract/agent_adapter.py`; `process_mode.py` has `validate_process_mode()`; `test_adapter.py` test_process_mode_pooled_rejected asserts `NotImplementedError` |
| 6 | No network/no external agent CI: all tests use fixture ACP agents (in-repo echo agent) | ✅ PASS | `echo_agent.py` (168 lines, stdlib only) and `configurable_echo_agent.py` (278 lines, stdlib only); all 70 tests pass with `python -m unittest discover -s packages/acp-client/tests` using PYTHONPATH only |

## Requirement Traceability

| REQ-ID | Description | Status | Plan | Evidence |
|--------|-------------|--------|------|----------|
| ACP-01 | Python ACP client (stdio, lock protocol v1, initialize version+capability negotiation), implement BackendAdapter 9-method Protocol | ✅ Complete | 89-01 | `client.py` (ACPClient, StdioACPTransport), `capability_negotiation.py`, `event_mapping.py`, 32 tests |
| ACP-02 | `hermes acp` backend usable with capability detection and Hermes version compatibility matrix | ✅ Complete | 89-02 | `adapter.py` has `create_hermes_adapter()`, `HERMES_COMPATIBILITY_MATRIX`, `check_hermes_compatibility()`; 17 tests |
| ACP-03 | At least one additional ACP backend passes the same contract, proving backend replaceability | ✅ Complete | 89-04 | `configurable_echo_agent.py` simulates codex-acp; `test_second_backend.py` has 8 replaceability tests; `run_full_cycle()` is the proof |
| ACP-06 | ACP session and subprocess lifecycle management (new/resume/cancel/close, timeout recovery, crash restart), contract reserves `backend_process_mode` | ✅ Complete | 89-03 | `lifecycle.py` has `SubprocessLifecycleManager`, `SubprocessInfo`, `assert_no_orphans`; 13 tests |

## Binding Constraints

| Constraint | Status | Evidence |
|------------|--------|----------|
| Lock ACP v1, negotiate at initialize | ✅ | `negotiate()` checks `protocolVersion == 1`; raises on mismatch |
| No silent degradation | ✅ | `CapabilityMismatchError` raised when required caps missing; `test_bootstrap_check_capability_mismatch` passes |
| Permission requests never auto-approved | ✅ | `_DANGEROUS_PERMISSION_KINDS` frozenset; `submit_approval` rejects terminal/execute_code with `WAITING_FOR_USER`; `test_submit_approval_no_auto_approve_terminal` + `test_permission_request_not_auto_approved` pass |
| Tool rounds must stream | ✅ | `stream_events()` yields events as they arrive; background task collects via `stream_updates()` |
| Contract logs prefer raw_payload_ref | ✅ | Event mapping uses `raw_input_ref`/`raw_output_ref` for tool_call_update |
| All 29 gates green | ✅ | `python scripts/run_v2_gates.py` exits 0; `--json-summary` confirms 29 gates all exit_code 0 |
| Use echo agent fixture for CI tests | ✅ | Both `echo_agent.py` and `configurable_echo_agent.py` are stdlib-only in-repo fixtures |

## Issues Found

**PyPI module name mismatch (89-01 deviation):** PyPI `agent-client-protocol` installs as module `acp`, not `agent_client_protocol`. Resolved by using the `acp` module name in imports.

**Gate registration moved to 89-01 (deviation):** The `acp-client` gate was registered in Plan 89-01 instead of Plan 89-04 to satisfy the `gate-coverage-meta-test` immediately. Plan 89-04 verified the gate is correct and green.

**Contract freeze baseline update (89-02 deviation):** Adding `BackendProcessMode` to `agent_adapter.py` intentionally modified contract surface files (additive). SHA-256 baseline hashes updated.

**Orphan detection test uses subprocess.Popen (89-03 deviation):** `test_orphan_detection_raises` uses `subprocess.Popen` to spawn a SIGTERM-ignoring process, because `assert_no_orphans` successfully kills echo agent processes (they respond to SIGTERM). The API and behavior match the plan specification.

## Human Verification Needed

None — all verification criteria are testable via automated tests and code inspection. No human judgment gates apply to Phase 89 (HG-1/HG-2/HG-3/HG-4 are for later phases).
