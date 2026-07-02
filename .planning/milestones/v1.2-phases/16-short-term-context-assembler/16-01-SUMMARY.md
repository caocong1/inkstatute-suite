---
phase: 16-short-term-context-assembler
plan: 16-01
subsystem: platform-runtime
tags: [python, stdlib, context-bundle, short-term-context, privacy, tdd]
requires:
  - phase: 14-memory-research-and-contract-spec
    provides: ContextBundle contract schema and Python dataclass
  - phase: 15-session-resolver-and-interrupt-runtime
    provides: SessionScope, PendingInterruptSnapshot, and ActiveTaskSnapshot runtime inputs
provides:
  - Backend-neutral ContextAssembler surface for bounded short-term context assembly
  - Reference-first RollingSummaryRecord and scoped copy-safe InMemoryRollingSummaryStore
  - Deterministic budget trimming with protected current-turn, pending-clarification, and output-policy sections
affects: [phase-16, phase-17-memory-contracts, platform-runtime, backend-adapters]
tech-stack:
  added: []
  patterns: [stdlib-only frozen dataclasses, scoped in-memory store, reference-first privacy guard, deterministic value-budget estimator]
key-files:
  created:
    - packages/platform-runtime/src/platform_runtime/context_assembler.py
    - packages/platform-runtime/tests/test_context_assembler.py
  modified:
    - packages/platform-runtime/src/platform_runtime/__init__.py
key-decisions:
  - "Context assembly remains a platform-runtime library surface with no backend, channel, database, tokenizer, or external memory dependency."
  - "Budget estimation counts emitted values and refs deterministically rather than backend tokenizer tokens."
  - "Protected context is limited to current turn ref/hash/length, pending clarification refs, and output-policy/output-constraints refs; optional sections trim before backend submission."
patterns-established:
  - "Rolling summaries store summary_ref plus structured refs, hash, length, timestamps, scope, and sanitized metadata only."
  - "Long histories are capped first by policy and then trimmed in fixed feedback, memory, recent-turn, artifact, active-task order."
requirements-completed: [STM-01, STM-02, STM-03, STM-04]
duration: 8min
completed: 2026-07-01T11:23:29Z
---

# Phase 16 Plan 16-01: Core Context Assembler Summary

**Backend-neutral short-term context bundles with reference-first rolling summaries and deterministic protected-section trimming.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-01T11:15:47Z
- **Completed:** 2026-07-01T11:23:29Z
- **Tasks:** 2
- **Files modified:** 3 source/test files plus this summary

## Accomplishments

- Added `ContextAssembler`, `ContextAssemblyPolicy`, `ContextAssemblyInput`, `ContextAssemblyResult`, `ContextAssemblyBudgetError`, `RollingSummaryRecord`, and `InMemoryRollingSummaryStore`.
- Implemented scoped, copy-safe rolling summary storage keyed by full `SessionScope`.
- Implemented deterministic context bundle assembly from current turn refs, recent turn refs, active task refs, artifacts, feedback corrections, pending clarification refs, memory refs, output constraints, and rolling summaries.
- Added budget caps and fixed-order trimming that preserves current turn, pending clarification, and output policy refs, failing closed when protected context alone exceeds budget.
- Added unit tests for STM-01 through STM-04 plus privacy rejection and serialization checks.

## Task Commits

Each TDD gate was committed separately:

1. **Task 1 RED:** `ef90934` test(16-01): add failing context assembler contract tests
2. **Task 1 GREEN:** `3d5b68e` feat(16-01): add context assembly contracts
3. **Task 2 RED:** `3e14fb9` test(16-01): add failing context budget tests
4. **Task 2 GREEN:** `241c7db` feat(16-01): implement deterministic context assembly

## Files Created/Modified

- `packages/platform-runtime/src/platform_runtime/context_assembler.py` - New stdlib-only context assembly module, rolling summary record/store, budget policy/result, privacy-safe serialization, and deterministic trimming.
- `packages/platform-runtime/src/platform_runtime/__init__.py` - Public exports for the Phase 16 assembler and rolling summary symbols.
- `packages/platform-runtime/tests/test_context_assembler.py` - Unit tests for context source acceptance, rolling summary privacy, scoped storage, trimming, protected sections, impossible budgets, and deterministic output.
- `.planning/phases/16-short-term-context-assembler/16-01-SUMMARY.md` - Plan execution summary.

## Decisions Made

- Kept Phase 16 inside `packages/platform-runtime` only; no service, database, queue, backend adapter, channel adapter, tokenizer package, or external memory dependency was introduced.
- Reused the existing runtime privacy vocabulary via `ContractLogPrivacyError` behavior from session/store helpers, rejecting `raw_payload`, `raw_text`, `payload_text`, `full_text`, `document_text`, `customer_document_text`, and `case_facts`.
- Used a deterministic value-character budget estimator, not a tokenizer, so the surface remains backend-neutral and replayable.
- Treated rolling summary content as out-of-band behind `summary_ref`; emitted only refs, hash, length, timestamps, scope, and sanitized metadata.

## Deviations from Plan

None - plan executed within the allowed source/test files. Existing unrelated dirty files were present before execution, including planning, contract, and Phase 14 artifacts, but no unrelated changes were staged, reverted, or modified for this plan.

## Issues Encountered

- During Task 2 implementation, the initial estimator counted JSON object/key overhead, making protected metadata exceed tight test budgets. Resolved by estimating emitted values/refs deterministically, which better matches the plan's stdlib heuristic and keeps schema key names from consuming model budget.
- The protected-budget precheck initially included optional active-task and rolling-summary metadata. Resolved by checking only the never-droppable protected set before trimming optional sections.

## Verification

- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_context_assembler.py` passed: 10 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests` passed: 69 tests.
- `rg -n "ContextAssembler|ContextAssemblyPolicy|RollingSummaryRecord|InMemoryRollingSummaryStore" packages/platform-runtime/src/platform_runtime/context_assembler.py packages/platform-runtime/src/platform_runtime/__init__.py` confirmed the public symbols.
- Privacy coverage grep confirmed tests cover `raw_payload`, `full_text`, `payload_text`, and `case_facts`.

## Known Stubs

None. Empty tuple/list defaults and optional timestamp defaults in dataclasses are constructor defaults, not unfinished data-source stubs.

## Threat Flags

None. This plan added no network endpoints, auth paths, file access patterns, schema trust-boundary changes, services, queues, databases, or external memory adapters.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 16 can now wire runtime context assembly behind later feature flags or contract-test-suite fixtures. Phase 17 can consume `memory_refs` and summary refs without changing the assembler's reference-first privacy boundary.

## Self-Check: PASSED

- Created files exist: `packages/platform-runtime/src/platform_runtime/context_assembler.py`, `packages/platform-runtime/tests/test_context_assembler.py`, `.planning/phases/16-short-term-context-assembler/16-01-SUMMARY.md`.
- Modified export file exists: `packages/platform-runtime/src/platform_runtime/__init__.py`.
- Task commits exist: `ef90934`, `3d5b68e`, `3e14fb9`, `241c7db`.
- No tracked files were deleted by task commits.

---
*Phase: 16-short-term-context-assembler*
*Completed: 2026-07-01*
