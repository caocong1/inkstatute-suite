---
phase: 04-hermes-shadow-event-layer
plan: 03
subsystem: contract-test-suite
tags: [event-stream-replay, jsonl, fixtures, relationships, privacy]

requires:
  - phase: 04-02
    provides: Phase 4 mapper and JSONL envelope writer shape
provides:
  - Event-stream replay helper for Phase 4 partial JSONL streams
  - Three Phase 4 JSONL stream fixtures
  - Contract-test-suite coverage for success, simple-QA/unmatched, and failed long-task paths
affects: [phase-05-wecom-shadow-loop-validation, phase-07-ci-composability-privacy-gates]

tech-stack:
  added: []
  patterns:
    - Reuse existing `validate_event` schema validation for nested stream payloads
    - Separate partial stream replay from full five-event fixture bundle replay
    - Structured event-stream issue/report dataclasses

key-files:
  created:
    - packages/contract-test-suite/src/contract_test_suite/event_stream_replay.py
    - packages/contract-test-suite/tests/test_event_stream_replay.py
    - packages/contract-test-suite/fixtures/phase4_success_event_stream.jsonl
    - packages/contract-test-suite/fixtures/phase4_simple_qa_event_stream.jsonl
    - packages/contract-test-suite/fixtures/phase4_failed_long_task_event_stream.jsonl
    - .planning/phases/04-hermes-shadow-event-layer/04-03-SUMMARY.md
  modified:
    - packages/contract-test-suite/README.md
    - .planning/ROADMAP.md
    - .planning/STATE.md
    - .planning/phases/04-hermes-shadow-event-layer/04-VALIDATION.md

key-decisions:
  - "Phase 4 JSONL stream replay validates AgentTurn, RouteDecision, ExecutionTrace, and AgentResult without requiring FeedbackEvent."
  - "Existing full-bundle fixture replay remains unchanged; partial stream replay is a separate helper."
  - "Committed stream fixtures use only synthetic text plus `fixture://` and `raw_payload_ref` references."

patterns-established:
  - "Event stream reports include stream path, event key, relationship, field path, expected value, and actual value."
  - "Relationship checks cover shared turn IDs, route IDs, trace IDs, and artifact links when artifacts exist."
  - "The package-local runner discovers `test_event_stream_replay.py` without runner changes."

requirements-completed:
  - REQ-observability-and-replay
  - REQ-hermes-contract-layer

duration: 8min
completed: 2026-06-28
---

# Phase 04 Plan 03: Event Stream Replay Summary

Phase 4 now has contract-test-suite support for replaying partial Hermes shadow JSONL streams without fabricating feedback records.

## Accomplishments

- Added `event_stream_replay.py` with `load_event_stream`, `replay_event_streams`, `assert_event_stream_integrity`, `EventStreamIssue`, and `EventStreamReport`.
- Added three Phase 4 JSONL fixtures covering normal success with artifact linkage, simple-QA/no registered skill, and failed long-task status with `queued`, `running`, and `failed` steps.
- Added tests for envelope validation, nested schema validation, missing FeedbackEvent acceptance, broken turn/trace/route/artifact relationships, exact async states, runtime error category, and privacy scanning.
- Documented the Phase 4 event-stream boundary in the contract-test-suite README.

## Verification

- PASS: `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python -m unittest discover -s tests -p 'test_event_stream_replay.py' -v` ran 7 tests successfully.
- PASS: Full Phase 4 verification command ran `compileall`, the package-local contract-test-suite runner with 36 tests, and all 18 service tests successfully.
- PASS: Existing full-bundle fixture replay remains unchanged and green through the same package-local runner.
- PASS: Phase 4 stream fixtures contain no `feedback_event` records and no exact `raw_payload` keys.
- PASS: `git diff --check`.

## Next

Phase 4 implementation is ready for code review and phase-level verification against the roadmap success criteria.
