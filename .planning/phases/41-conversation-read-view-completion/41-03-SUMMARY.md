---
phase: 41
plan: 41-03
title: "Read-Time Privacy Scrubbing on New Endpoints, Backward Compatibility Tests, and V2 Gate Verification"
wave: 3
requirements:
  - READVIEW-03
  - READVIEW-01
  - READVIEW-02
  - SAFETY-02
  - SAFETY-06
status: complete
---

# Plan 41-03 — Summary

## Tasks Completed

| Task ID | Description | Commit |
|---------|-------------|--------|
| 41-03-01 | Extend `test_privacy_scrub.py` with `ForbiddenKeyFakeReadModel` and `NewEndpointPrivacyScrubTests` class (9 tests) covering all 4 new endpoints' scrub behavior | `4d255df` |
| 41-03-02 | Create `test_backward_compat.py` with `BackwardCompatTests` class (7 tests) snapshotting existing endpoint response top-level key sets | `ffa9b08` |
| 41-03-03 | Run full V2 gate suite (13 gates), verify SAFETY-02 contract freeze, verify no contract drift | — (verification only) |

## Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| `test_privacy_scrub.py` (PrivacyScrubTests — existing) | 6 | PASS |
| `test_privacy_scrub.py` (NewEndpointPrivacyScrubTests — new) | 9 | PASS |
| `test_backward_compat.py` (BackwardCompatTests — new) | 7 | PASS |
| Full conversation-read-view discover suite | 106 | PASS |
| SAFETY-02 contract-count freeze tests | 3 | PASS |
| Full V2 gate suite (`scripts/run_v2_gates.py`) | 13 gates | PASS (exit 0) |

**Total: 106 conversation-read-view tests — all green, 0 failures.**
**V2 gates: 13/13 pass with exit code 0.**

### V2 Gate Breakdown

| # | Gate | Tests | Result |
|---|------|-------|--------|
| 1 | platform-contract | 21 | PASS |
| 2 | wecom-service | 72 | PASS |
| 3 | hermes-contract-layer | 35 | PASS |
| 4 | conversation-read-view | 106 | PASS |
| 5 | skill-registry | 35 | PASS |
| 6 | router-service | 33 | PASS |
| 7 | codex-backend | 32 | PASS |
| 8 | provider-model-backend | 37 | PASS |
| 9 | feedback-service | 31 | PASS |
| 10 | phase7-privacy-boundary | 13 | PASS |
| 11 | contract-test-suite | 323 | PASS |
| 12 | v2-acceptance-traceability | — | PASS |
| 13 | compileall | — | PASS |

### SAFETY-02 Contract Freeze Verification

- `BACKEND_ADAPTER_METHOD_COUNT == 9` — PASS
- `ADAPTER_CAPABILITY_SET_FIELD_COUNT == 14` — PASS
- `CHANNEL_ADAPTER_METHOD_COUNT == 6` — PASS

### Contract Drift Verification

- `git diff --name-only packages/platform-contract/src/` → no output (no drift)
- `git diff --name-only packages/platform-runtime/src/platform_runtime/protocols.py` → no output (no drift)
- `services/conversation-read-view/pyproject.toml` still has `dependencies = []`

## Files Modified/Created

| File | Action |
|------|--------|
| `services/conversation-read-view/tests/test_privacy_scrub.py` | Modified — added `ForbiddenKeyFakeReadModel` class and `NewEndpointPrivacyScrubTests` class with 9 tests |
| `services/conversation-read-view/tests/test_backward_compat.py` | Created — `BackwardCompatTests` class with 7 tests snapshotting existing endpoint response shapes |

## Key Implementation Details

- **Privacy scrubbing on new endpoints:** All 4 new endpoints (`/conversations` list, `/tasks` list, `/traces/{trace_id}`, `/export`) raise `ValueError` when the response contains any key in `ALL_FORBIDDEN_KEYS`. Verified with 9 tests covering:
  - Individual endpoint forbidden-key assertions (6 tests)
  - All `ALL_FORBIDDEN_KEYS` keys via `subTest` on `/conversations` (1 test, 11 sub-tests)
  - Forbidden key in nested event dict within trace reconstruction (1 test)
  - Forbidden key in nested item metadata within export (1 test)
- **Backward compatibility:** 7 tests snapshot exact top-level key sets for:
  - `/conversations/{id}` → `{conversation_id, turn_count, user_ids, turns, metadata, issues}`
  - `/tasks/{id}` → 17 keys including `metadata` (added by `_with_contract_metadata`)
  - `/feedback?status=pending` → `{items, count, metadata}`
  - 404 response shape → `{error, metadata}` with `error.code == "not_found"`
  - Turn-level keys (assertGreaterEqual for optional `fallback_source`)
  - `lookup_aliases` structure unchanged
  - `handle_get` signature unchanged: `(path, query, read_model, feedback_queue=None)`
- **Contract freeze:** No files in `packages/platform-contract/` or `packages/platform-runtime/protocols.py` were modified by Phase 41.
- **Dependencies:** `pyproject.toml` still has `dependencies = []`.

## Deviations from Plan

- **Task response `metadata` key:** The plan's expected task top-level keys did not include `metadata`, but `_with_contract_metadata` adds a `metadata` key to every single-resource response (including `/tasks/{id}`). The test was adjusted to include `metadata` in the expected key set. This reflects the actual existing behavior — no behavioral deviation from the implementation, only a correction in the test's expected key set.
- **Task 03 is verification-only:** No code was written for Task 41-03-03. All verification checks passed: 13 gates green, SAFETY-02 freeze tests green, no contract drift, `dependencies = []` confirmed.

## EXECUTION COMPLETE
