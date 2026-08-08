---
phase: 105-arena-contract-extension
plan: 01
status: complete
requirements: [CONTRACT-01]
---

# Plan 01: Arena Event Vocabulary - Summary

## What Was Built
- Added 8 Arena lifecycle event types to `RunEventType` StrEnum (arena.workflow_started through arena.early_stop_triggered), bringing total enum members from 23 to 31
- Added 8 frozen slotted payload dataclasses to `unified_events.py` (ArenaWorkflowStartedPayload through ArenaEarlyStopTriggeredPayload) with fields matching the plan specification
- Added all 8 Arena event type strings to `EVENT_TYPE_TO_PAYLOAD_CLASS` mapping dict
- Re-exported all 8 Arena payload dataclasses from `__init__.py` and added them to `__all__`
- Extended `common.schema.json` `run_event_type` enum with all 8 Arena event type strings
- Created 8 new JSON Schema files (arena_*.schema.json) following the session_started.schema.json template: Draft 2020-12, correct $id, additionalProperties: false, event_type const, common.schema.json $ref for metadata, mode enum for mode fields, integer type for round/score, object array for findings
- Updated `test_event_schemas.py` NEW_SCHEMAS list to include all 8 Arena schema names
- Updated `test_unified_events.py`: enum count assertion to 31, added 8 Arena members to V3_MEMBERS, added 8 Arena values to V3_VALUES, added 8 round-trip test methods
- Added 8 Arena TypeScript payload interfaces to `events.ts` with ArenaMode type and extended UnifiedEventPayload union type
- Added 3 new Arena test methods to `test_event_types.py` (interface existence, ArenaMode type, union type inclusion)
- Updated contract freeze baseline (`contract_freeze_baseline.json`) with new hashes for modified files and entries for 8 new schema files

## Tasks Completed
- [x] Task 1: Add 8 Arena event types to enum, dataclasses, mapping, and JSON Schemas
- [x] Task 2: Add 8 Arena TypeScript interfaces to events.ts and extend union type

## Verification Results
- `python -m unittest discover -s packages/platform-contract/tests` — 114 tests, all OK (exit 0)
- `python -m unittest discover -s packages/platform-sdk-ts/tests` — 24 tests, all OK (exit 0)
- `python -m unittest packages.contract-test-suite.tests.test_contract_freeze` — 2 tests, all OK (exit 0)
- `python scripts/run_v2_gates.py` — all 28 gates pass; pre-existing failures in contract-test-suite (test_boundary_allowlist, test_thin_layer_boundaries, test_phase13_solution_evidence, test_bot_output_boundary) are unrelated to this plan and existed before changes

## Artifacts Produced
- `RunEventType.ARENA_WORKFLOW_STARTED` = `"arena.workflow_started"` (enum member)
- `RunEventType.ARENA_WORKFLOW_COMPLETED` = `"arena.workflow_completed"` (enum member)
- `RunEventType.ARENA_SCORE_RECORDED` = `"arena.score_recorded"` (enum member)
- `RunEventType.ARENA_REVIEW_COMPLETED` = `"arena.review_completed"` (enum member)
- `RunEventType.ARENA_SYNTHESIS_STARTED` = `"arena.synthesis_started"` (enum member)
- `RunEventType.ARENA_SYNTHESIS_COMPLETED` = `"arena.synthesis_completed"` (enum member)
- `RunEventType.ARENA_ADVERSARIAL_CHALLENGE_COMPLETED` = `"arena.adversarial_challenge_completed"` (enum member)
- `RunEventType.ARENA_EARLY_STOP_TRIGGERED` = `"arena.early_stop_triggered"` (enum member)
- `ArenaWorkflowStartedPayload` (dataclass: arena_id, mode, agent_slots, metadata)
- `ArenaWorkflowCompletedPayload` (dataclass: arena_id, mode, status, agent_slots, metadata)
- `ArenaScoreRecordedPayload` (dataclass: arena_id, agent_slot, round, score, metadata)
- `ArenaReviewCompletedPayload` (dataclass: arena_id, reviewer_slot, reviewed_slot, round, findings, metadata)
- `ArenaSynthesisStartedPayload` (dataclass: arena_id, round, source_slots, metadata)
- `ArenaSynthesisCompletedPayload` (dataclass: arena_id, round, metadata)
- `ArenaAdversarialChallengeCompletedPayload` (dataclass: arena_id, challenger_slot, challenged_slot, round, findings, metadata)
- `ArenaEarlyStopTriggeredPayload` (dataclass: arena_id, reason, round, metadata)
- 8 `arena_*.schema.json` files in `schemas/` directory
- `ArenaMode` TypeScript type in `events.ts`
- 8 Arena TypeScript payload interfaces in `events.ts`
- Extended `UnifiedEventPayload` union type in `events.ts`
- Updated `contract_freeze_baseline.json` with new hashes and 8 new schema file entries

## Notes
- The contract freeze baseline (`contract_freeze_baseline.json`) was updated to reflect the modified `__init__.py`, `enums.py`, `common.schema.json` and the 8 new `arena_*.schema.json` files. Without this update, `test_contract_freeze.py` would fail on hash mismatches and new-file detection.
- All Arena schemas are industry-neutral: no legal-specific fields in top-level `required`, `additionalProperties: false` on all, `metadata` references `common.schema.json#/$defs/metadata`. The `test_event_schemas.py` FORBIDDEN_TOP_LEVEL check validates this.
- Pre-existing failures in `contract-test-suite` (test_boundary_allowlist, test_thin_layer_boundaries re: `codex` in feature_flags.py, test_phase13_solution_evidence, test_bot_output_boundary) are unrelated to this plan and existed before any changes were made.
