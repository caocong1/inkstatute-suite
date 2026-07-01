---
phase: 17-long-term-memory-and-feedback-learning
plan: 17-03
subsystem: contract-test-suite
tags: [contract-fixture, memory, feedback, privacy, verification]
requires:
  - phase: 17-01
    provides: Privacy-safe memory store and retrieval policy
  - phase: 17-02
    provides: Feedback learning outputs and pending candidate policy
provides:
  - Sanitized Phase 17 contract fixture
  - Focused fixture relationship and privacy tests
  - Prepared local verification command set
affects: [contract-test-suite, phase-18-memory-adapters]
tech-stack:
  added: []
  patterns: [synthetic-fixture, refs-only-evidence, schema-validation, human-review-gates]
key-files:
  created:
    - packages/contract-test-suite/fixtures/phase17_long_term_memory_feedback_learning.json
    - packages/contract-test-suite/tests/test_phase17_long_term_memory_feedback_learning.py
  modified:
    - packages/contract-test-suite/tests/test_schema_validation.py
key-decisions:
  - "Use synthetic refs, hashes, lengths, counts, and statuses instead of raw legal/customer payloads."
  - "Record memory/context/feedback/candidate relationships in the contract fixture rather than requiring live WeCom, Hermes, or external memory systems."
  - "Keep route mismatch and skill candidate evidence pending, human-reviewed, and no-auto-modify."
patterns-established:
  - "Contract fixtures can include optional memory_records, memory_candidates, memory_uses, and context_bundle evidence."
  - "Prepared verification commands must include actual repository source roots, including solutions/lawfirm/src and solutions/demo_non_legal/src for full contract-suite runs."
requirements-completed: [LTM-03, LTM-04, FBK-01, FBK-02, FBK-03, FBK-04]
duration: 12 min
completed: 2026-07-01
---

# Phase 17 Plan 03: Contract Fixture and Verification Environment Summary

**Sanitized Phase 17 evidence plus runnable local tests for memory, feedback, context, and human-review safeguards**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-01T15:38:00Z
- **Completed:** 2026-07-01T15:50:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `phase17_long_term_memory_feedback_learning.json` with required platform events plus context bundle, memory records, memory candidates, and memory uses.
- Added focused contract tests for schema validation, memory-to-context links, memory-use links, feedback correction refs, pending repeated-negative candidates, route/skill human-review gates, and recursive privacy scans.
- Registered the Phase 17 fixture id with the existing schema validation expected fixture set.
- Prepared a working full contract-suite command using the actual local source roots for solution materializers.

## Task Commits

1. **Tasks 1-2: Phase 17 fixture, relationship tests, and schema registration** - `b094d3b` (test)

## Files Created/Modified

- `packages/contract-test-suite/fixtures/phase17_long_term_memory_feedback_learning.json` - Synthetic refs-only fixture proving Phase 17 memory, feedback, context, and candidate relationships.
- `packages/contract-test-suite/tests/test_phase17_long_term_memory_feedback_learning.py` - Focused tests for relationships, privacy, human review, candidate metadata, and prepared command evidence.
- `packages/contract-test-suite/tests/test_schema_validation.py` - Adds `phase17-long-term-memory-feedback-learning-001` to the expected fixture ids.

## Decisions Made

- Keep the fixture explicitly synthetic and local-only; it is not live WeCom/legal acceptance and does not claim external memory adapter readiness.
- Use `raw_payload_ref`, `feedback://`, `memory://`, and `fixture://` references for inspectable evidence without committing raw payloads.
- Treat user validation readiness as a concrete test environment problem, so the fixture metadata and test source both document focused commands.

## Deviations from Plan

- The initial full contract-suite command used non-existent `packages/solutions/...` paths. The working repository layout uses `solutions/lawfirm/src` and `solutions/demo_non_legal/src`; the full-suite command was corrected and rerun successfully.

## Issues Encountered

- A nested partial `route_decision` object in the first fixture draft failed schema validation because the schema requires complete route decision fields. The fixture now keeps the complete route decision at the top-level event and links trace metadata by id.
- The full contract-suite first failed with `ModuleNotFoundError: No module named 'inkstatute_solutions_lawfirm'` until the actual `solutions/*/src` roots were added to `PYTHONPATH`.

## Verification

- `python -m json.tool packages/contract-test-suite/fixtures/phase17_long_term_memory_feedback_learning.json >/dev/null` - passed.
- `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase17_long_term_memory_feedback_learning.py'` - passed, 8 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` - passed, 9 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src:packages/platform-runtime/src:packages/backends/hermes/src:packages/solution-loader/src:solutions/lawfirm/src:solutions/demo_non_legal/src:packages/channels/wecom/src:packages/channels/web_sse/src:services/wecom-service/src:services/feedback-service/src:services/conversation-read-view/src python -m unittest discover -s packages/contract-test-suite/tests` - passed, 171 tests.

## User Setup Required

None for local verification. The prepared commands run against synthetic fixtures and local source roots only.

## Next Phase Readiness

Ready for Phase 17 verification and review. Phase 18 can use this fixture and command set as acceptance evidence when evaluating external memory adapters.

## Self-Check: PASSED

---
*Phase: 17-long-term-memory-and-feedback-learning*
*Completed: 2026-07-01*
