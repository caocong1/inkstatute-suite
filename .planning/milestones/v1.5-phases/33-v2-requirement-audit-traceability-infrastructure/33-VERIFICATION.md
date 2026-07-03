# Phase 33: V2 Requirement Audit & Traceability Infrastructure - Verification

**Phase:** 33
**Milestone:** v1.5 V2 Acceptance Closure
**Requirements:** AUDIT-01, AUDIT-02, AUDIT-03, AUDIT-04, AUDIT-05, AUDIT-06, AUDIT-07
**Date:** 2026-07-03

## Goal

Operator can run a deterministic audit that maps every unchecked V2 Active requirement to concrete code evidence and classifies each as satisfied, partial, gap, or human_gate using three-level verification (schema -> library surface -> production wiring).

## Must-Haves

- [x] `scripts/audit_v2_requirements.py` exists and runs with `--json`, `--check-gaps`, `--requirement` modes
- [x] Audit produces a complete traceability matrix for all 10 unchecked V2 Active requirements
- [x] Each requirement has a per-requirement evidence bundle (files, tests, gates, schemas, fixtures)
- [x] Three-level verification classifies each requirement as satisfied/partial/gap/human_gate
- [x] `acceptance/v2-traceability.json` exists with correct schema and PRD Section 10 mapping
- [x] `scripts/run_v2_gates.py` includes 9th gate `v2-acceptance-traceability`
- [x] 9th gate fails when any requirement is classified as `gap` (does not fail on `partial` or `human_gate`, by design)
- [x] Audit is deterministic — two runs produce byte-identical JSON
- [x] All audit script tests pass (24 test cases)
- [x] All 9 V2 gates pass green (8 existing + 1 new)
- [x] No new runtime dependencies introduced (stdlib-only)

## Evidence

### Deliverables

| File | Description |
|------|-------------|
| `scripts/audit_v2_requirements.py` | Stdlib-only audit script (~1250 lines) with RequirementSpec, VerificationProbe, 10-requirement registry, three-level verification, evidence collector, classification engine, PRD Section 10 mapping, JSON sidecar writer |
| `scripts/run_v2_gates.py` | Modified: added 9th gate `v2-acceptance-traceability` + audit script in compileall |
| `acceptance/v2-traceability.json` | Generated traceability sidecar (deterministic, 10 requirements, 15 PRD Section 10 criteria) |
| `packages/contract-test-suite/tests/test_audit_v2_requirements.py` | 24 test cases covering all audit script functionality |

### Requirement Registry (10 requirements)

| # | Req ID | Description | Status | L1 Schema | L2 Library | L3 Wiring |
|---|--------|-------------|--------|-----------|------------|-----------|
| 1 | WECOM-01 | WeCom service | satisfied | channel_message, channel_delivery | ingress_runtime.py: WeComRuntimeIngress | imports normalization, session_runtime, active_task_router |
| 2 | ADAPTER-01 | Agent adapter contract | satisfied | agent_adapter_manifest | agent_backend.py: select_agent_backend | imports platform_contract.agent_adapter |
| 3 | HERMES-01 | Hermes bootstrap | satisfied | agent_adapter_manifest | bootstrap.py: probe_hermes_capabilities | __init__.py exports bootstrap functions |
| 4 | OUTPUT-01 | Output boundary | satisfied | (none) | output_policy.py: apply_output_policy | sender.py imports and calls apply_output_policy |
| 5 | LOOP-01 | WeCom loop validation | satisfied | feedback_event, agent_turn, agent_result | active_task_router.py: route_active_task_turn | session_runtime.py imports route_active_task_turn |
| 6 | FEEDBACK-01 | Feedback normalization | satisfied | feedback_event | wecom_normalizer.py: normalize_wecom_feedback_records | queue.py imports from wecom_normalizer |
| 7 | READVIEW-01 | Read-only APIs | satisfied | (none) | api.py: handle_get | api.py reads from contract logs via read_model |
| 8 | OBSERVE-01 | Observability/replay/privacy | satisfied | memory_use, execution_trace | privacy_scan.py: scan_privacy_targets | hook.py imports ContractEventWriter |
| 9 | COMPOSE-01 | Composability CI | satisfied | (none) | boundary_checks.py: BoundaryAllowlistPolicy | run_v2_gates.py includes contract-test-suite gate |
| 10 | TRIAL-01 | Lawyer trial | human_gate | (none) | trial_acceptance.py: evaluate_trial_acceptance | (human gate — no wiring required) |

### Summary

- **9 satisfied** — all non-human-gate requirements have schema, library surface, and production wiring verified
- **0 partial** — no requirements have missing wiring
- **0 gap** — no requirements have missing schema or library surface
- **1 human_gate** — TRIAL-01 (lawyer trial) is correctly classified as human_gate, not gap

