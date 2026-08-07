---
phase: 89-acp-backend-client
plan: 04
subsystem: backend
title: Second ACP Backend Replaceability + Gate Registration + Full Gate Suite Green
tags: [replaceability, second-backend, codex-acp, claude-agent-acp, gate-registration, config-driven]
requires:
  - phase: 89-01
    provides: ACP client core (stdio, initialize, event mapping, echo agent fixture)
  - phase: 89-02
    provides: BackendAdapter 9-method, BackendProcessMode, Hermes integration
  - phase: 89-03
    provides: SubprocessLifecycleManager (per-session, timeout, crash, orphan)
provides:
  - Configurable echo agent fixture simulating codex-acp (thought chunks, elicitation, permissions)
  - 8 backend replaceability tests proving zero caller code changes on backend_id swap
  - acp-client gate registered (29 gates total, all green)
affects:
  - 90+ (ACP Event Bridge uses the adapter and event mapping established here)
key-files:
  - packages/acp-client/tests/fixtures/configurable_echo_agent.py
  - packages/acp-client/tests/test_second_backend.py
  - scripts/run_v2_gates.py
key-decisions:
  - "Configurable echo agent simulates codex-acp with thought chunks, elicitation, and permission requests — proves different ACP backends work through the same adapter"
  - "run_full_cycle function is the proof of replaceability — identical caller code, only ACPBackendConfig differs"
  - "acp-client gate was registered in Plan 89-01 (deviation); Plan 89-04 verified it remains green with all new tests"
  - "backend_id is config-driven, not code-driven — swapping backends requires only ACPBackendConfig change"
patterns-established:
  - "Fixture agent pattern: standalone stdlib Python scripts simulating ACP backends with configurable capabilities"
  - "Replaceability test pattern: same run_full_cycle function called with different adapters, assert both produce same core event types"
  - "Permission safety test pattern: assert terminal/execute_code approvals are rejected regardless of backend"
coverage:
  tests: 70
  gates: 29
  requirements: ACP-03
duration: "1 session"
completed: 2026-08-07
status: complete
requirements-completed:
  - ACP-03
---

# Plan 89-04 Summary: Second ACP Backend Replaceability

## What Was Built

### Configurable Echo Agent Fixture (Task 89-04-02)
Created `packages/acp-client/tests/fixtures/configurable_echo_agent.py` — a second ACP backend fixture simulating `codex-acp` with:
- Configurable `--backend-name` and `--capabilities` CLI arguments
- `agent_thought_chunk` notifications (not in base echo agent)
- Chunked `agent_message_chunk` notifications (3 chunks)
- `elicitation/create` requests when prompt contains "ask:"
- `session/request_permission` requests with `kind: "terminal"` when prompt contains "permission:"
- Session IDs prefixed by backend name (`codex-acp-session-<uuid>`)
- Stdlib only (sys, json, uuid, argparse)

### Backend Replaceability Tests (Task 89-04-03)
Created `packages/acp-client/tests/test_second_backend.py` with 8 tests:
1. `test_echo_backend_full_cycle` — full cycle with echo backend
2. `test_codex_acp_backend_full_cycle` — same cycle with codex-acp backend
3. `test_same_caller_code_different_backends` — identical `run_full_cycle` function works with both
4. `test_different_capabilities_negotiated` — echo has no elicitation, codex-acp does
5. `test_thought_chunks_from_second_backend` — codex-acp yields `thought.delta`
6. `test_elicitation_from_second_backend` — codex-acp yields `elicitation.requested`
7. `test_permission_request_not_auto_approved` — terminal permission rejected
8. `test_backend_id_isolated` — backend_id is config-driven

### Gate Registration (Task 89-04-04)
The `acp-client` gate was registered in Plan 89-01 (deviation noted in 89-01-SUMMARY.md). Plan 89-04 verified:
- Gate is present in `scripts/run_v2_gates.py` with correct PYTHONPATH
- `packages/acp-client/src` is in the `compileall` gate path list
- `gate-coverage-meta-test` passes with the new package covered
- All 29 gates (28 existing + 1 new) are green

## Verification Results

- `python -m unittest discover -s packages/acp-client/tests` → **70 tests passed** (62 from Plans 01-03 + 8 from Plan 04)
- `python scripts/run_v2_gates.py` → **29 gates green** (exit code 0)
- `python scripts/run_v2_gates.py --json-summary` → `{"passed": true, ...}` with 29 gate entries
- `python -m compileall packages/acp-client/tests/test_second_backend.py` → exits 0
- No test requires network or external agent binaries — both backends are fixture agents

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 89-04-01 | (verification-only) | Reversibility checkpoint — 29 gates green, gate already registered |
| 89-04-02 | `b18be6a` | Configurable echo agent fixture — second ACP backend with thought chunks, elicitation, permissions |
| 89-04-03 | `ad5173a` | 8 backend replaceability tests — same caller code, different backends |
| 89-04-04 | (already done in 89-01) | Gate registration verified — no duplicate added |
| 89-04-05 | (verification-only) | Full gate suite — all 29 gates green |
| docs | (this commit) | SUMMARY.md, STATE.md, ROADMAP.md, REQUIREMENTS.md updated |

## Deviations

1. **Gate registration already done in Plan 89-01** — The `acp-client` gate was registered in Plan 89-01 (deviation noted in 89-01-SUMMARY.md) to satisfy the `gate-coverage-meta-test` immediately. Plan 89-04 verified the gate is correct and green rather than re-registering it.

2. **Configurable echo agent committed before test file** — The configurable echo agent fixture (Task 89-04-02) was committed in a prior session (`b18be6a`) before the test file (Task 89-04-03) was written. The test file was committed separately (`ad5173a`). Both are now in the repository.

## Self-Check: PASSED

- [x] Second ACP backend (configurable echo agent) passes the same `ACPBackendAdapter` test path as the first backend
- [x] The same `run_full_cycle` function works with both backends — zero caller code changes
- [x] `backend_id` swap requires only config change, not code change
- [x] Different capabilities (elicitation, permissions, thought chunks) handled by the same adapter
- [x] `acp-client` gate is registered with correct PYTHONPATH
- [x] `packages/acp-client/src` is in the `compileall` gate path list
- [x] All 29 gates green
- [x] `gate-coverage-meta-test` passes with the new package covered
- [x] No regressions in any existing gate
- [x] No test requires network or external agent binaries
