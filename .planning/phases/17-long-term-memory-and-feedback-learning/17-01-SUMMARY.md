---
phase: 17-long-term-memory-and-feedback-learning
plan: 17-01
subsystem: runtime-memory
tags: [memory, privacy, context, unittest]
requires:
  - phase: 16-short-term-context-assembler
    provides: ContextAssembler scope and privacy patterns
provides:
  - Privacy-safe in-memory MemoryRecord store
  - Scoped deterministic memory retrieval
  - TTL/deletion/confidence/sensitivity policy gates
affects: [platform-runtime, phase-18-memory-adapters]
tech-stack:
  added: []
  patterns: [stdlib-only, copy-safe-store, reference-first-privacy, deterministic-ranking]
key-files:
  created:
    - packages/platform-runtime/src/platform_runtime/memory.py
    - packages/platform-runtime/tests/test_memory_store.py
  modified:
    - packages/platform-runtime/src/platform_runtime/__init__.py
key-decisions:
  - "Keep Phase 17 MemoryStore in packages/platform-runtime as a dependency-free support surface."
  - "Use deterministic lexical/label/source-ref ranking instead of vector search or external memory systems."
  - "Exclude deleted, suppressed, expired, low-confidence, and disallowed-sensitivity memory records from retrieval."
patterns-established:
  - "Memory store reads return copies so callers cannot mutate store state."
  - "Memory privacy checks reject exact raw/full-text payload keys while allowing raw_payload_ref."
requirements-completed: [LTM-03, LTM-04]
duration: 15 min
completed: 2026-07-01
---

# Phase 17 Plan 01: Platform-Native Memory Store Summary

**Dependency-free scoped MemoryRecord store with deterministic privacy-safe retrieval and policy gates**

## Performance

- **Duration:** 15 min
- **Started:** 2026-07-01T15:20:00Z
- **Completed:** 2026-07-01T15:35:07Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `InMemoryMemoryStore`, `MemoryQuery`, `MemorySearchResult`, `MemoryStorePolicy`, and `MemoryPrivacyError`.
- Implemented tenant/workspace/session/user/workspace/tenant scope filtering with deterministic relevance sorting and bounded result counts.
- Added privacy gates for raw/full-text/secret-like fields plus retrieval gates for status, TTL, confidence, and sensitivity.
- Exported the memory store surface from `platform_runtime`.

## Task Commits

1. **Tasks 1-2: Memory store, retrieval, and policy gates** - `e2465ee` (feat)

## Files Created/Modified

- `packages/platform-runtime/src/platform_runtime/memory.py` - Runtime memory store, query/result dataclasses, privacy checks, deterministic retrieval, and delete policy support.
- `packages/platform-runtime/tests/test_memory_store.py` - Unit tests for scoping, ranking, copy safety, status/TTL/confidence/sensitivity gates, and privacy rejection.
- `packages/platform-runtime/src/platform_runtime/__init__.py` - Public exports for memory store symbols.

## Decisions Made

- Keep retrieval lexical/label/ref based for Phase 17 so tests are deterministic and no vector/external dependency is introduced.
- Treat `restricted` memory as disallowed by default policy while allowing callers to opt into alternate policy later.
- Use `raw_payload_ref` as the allowed evidence pointer and reject exact unsafe payload/full-text keys.

## Deviations from Plan

None - plan executed within the intended Phase 17 memory store scope. The two planned tasks landed in one coherent implementation commit because the privacy gates and store API are tightly coupled.

## Issues Encountered

- Initial ranking test data accidentally inherited a matching subject/label on the unrelated memory fixture. The fixture was corrected so the test now proves label-aware ranking deterministically.

## Verification

- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_store.py` — passed, 7 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests` — passed, 82 tests.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 17-02. Feedback learning can now create correction refs and candidates using the memory store policy/privacy helpers.

## Self-Check: PASSED

---
*Phase: 17-long-term-memory-and-feedback-learning*
*Completed: 2026-07-01*
