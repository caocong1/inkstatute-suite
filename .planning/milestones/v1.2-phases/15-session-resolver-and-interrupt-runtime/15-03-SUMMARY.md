---
phase: 15-session-resolver-and-interrupt-runtime
plan: 15-03
subsystem: wecom-service
tags: [wecom, session-resolution, interrupt-runtime, contract-fixture, privacy, tdd]
requires:
  - phase: 15-session-resolver-and-interrupt-runtime
    provides: resolver policy and interrupt resume runtime from 15-01 and 15-02
provides:
  - WeCom session runtime helper for pending interrupt resume and active-task precedence
  - InkStatute-owned clarification delivery envelope through existing output policy
  - Phase 15 sanitized contract fixture and contract-suite assertions
affects: [wecom-service, contract-test-suite, phase-16-context-assembler]
tech-stack:
  added: []
  patterns:
    - stdlib-only WeCom orchestration seam over platform-runtime primitives
    - reference-first branch evidence for session and interrupt decisions
    - exact enum assertions for waiting_for_user and needs_clarification
key-files:
  created:
    - services/wecom-service/src/wecom_service/session_runtime.py
    - services/wecom-service/tests/test_session_interrupt_runtime.py
    - packages/contract-test-suite/fixtures/phase15_session_interrupt_runtime.json
    - packages/contract-test-suite/tests/test_phase15_session_interrupt_runtime.py
  modified:
    - services/wecom-service/src/wecom_service/__init__.py
    - packages/contract-test-suite/tests/test_schema_validation.py
key-decisions:
  - "Kept WeCom Phase 15 integration as a pure helper with injected runtime/store/capabilities and no server, network IO, DB, queue, Hermes import, or raw callback parsing."
  - "Resolved pending interrupts before active-task and recent-session handling, then delegated active-task follow-ups to the existing route_active_task_turn classifier."
  - "Represented fixture evidence with refs, hashes, lengths, IDs, statuses, and branch metadata only; no raw payload, full-text, secret, internal path, or user command requirement is stored."
patterns-established:
  - "WeComSessionRuntimeOutcome.as_event() exposes sanitized decision, active-task route, delivery metadata, and evidence for future contract logging."
  - "build_clarification_delivery() routes ordinary clarification text through build_text_send_envelope and the existing output policy boundary."
requirements-completed:
  - CTX-01
  - CTX-02
  - CTX-03
  - CTX-04
  - INT-01
  - INT-02
  - INT-03
  - INT-04
duration: 5h20m elapsed across interrupted/resumed execution
completed: 2026-07-01
---

# Phase 15 Plan 15-03: WeCom Integration Evidence and Contract Fixtures Summary

**WeCom session runtime helper plus privacy-safe Phase 15 fixture evidence for pending clarification resume, active-task precedence, and session splitting.**

## Performance

- **Duration:** 5h20m elapsed across interrupted/resumed execution
- **Started:** 2026-07-01T07:00:00+08:00
- **Completed:** 2026-07-01T12:20:23+08:00
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `WeComSessionRuntime` as a stdlib-only orchestration helper over `resolve_session_turn`, `InMemoryInterruptStore`, `RunRuntime.resume_interrupt`, existing active-task routing, and existing WeCom send envelopes.
- Covered pending interrupt resume, cross-user scope isolation, active-task precedence, stale/terminal/new-task splits, duplicate idempotency, expired/cancelled interrupts, and output policy behavior in WeCom tests.
- Added `phase15_session_interrupt_runtime.json` and focused contract-suite assertions for exact `waiting_for_user` / `needs_clarification` evidence, branch coverage, run-event ordering, and privacy boundaries.
- Registered the Phase 15 fixture in schema validation expectations without introducing a new validator.

## Task Commits

1. **Task 1 RED: WeCom session runtime coverage** - `02e8b10` (test)
2. **Task 1 GREEN: WeCom session interrupt runtime helper** - `87aa2fd` (feat)
3. **Task 2: Phase 15 contract fixture and assertions** - `d1f0fea` (test)

## Files Created/Modified

- `services/wecom-service/src/wecom_service/session_runtime.py` - Pure WeCom/platform orchestration helper and sanitized outcome/event model.
- `services/wecom-service/src/wecom_service/__init__.py` - Public exports for the helper, outcome/action enum, and clarification delivery builder.
- `services/wecom-service/tests/test_session_interrupt_runtime.py` - WeCom runtime behavior tests across resume, active task, stale/new, duplicate, timeout, cancel, and output policy branches.
- `packages/contract-test-suite/fixtures/phase15_session_interrupt_runtime.json` - Sanitized Phase 15 fixture evidence.
- `packages/contract-test-suite/tests/test_phase15_session_interrupt_runtime.py` - Targeted Phase 15 contract-suite assertions.
- `packages/contract-test-suite/tests/test_schema_validation.py` - Expected fixture ID updated for the Phase 15 fixture.

## Decisions Made

- The helper accepts already-normalized `AgentTurn`/runtime request data. It does not parse raw WeCom XML and does not own persistence beyond injected in-memory/runtime collaborators.
- Duplicate answer idempotency is tracked at the WeCom helper boundary by idempotency key and at the runtime/store boundary by interrupt lifecycle metadata.
- Expired/cancelled interrupt outcomes are surfaced as explicit runtime actions with `resume_attempted: false`, preserving deterministic user-flow evidence without pretending a backend resume occurred.
- Clarification delivery uses InkStatute-owned WeCom send-envelope primitives so backend gateway/help/debug notices are blocked or rewritten before ordinary delivery.

## Deviations from Plan

None - plan executed within the requested files and scope.

### Auto-fixed Issues

None.

## Issues Encountered

- The resumed Task 1 fake runtime initially did not mutate the interrupt store in one duplicate-answer assertion. The test harness was wired to the same in-memory store used by the helper, matching the real `DefaultRunRuntime.resume_interrupt` behavior.
- The first fixture ref path used a `runtime://.../resume/...` segment. It was renamed to `runtime://.../continuation-state/...` so fixture evidence contains no `/resume` or `/new` command-like strings.

## Verification

- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:services/wecom-service/src:packages/channels/wecom/src python -m unittest discover -s services/wecom-service/tests -p 'test_session_interrupt_runtime.py'` - passed, 6 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase15_session_interrupt_runtime.py'` - passed, 6 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` - passed, 9 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:services/wecom-service/src:packages/contract-test-suite/src python -m unittest discover -s packages/platform-runtime/tests` - passed, 57 tests.

## User Setup Required

None - no external service, dependency, database, queue, secret, or deployment setup was added.

## Next Phase Readiness

Phase 15 now has resolver, interrupt runtime, WeCom integration, and contract-suite evidence for ordinary users to continue, clarify, or start a new task without session commands. Phase 16 can build bounded short-term context assembly on top of the stable session and interrupt IDs, run statuses, branch evidence, refs, and privacy-safe metadata.

## Self-Check: PASSED

- Found `services/wecom-service/src/wecom_service/session_runtime.py`.
- Found `services/wecom-service/tests/test_session_interrupt_runtime.py`.
- Found `packages/contract-test-suite/fixtures/phase15_session_interrupt_runtime.json`.
- Found `packages/contract-test-suite/tests/test_phase15_session_interrupt_runtime.py`.
- Found commits `02e8b10`, `87aa2fd`, and `d1f0fea`.
- Verification commands passed after the final task commit.

---
*Phase: 15-session-resolver-and-interrupt-runtime*
*Completed: 2026-07-01*