### PRD Section 10 Mapping

The sidecar contains 15 criterion-to-test mappings covering all 4 sections:
- **10.1** (4 criteria): Repository and documentation acceptance (manual checks)
- **10.2** (7 criteria): Contract CI acceptance (schema validation, fixture replay, relationship integrity, coverage, output boundary)
- **10.3** (1 criterion): Composability synthesis task acceptance
- **10.4** (3 criteria): Lawyer trial acceptance (human gate + live WeCom service)

## Automated Checks

### 1. Audit script runs without error
```
$ python scripts/audit_v2_requirements.py
V2 Requirement Audit — Traceability Matrix
...
Summary: 9 satisfied, 0 partial, 0 gap, 1 human_gate
EXIT: 0
```

### 2. JSON sidecar generation
```
$ python scripts/audit_v2_requirements.py --json
Wrote acceptance/v2-traceability.json
Summary: 9 satisfied, 0 partial, 0 gap, 1 human_gate
EXIT: 0
```

### 3. Gap-check mode
```
$ python scripts/audit_v2_requirements.py --check-gaps
PASS: no requirements classified as gap
EXIT: 0
```

### 4. Single-requirement mode
```
$ python scripts/audit_v2_requirements.py --requirement WECOM-01
Requirement: WECOM-01
Description: Build InkStatute-owned WeCom service...
Status: satisfied
Evidence:
  Implementation files (15): ...
  Test modules (10): ...
  Gate suites: wecom-service
  Schema IDs: channel_delivery.schema.json, channel_message.schema.json
  Fixtures (5): ...
Verification:
  Level 1 (Schema): PASS
  Level 2 (Library): PASS
  Level 3 (Wiring): PASS
EXIT: 0
```

### 5. Determinism verification
```
$ diff <(python scripts/audit_v2_requirements.py --json) <(python scripts/audit_v2_requirements.py --json)
(no diff — byte-identical output)
```
Verified via MD5: `1d876cca1917b45d20e81bb838fa911c` (identical across runs)

### 6. Audit script tests
```
$ python -m unittest packages/contract-test-suite/tests/test_audit_v2_requirements.py -v
Ran 24 tests in 0.725s
OK
```

### 7. Full V2 gate suite (9 gates)
```
$ python scripts/run_v2_gates.py
==> platform-contract          (21 tests)   OK
==> wecom-service              (71 tests)   OK
==> hermes-contract-layer      (30 tests)   OK
==> conversation-read-view     (18 tests)   OK
==> feedback-service           (31 tests)   OK
==> phase7-privacy-boundary    (13 tests)   OK
==> contract-test-suite        (264 tests)  OK
==> v2-acceptance-traceability             OK  (PASS: no gaps)
==> compileall                             OK
EXIT: 0
```

### 8. Gate list verification
```
$ python scripts/run_v2_gates.py --list
platform-contract
wecom-service
hermes-contract-layer
conversation-read-view
feedback-service
phase7-privacy-boundary
contract-test-suite
v2-acceptance-traceability
compileall
(9 gates total)
```

## Notes

- The audit script reads codebase structure but does NOT re-run tests or gates. Gate-passing is proven by `run_v2_gates.py`; the audit proves traceability and wiring.
- Three-level verification catches the MEM-07/MEM-16 false-positive pattern: Level 3 (production wiring) verifies that library code is actually imported and called in production entrypoints, not just present on disk.
- The 9th gate (`v2-acceptance-traceability`) fails only on `gap` status, not `partial` or `human_gate`. This is by design: `partial` requirements are expected at this phase (Phase 34 closes partials), and `human_gate` requirements (lawyer trial) are deferred to manual acceptance.
- The lawyer trial requirement (TRIAL-01) is classified as `human_gate`, not `gap`, because the infrastructure (`trial_acceptance.py`) exists but the actual 5-workday trial requires human execution.
- All output is deterministic: `generated_at: "deterministic"` placeholder, sorted keys, sorted lists, no timestamps. Same input codebase produces same output byte-for-byte.
- The script is stdlib-only: uses `argparse`, `ast`, `json`, `re`, `sys`, `dataclasses`, `pathlib`, `collections.abc`, `typing` — no new dependencies introduced. (The test module additionally uses `importlib`, `subprocess`, `unittest.mock`.)

## Result

**PASS** — All 7 requirements (AUDIT-01 through AUDIT-07) are satisfied. All 9 V2 gates pass green. The traceability matrix is complete, deterministic, and correctly classifies all 10 unchecked V2 Active requirements.
