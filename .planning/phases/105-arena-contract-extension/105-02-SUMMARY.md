---
phase: 105-arena-contract-extension
plan: 02
status: complete
requirements: [CONTRACT-02]
---

# Plan 02: Arena Dataclasses - Summary

## What Was Built
- Created `arena_contract.py` module with 4 frozen slotted dataclasses: `ArenaWorkflowConfig`, `ArenaHandle`, `ArenaStatus`, `ArenaUserAction`
- Re-exported all 4 Arena dataclasses from `platform_contract.__init__`
- Created 4 JSON Schema files (`arena_workflow_config`, `arena_handle`, `arena_status`, `arena_user_action`) with `additionalProperties: false`, correct `$id`, and `common.schema.json` references
- Added 4 Arena contract TypeScript interfaces to `events.ts` with field signatures matching the Python dataclasses
- Added `test_contains_arena_contract_interfaces` test to `test_event_types.py`
- Created `test_arena_contract.py` with 3 test classes (17 tests total) proving cross-language round-trip losslessness

## Tasks Completed
- [x] Task 1: Define 4 Arena dataclasses in arena_contract.py with JSON Schemas and TS interfaces
- [x] Task 2: Cross-language round-trip test (Python → JSON → TS-shape → JSON → Python lossless)

## Verification Results
- `python -m unittest discover -s packages/platform-contract/tests` — 131 tests, exit 0
- `python -m unittest discover -s packages/platform-sdk-ts/tests` — 25 tests, exit 0
- `python -m unittest packages/platform-contract/tests/test_arena_contract.py` — 17 tests, exit 0
  - 4 ArenaDataclassRoundTripTests (Config/Handle/Status/UserAction round-trips with schema validation)
  - 5 CrossLanguageShapeConformanceTests (4 dataclass + 1 payload TS field-name matching)
  - 8 ArenaEventPayloadRoundTripTests (all 8 Arena event payloads with schema validation)

## Artifacts Produced
- `ArenaWorkflowConfig` (dataclass in `arena_contract.py`: arena_id, mode, agent_slots, task_instruction, reference_dir, max_rounds, metadata)
- `ArenaHandle` (dataclass in `arena_contract.py`: arena_id, status, created_at, metadata)
- `ArenaStatus` (dataclass in `arena_contract.py`: arena_id, mode, status, agent_slots, current_round, metadata)
- `ArenaUserAction` (dataclass in `arena_contract.py`: arena_id, action, selected_slot, metadata)
- `arena_workflow_config.schema.json` (new schema file)
- `arena_handle.schema.json` (new schema file)
- `arena_status.schema.json` (new schema file)
- `arena_user_action.schema.json` (new schema file)
- 4 Arena contract TypeScript interfaces (ArenaWorkflowConfig, ArenaHandle, ArenaStatus, ArenaUserAction in `events.ts`)
- `test_arena_contract.py` (new test file: ArenaDataclassRoundTripTests, CrossLanguageShapeConformanceTests, ArenaEventPayloadRoundTripTests)

## Notes
- The 4 Arena dataclass schemas follow the `run.schema.json` template (non-event-payload dataclasses) — no `event_type` const field, unlike the 8 Arena event payload schemas from Plan 105-01.
- The `mode` field uses enum `["standard", "self_score", "arena_review", "adversarial"]` and `action` uses enum `["stop", "pause", "cancel", "select_result"]` in both JSON Schemas and TS interfaces.
- Cross-language round-trip tests strip `None` values from the JSON intermediate dict to match TypeScript optional `?` semantics (optional fields absent rather than `null`).
- The `_dict_to_dataclass` helper from `unified_events.py` is reused for Arena dataclass re-instantiation — it handles unknown keys and passes through primitives correctly.
- Arena event payload round-trip tests add the `event_type` const field before schema validation (payload dataclasses don't carry it), then strip it before deserialization.
- Plan 105-01's work in `__init__.py`, `events.ts`, and `test_event_types.py` was preserved — only additive changes were made.
