---
phase: 88-unified-event-contract
plan: 02
subsystem: contract
tags: [run-event, replay, seq, resume, ingestion]

requires:
  - phase: 88-01
    provides: unified event vocabulary + RunEventType enum (23 members)

provides:
  - RunEvent dataclass with ingested_at (optional ISO 8601) and payload (optional typed dict) fields
  - run_event.schema.json with ingested_at and payload as optional properties
  - sort_events_by_seq pure function for out-of-order replay
  - resume_from_seq pure function for seq-based resume (no duplicates, no loss)
  - 5 replay/resume test methods covering out-of-order, arbitrary breakpoints, ingested_at semantics
  - Updated contract freeze baseline (46 files, includes 88-01 + 88-02 authorized changes)

affects: [88-05, 88-06]

key-files:
  created: []
  modified:
    - packages/platform-contract/src/platform_contract/events.py
    - packages/platform-contract/src/platform_contract/schemas/run_event.schema.json
    - packages/contract-test-suite/src/contract_test_suite/event_stream_replay.py
    - packages/contract-test-suite/tests/test_event_stream_replay.py
    - packages/contract-test-suite/fixtures/contract_freeze_baseline.json

key-decisions:
  - "ingested_at and payload added as optional fields after seq and before status — backward compatible, no existing field removed or renamed"
  - "payload reuses common.schema.json#/$defs/metadata as an extensible object (same pattern as metadata field)"
  - "sort_events_by_seq and resume_from_seq are pure functions — no side effects, no mutation of input"
  - "Contract freeze baseline updated to include 15 new 88-01 schema files + 5 modified files (88-01 + 88-02) — baseline was stale from v1.5"

patterns-established:
  - "Pattern: Additive-only RunEvent respecification — new optional fields, existing fields untouched"
  - "Pattern: Pure replay/resume functions — sort_events_by_seq and resume_from_seq have no side effects"
  - "Pattern: ingested_at distinct from occurred_at — occurred_at = backend production time, ingested_at = platform ingestion time"

requirements-completed: [EVT-02]

coverage:
  - id: D1
    description: "RunEvent dataclass has ingested_at and payload as optional fields"
    requirement: "EVT-02"
    verification:
      - kind: unit
        ref: "packages/platform-contract/tests/ (55 tests pass)"
        status: pass
    human_judgment: false
  - id: D2
    description: "run_event.schema.json includes ingested_at and payload as optional properties"
    requirement: "EVT-02"
    verification:
      - kind: unit
        ref: "inline assertion: schema properties and required array"
        status: pass
    human_judgment: false
  - id: D3
    description: "sort_events_by_seq correctly sorts out-of-order events by seq"
    requirement: "EVT-02"
    verification:
      - kind: unit
        ref: "packages/contract-test-suite/tests/test_event_stream_replay.py#test_out_of_order_events_replay_correctly_by_seq"
        status: pass
    human_judgment: false
  - id: D4
    description: "resume_from_seq returns exactly events with seq > last_seen_seq — no duplicates, no loss"
    requirement: "EVT-02"
    verification:
      - kind: unit
        ref: "packages/contract-test-suite/tests/test_event_stream_replay.py#test_resume_from_seq_no_duplicates_no_loss"
        status: pass
      - kind: unit
        ref: "packages/contract-test-suite/tests/test_event_stream_replay.py#test_resume_from_arbitrary_breakpoints"
        status: pass
    human_judgment: false
  - id: D5
    description: "occurred_at and ingested_at preserved through sort and resume operations"
    requirement: "EVT-02"
    verification:
      - kind: unit
        ref: "packages/contract-test-suite/tests/test_event_stream_replay.py#test_ingested_at_preserved_through_replay"
        status: pass
      - kind: unit
        ref: "packages/contract-test-suite/tests/test_event_stream_replay.py#test_occurred_at_and_ingested_at_semantics"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-07
status: complete
---

# Phase 88 Plan 02: RunEvent Respecification Summary

**RunEvent respecified as unified event carrier with ingested_at + payload fields, plus pure-function replay/resume utilities enabling out-of-order replay and seq-based resume with no duplicates and no loss**

## Performance

- **Duration:** ~25 min
- **Tasks:** 4
- **Files modified:** 5 (2 contract source, 1 test source, 1 test file, 1 baseline fixture)

## Accomplishments

- Added `ingested_at: str | None = None` and `payload: JsonObject | None = None` to RunEvent dataclass (additive, backward compatible)
- Added `ingested_at` and `payload` as optional properties to `run_event.schema.json` (required array unchanged)
- Implemented `sort_events_by_seq(events)` — pure function for out-of-order replay by seq ascending
- Implemented `resume_from_seq(events, last_seen_seq)` — pure function for seq-based resume (no duplicates, no loss)
- Created 5 test methods covering out-of-order replay, arbitrary breakpoints, ingested_at preservation, and occurred_at/ingested_at semantic distinction
- Updated contract freeze baseline to include 15 new 88-01 schema files + 5 modified files (baseline was stale from v1.5)

## Task Commits

1. **Task 88-02-01: Add ingested_at and payload fields** — `88683e4` (feat)
2. **Task 88-02-02: Implement replay/resume utilities** — `eb15f9f` (feat)
3. **Task 88-02-03: Create replay/resume tests** — `13666bd` (test)
4. **Task 88-02-04: Gate suite verification + baseline update** — `3d93b33` (fix)

## Files Created/Modified

