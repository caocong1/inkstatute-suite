---
phase: 17-long-term-memory-and-feedback-learning
plan: 17-02
subsystem: feedback-learning
tags: [feedback, memory-candidate, context, human-review, unittest]
requires:
  - phase: 17-01
    provides: Privacy-safe memory store and policy helpers
provides:
  - FeedbackLearningPolicy
  - Feedback correction refs for current-session context
  - Pending memory/routing candidates from repeated negative feedback
  - Human-review/no-auto-modify route and skill candidate safeguards
affects: [platform-runtime, feedback-service, contract-test-suite]
tech-stack:
  added: []
  patterns: [feedback-event-shaped-input, refs-only-learning, human-review-candidates]
key-files:
  created:
    - packages/platform-runtime/tests/test_feedback_learning.py
  modified:
    - packages/platform-runtime/src/platform_runtime/memory.py
    - packages/platform-runtime/src/platform_runtime/__init__.py
    - .planning/phases/17-long-term-memory-and-feedback-learning/17-02-PLAN.md
    - .planning/phases/17-long-term-memory-and-feedback-learning/17-VALIDATION.md
key-decisions:
  - "Feedback learning consumes FeedbackEvent-shaped dictionaries without making feedback-service depend on platform-runtime."
  - "Correction feedback enters current-session context as refs and hash/length metadata, not raw feedback text."
  - "Route mismatch and skill candidate evidence always creates pending human-review/no-auto-modify candidates."
patterns-established:
  - "Repeated negative feedback is thresholded into pending MemoryCandidate records with source refs and confidence."
  - "Selected memory refs can be represented as MemoryUse records linked to a ContextBundle."
requirements-completed: [FBK-01, FBK-02, FBK-03, FBK-04, LTM-04]
duration: 8 min
completed: 2026-07-01
---

# Phase 17 Plan 02: Feedback Learning Policy Summary

**Refs-only feedback learning policy that produces context correction refs and pending human-review candidates**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-01T15:30:00Z
- **Completed:** 2026-07-01T15:38:04Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added `FeedbackLearningInput`, `FeedbackLearningResult`, and `FeedbackLearningPolicy`.
- Converted safe correction feedback into `feedback://.../correction` refs accepted by `ContextAssembler`.
- Added repeated-negative-feedback aggregation into pending `MemoryCandidate` records with source refs, confidence, and sanitized metadata.
- Added route mismatch and skill candidate safeguards: pending status, human review, and `no_auto_modify=true`.
- Preserved feedback-service dedupe/pending queue behavior by testing it through the corrected local environment.

## Task Commits

1. **Tasks 1-2: Feedback learning policy and queue regression evidence** - `632ba00` (feat)

## Files Created/Modified

- `packages/platform-runtime/src/platform_runtime/memory.py` - Feedback learning dataclasses, policy logic, MemoryCandidate/MemoryUse generation, and event privacy checks.
- `packages/platform-runtime/tests/test_feedback_learning.py` - Tests for correction refs, context integration, repeated-negative candidates, route/skill review gates, and raw payload rejection.
- `packages/platform-runtime/src/platform_runtime/__init__.py` - Public exports for feedback learning symbols.
- `.planning/phases/17-long-term-memory-and-feedback-learning/17-02-PLAN.md` - Corrected regression-test command environment.
- `.planning/phases/17-long-term-memory-and-feedback-learning/17-VALIDATION.md` - Corrected Phase 17 validation command environment.

## Decisions Made

- Keep feedback-service dependency direction unchanged: runtime consumes normalized event dictionaries instead of importing feedback-service.
- Keep all reusable learning outputs pending and reference-backed.
- Use deterministic candidate IDs derived from source refs and category/action.

## Deviations from Plan

None - plan executed within scope. The plan/validation command was corrected after execution revealed the feedback-service test also needs `packages/contract-test-suite/src` on `PYTHONPATH`.

## Issues Encountered

- The initial feedback queue regression command lacked `packages/contract-test-suite/src`, causing `ModuleNotFoundError: No module named 'contract_test_suite'`. The command was fixed in `17-02-PLAN.md` and `17-VALIDATION.md`, then rerun successfully.

## Verification

- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_feedback_learning.py` — passed, 6 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:services/feedback-service/src python -m unittest packages/platform-runtime/tests/test_feedback_learning.py services/feedback-service/tests/test_feedback_queue.py` — passed, 16 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests` — passed, 88 tests.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 17-03. Runtime behavior now has enough concrete outputs to create sanitized contract-suite fixture evidence and local verification commands.

## Self-Check: PASSED

---
*Phase: 17-long-term-memory-and-feedback-learning*
*Completed: 2026-07-01*
