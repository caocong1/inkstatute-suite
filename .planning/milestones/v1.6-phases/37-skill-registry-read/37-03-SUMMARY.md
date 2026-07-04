---
phase: 37
plan: 03
title: "V2 gate integration and contract freeze verification"
wave: 3
requirements:
  - SKILL-01
  - SKILL-02
status: complete
---

# Plan 37-03 — Summary: V2 Gate Integration and Contract Freeze Verification

## Tasks Completed

### Task 01 — Add skill-registry gate and update compileall and contract-test-suite gates

**Commit:** `a5e429b`

**Changes:**
- `scripts/run_v2_gates.py`:
  - Added `skill_registry_src` path variable (line 62)
  - Added new `skill-registry` gate (lines 85-89) with PYTHONPATH `(skill_registry_src, platform_src, platform_runtime_src)`
  - Updated `compileall` gate to include `"packages/skill-registry/src"` in its path list (line 124)
  - Updated `contract-test-suite` gate PYTHONPATH to append `skill_registry_src` (line 109)

**Acceptance Criteria Verified:**
- `python scripts/run_v2_gates.py --list` includes `skill-registry` ✓
- `skill-registry` gate has `pythonpath` tuple containing `skill_registry_src`, `platform_src`, and `platform_runtime_src` ✓
- `compileall` gate command tuple includes `"packages/skill-registry/src"` ✓
- `contract-test-suite` gate `pythonpath` tuple includes `skill_registry_src` ✓
- `python -m compileall scripts/run_v2_gates.py` exits 0 ✓

### Task 02 — Verify full V2 gate suite green and contract freeze not violated

**Commit:** `04d2498`

**Deviation:** The existing test `test_v2_gates_includes_traceability_gate` in `packages/contract-test-suite/tests/test_audit_v2_requirements.py` hardcoded the gate count as 9. With the new `skill-registry` gate, the count became 10, causing the `contract-test-suite` gate to fail. Fixed by updating the assertion from 9 to 10 and adding an `assertIn("skill-registry", gate_names)` check. This file is in `packages/contract-test-suite/tests/`, not `packages/platform-contract/`, so SAFETY-06 is not violated.

**Acceptance Criteria Verified:**
- `python scripts/run_v2_gates.py` exits 0 — all 10 gates green ✓
- Contract freeze test passes (2 tests, OK) ✓
- `python scripts/run_v2_gates.py --json-summary` outputs `{"passed": true, ...}` with 10 gate entries all having `exit_code: 0` ✓
- No files in `packages/platform-contract/src/platform_contract/schemas/` modified ✓

## Test Results

### Full V2 Gate Suite (10 gates)

| Gate | Tests | Result |
|------|-------|--------|
| platform-contract | 21 | PASS |
| wecom-service | 72 | PASS |
| hermes-contract-layer | 30 | PASS |
| conversation-read-view | 24 | PASS |
| skill-registry | 35 | PASS |
| feedback-service | 31 | PASS |
| phase7-privacy-boundary | 13 | PASS |
| contract-test-suite | 300 | PASS |
| v2-acceptance-traceability | — | PASS |
| compileall | — | PASS |

**Total:** 10 gates, 526 test cases, all green.

### Contract Freeze Test

- `test_schema_files_match_baseline_hash`: PASS
- `test_no_new_schema_files_added_without_baseline`: PASS
- SAFETY-06 preserved — no `packages/platform-contract/` modifications.

### Skill-Registry Tests (independent run)

- `test_mapper.py`: 4 cases PASS
- `test_registry.py`: 10 cases PASS
- `test_discovery.py`: 9 cases PASS
- `test_api.py`: 12 cases PASS
- **Total:** 35 test cases, all PASS.

## Files Modified

1. `scripts/run_v2_gates.py` — new `skill-registry` gate, updated `compileall` gate paths, updated `contract-test-suite` gate PYTHONPATH
2. `packages/contract-test-suite/tests/test_audit_v2_requirements.py` — updated gate count assertion from 9 to 10 (deviation fix)

## Deviations

- **Gate count assertion fix:** The plan's `files_modified` list only included `scripts/run_v2_gates.py`, but the existing test `test_v2_gates_includes_traceability_gate` in `packages/contract-test-suite/tests/test_audit_v2_requirements.py` hardcoded `len(gate_names) == 9`. Adding the 10th gate caused this test to fail. The fix was necessary to make the full V2 gate suite green, which is a core acceptance criterion of Task 02. The plan's Task 02 action step 4 explicitly anticipates this: "If any gate fails, diagnose and fix the issue." The modified file is in `packages/contract-test-suite/tests/`, not `packages/platform-contract/`, so SAFETY-06 is not violated.

## EXECUTION COMPLETE