- `packages/platform-contract/src/platform_contract/events.py` — RunEvent dataclass: +ingested_at, +payload fields
- `packages/platform-contract/src/platform_contract/schemas/run_event.schema.json` — +ingested_at, +payload optional properties
- `packages/contract-test-suite/src/contract_test_suite/event_stream_replay.py` — +sort_events_by_seq, +resume_from_seq
- `packages/contract-test-suite/tests/test_event_stream_replay.py` — +5 test methods, +_make_run_event_record helper
- `packages/contract-test-suite/fixtures/contract_freeze_baseline.json` — updated to 46 files (15 new + 5 changed)

## Decisions Made

1. **Additive-only RunEvent respecification** — ingested_at and payload added as optional fields after `seq` and before `status`. All existing fields preserved. No field removed, renamed, or changed. Backward compatible — existing code constructing RunEvent without these fields continues to work.

2. **payload reuses metadata $def** — `payload` uses `common.schema.json#/$defs/metadata` (extensible object) rather than a per-event-type discriminated union. This keeps the envelope schema simple; per-event-type validation is handled by the 15 event-type schemas from Plan 88-01.

3. **Pure replay/resume functions** — `sort_events_by_seq` and `resume_from_seq` are pure functions with no side effects and no mutation of input. They operate on plain dicts (RunEvent serialized form), not dataclass instances, for maximum interoperability.

4. **Contract freeze baseline update** — The v1.5 baseline was stale: 88-01 added 15 new schema files and modified 3 files (enums.py, common.schema.json, __init__.py) without updating the baseline. 88-02 modified 2 more files (events.py, run_event.schema.json). Updated baseline to 46 files with current SHA-256 hashes. This is a Rule 3 (blocking) deviation — the baseline must reflect authorized V3 contract changes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Contract freeze baseline stale (88-01 + 88-02)**
- **Found during:** Task 88-02-04 (gate suite verification)
- **Issue:** `test_contract_freeze.py` checks SHA-256 hashes against a v1.5 baseline. 88-01 added 15 new schema files and modified 3 files without updating the baseline. 88-02 modified 2 more files. This caused 6 contract freeze test failures (5 hash mismatches + 1 new files without baseline).
- **Fix:** Regenerated `contract_freeze_baseline.json` with current hashes for all 46 files (31 original + 15 new from 88-01). This fixes both 88-01 and 88-02 contract freeze failures.
- **Files modified:** packages/contract-test-suite/fixtures/contract_freeze_baseline.json
- **Verification:** `test_contract_freeze.py` — 2 tests, 46 subtests pass
- **Committed in:** 3d93b33

---

**Total deviations:** 1 auto-fixed (blocking)
**Impact on plan:** The contract freeze baseline update was necessary to unblock gate #25 (contract-test-suite). No scope creep — the baseline is infrastructure, not event logic.

## Issues Encountered

- **Pre-existing qqbot-channel gate 18 failures (7 tests):** Same `qqbot_passive_reply_window_expired` issue documented in 88-01-SUMMARY. Verified pre-existing at commit adda569 (88-01 final). Blocks gates 19-28 from running. Unrelated to 88-02 — my changes only touch platform-contract and contract-test-suite.
- **Pre-existing contract-test-suite failures (5 tests, from 88-01):** `test_allows_backend_mode_enum_values`, `test_allows_phase13_solution_and_loader_package_paths`, `test_docs_preserve_fixture_runtime_and_phase8_boundary`, `test_neutral_boundary_allowlist_passes_for_current_repo` (unified_events.py 'Event' field), `test_v2_gates_includes_traceability_gate` (expects 26 gates, got 28). All verified pre-existing at commit adda569. Not caused by 88-02 changes.

## Next Phase Readiness

- RunEvent is now the carrier for the unified event vocabulary with ingested_at + payload — ready for Plans 88-05 (bot degradation aggregator) and 88-06 (gate verification)
- Replay/resume utilities are pure functions ready for Gateway SSE implementation (Phase 91)
- Contract freeze baseline is current — future plans can detect unauthorized changes correctly
- **Blocker (carried from 88-01):** Pre-existing qqbot-channel test failures (gate 18) need a separate fix before Plan 88-06 can verify all 28 gates green
- **Blocker (carried from 88-01):** Pre-existing contract-test-suite failures (5 tests from 88-01 boundary/audit changes) need investigation before Plan 88-06

## Self-Check: PASSED

- [x] All 4 tasks executed and committed
- [x] RunEvent has ingested_at field (optional, ISO 8601 string)
- [x] RunEvent has payload field (optional, typed event data dict)
- [x] run_event.schema.json has ingested_at and payload as optional properties
- [x] No existing RunEvent field removed or renamed (backward compatible)
- [x] Out-of-order replay test passes (events sorted by seq produce correct monotonic order)
- [x] Seq-based resume test passes (from any breakpoint, no duplicates and no loss)
- [x] occurred_at / ingested_at / seq semantics preserved through replay operations
- [x] platform-contract tests pass: 55 tests
- [x] contract-test-suite test_event_stream_replay.py passes: 13 tests (8 existing + 5 new)
- [x] Gates 1-17 pass (platform-contract through rbac-annotation-scan)
- [x] Contract freeze baseline updated (46 files, 88-01 + 88-02 authorized changes)
- [x] V2's 5 persistence schemas not modified

---
*Phase: 88-unified-event-contract*
*Completed: 2026-08-07*
