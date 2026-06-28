---
phase: 06-read-and-feedback-service-apis
plan: 06-01
subsystem: api
tags: [contract-log, read-model, privacy, unittest]
requires:
  - phase: 05.5-inkstatute-wecom-service-and-hermes-agent-adapter
    provides: contract event fixtures and WeCom feedback boundary evidence
provides:
  - Dependency-light conversation-read-view package
  - Contract-log-derived conversation/task/trace indexes
  - Privacy helpers rejecting exact raw payload fields
  - Read-model tests for ordering, lookup, and missing associations
affects: [conversation-read-view, contract-test-suite, feedback-service]
tech-stack:
  added: []
  patterns: [stdlib-unittest, src-layout-service, derived-read-model]
key-files:
  created:
    - services/conversation-read-view/pyproject.toml
    - services/conversation-read-view/src/conversation_read_view/models.py
    - services/conversation-read-view/src/conversation_read_view/privacy.py
    - services/conversation-read-view/src/conversation_read_view/read_model.py
    - services/conversation-read-view/tests/test_read_model.py
  modified:
    - services/conversation-read-view/README.md
    - services/conversation-read-view/src/conversation_read_view/__init__.py
key-decisions:
  - "Read models are derived from contract logs and remain rebuildable, with no authoritative session database."
  - "Task lookup prefers metadata.task_id and aliases turn_id for compatibility."
  - "Missing route/trace/result facts are reported through missing_associations instead of fabricated."
patterns-established:
  - "ContractLogReadModel builds in-memory conversation, task, and trace indexes from EventStreamRecord or envelope dictionaries."
  - "Privacy helpers reject exact raw_payload keys while preserving raw_payload_ref references."
requirements-completed:
  - REQ-conversation-read-view
duration: 18 min
completed: 2026-06-28
---

# Phase 06 Plan 01: Contract Log Read Model Summary

**Dependency-light read model over V2 contract logs with conversation, task, trace, ordering, and privacy guarantees**

## Performance

- **Duration:** 18 min
- **Started:** 2026-06-28T07:12:00Z
- **Completed:** 2026-06-28T07:29:43Z
- **Tasks:** 4
- **Files modified:** 7

## Accomplishments

- Added `services/conversation-read-view/` as a zero-runtime-dependency Python service package.
- Implemented privacy helpers that reject exact `raw_payload` fields and preserve reference fields such as `raw_payload_ref`.
- Implemented `ContractLogReadModel` with deterministic sorting, conversation lookup, task lookup, trace lookup, and missing-association metadata.
- Added 11 stdlib unit tests covering fixture replay, task id fallback/preference, trace lookup, shuffled records, missing associations, package exports, and no-authority documentation.

## Task Commits

1. **Task 06-01-01: Scaffold package** - `402f39e` (feat)
2. **Task 06-01-02: Privacy and loading helpers** - `a44e8c2` (feat)
3. **Task 06-01-03: Read-model indexes** - `e5b2b3c` (feat)
4. **Task 06-01-04: Privacy and authority tests** - `e6bdcb0` (test)

## Files Created/Modified

- `services/conversation-read-view/pyproject.toml` - New service package metadata with `dependencies = []`.
- `services/conversation-read-view/README.md` - Scope, privacy, derived authority, and lookup documentation.
- `services/conversation-read-view/src/conversation_read_view/__init__.py` - Package exports for read-model helpers.
- `services/conversation-read-view/src/conversation_read_view/models.py` - Dataclasses for conversation, task, event refs, and issues.
- `services/conversation-read-view/src/conversation_read_view/privacy.py` - Exact raw payload detection and payload scrubbing.
- `services/conversation-read-view/src/conversation_read_view/read_model.py` - JSONL loading and derived indexes.
- `services/conversation-read-view/tests/test_read_model.py` - Unit tests for Plan 06-01 behavior.

## Decisions Made

- Kept contract-test-suite usage lazy inside `load_records_from_jsonl` so importing `conversation_read_view` does not require a declared runtime dependency.
- Indexed both preferred task ids and fallback `turn_id` aliases so old contract streams remain queryable.
- Kept missing associations visible in response dictionaries instead of inventing task status, trace, route, or result data.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed. **Impact on plan:** None.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Verification

- `PYTHONPATH=services/conversation-read-view/src:packages/contract-test-suite/src python -m unittest discover services/conversation-read-view/tests` - passed, 11 tests.
- `python -m compileall services/conversation-read-view/src` - passed.

## Self-Check: PASSED

- Key files listed in frontmatter exist.
- Task commits exist for `06-01`.
- Plan verification commands passed.

## Next Phase Readiness

Plan 06-02 can build the feedback queue independently. Plan 06-03 can route `/conversations/{id}` and `/tasks/{id}` through `ContractLogReadModel` and integrate pending feedback once Plan 06-02 is complete.

---
*Phase: 06-read-and-feedback-service-apis*
*Completed: 2026-06-28*

