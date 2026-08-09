---
phase: 111
plan: 111-02
status: complete
started: 2026-08-09T00:00:00Z
completed: 2026-08-09T00:05:00Z
---

# Plan 111-02 Summary

## Objective
Fix the BackendAdapter method count test regression (9 to 10) introduced by SAFE-06's `backend_family()` addition across all 4 assertion locations in 3 gates, and refresh the stale `protocols.py` SHA-256 hash in the contract freeze baseline.

## Tasks Completed
| Task | Description | Commit | Verification |
|------|-------------|--------|--------------|
| 1 | Update BackendAdapter count assertions 9 to 10 in qqbot-channel + qqbot-service gates; rename tests to `_10_methods`; add `backend_family` to `BACKEND_ADAPTER_METHODS` frozenset | bc67369 | Both `test_backend_adapter_has_exactly_10_methods` tests pass (2/2 OK) |
| 2 | Update `BACKEND_ADAPTER_METHOD_COUNT` from 9 to 10 in contract count freeze; refresh `protocols.py` SHA-256 hash from stale `afc6c808...` to actual `219ad588...` in `contract_freeze_baseline.json` | 315686e | `test_contract_count_freeze` (5/5 OK) + `test_contract_freeze` (2/2 OK) pass; hash verified via `sha256sum` |

## Artifacts Produced
- `packages/channels/qqbot/tests/test_v1_8_safety_baseline.py` (modified) — test renamed to `test_backend_adapter_has_exactly_10_methods`, count 9 to 10
- `services/qqbot-service/tests/test_host_safety_baseline.py` (modified) — test renamed, count 9 to 10, `backend_family` added to `BACKEND_ADAPTER_METHODS` frozenset
- `packages/contract-test-suite/tests/test_contract_count_freeze.py` (modified) — `BACKEND_ADAPTER_METHOD_COUNT` changed from 9 to 10
- `packages/contract-test-suite/fixtures/contract_freeze_baseline.json` (modified) — `protocols.py` SHA-256 hash updated from `afc6c808...` to `219ad58892b90b840aa642f90cd8d093f5e6d8b22cc67a2d51eb8dc7fc78a27c`

## Deviations
- None

## Deferred Issues
- None

## Verification Results
- `test_backend_adapter_has_exactly_10_methods` (qqbot-channel): PASS
- `test_backend_adapter_has_exactly_10_methods` (qqbot-service): PASS
- `test_contract_count_freeze` (contract-test-suite): PASS (5/5 tests OK)
- `test_contract_freeze` (contract-test-suite): PASS (2/2 tests OK)
- `sha256sum packages/platform-runtime/src/platform_runtime/protocols.py` output matches the hash in `contract_freeze_baseline.json`: `219ad58892b90b840aa642f90cd8d093f5e6d8b22cc67a2d51eb8dc7fc78a27c`
- qqbot-service gate: PASS (149/149 tests OK)
- qqbot-channel gate: BackendAdapter assertions PASS; pre-existing recall test `test_recall01_c2c_over_window_wakeup_omits_msg_id_on_wire` failure is accepted as carry from a prior phase (untouched, out of scope)
- Final verification: PASS (BackendAdapter assertions pass; recall carry accepted)
