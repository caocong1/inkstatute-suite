---
phase: 04-hermes-shadow-event-layer
plan: 02
subsystem: hermes-contract-layer
tags: [mapper, writer, jsonl, schema-validation, privacy]

requires:
  - phase: 04-01
    provides: Safe after-filter hook artifact and no-mutation entrypoint
provides:
  - Deterministic contract event ID helper
  - Mapper from Hermes `agent:end` context to AgentTurn, RouteDecision, ExecutionTrace, and AgentResult
  - Append-only JSONL writer with envelope timestamps and monotonic sequence
  - Hook integration that writes four event records when configured
affects: [phase-04-plan-03, phase-05-wecom-shadow-loop-validation, phase-06-read-and-feedback-service-apis]

tech-stack:
  added: []
  patterns:
    - Plain dictionary payloads validated through the existing contract-test-suite schema validator
    - JSONL envelopes keep log clocks and sequence outside nested event payloads
    - Reference-first payload metadata through `raw_payload_ref`

key-files:
  created:
    - services/hermes-contract-layer/src/hermes_contract_layer/ids.py
    - services/hermes-contract-layer/src/hermes_contract_layer/mapper.py
    - services/hermes-contract-layer/src/hermes_contract_layer/writer.py
    - services/hermes-contract-layer/tests/test_mapper.py
    - services/hermes-contract-layer/tests/test_writer.py
    - .planning/phases/04-hermes-shadow-event-layer/04-02-SUMMARY.md
  modified:
    - services/hermes-contract-layer/src/hermes_contract_layer/hook.py
    - services/hermes-contract-layer/tests/test_hook.py
    - .planning/ROADMAP.md
    - .planning/STATE.md
    - .planning/phases/04-hermes-shadow-event-layer/04-VALIDATION.md

key-decisions:
  - "Map Phase 4 hook context to exactly four events: AgentTurn, RouteDecision, ExecutionTrace, and AgentResult; FeedbackEvent remains deferred."
  - "Use `session_id` as `conversation_id`, `message_id` as `feedback_target` only when present, and metadata to mark missing source fields."
  - "Failed results use `status_update` reply type and exact async states only when source context exposes valid platform states."
  - "JSONL envelope fields are `event_key`, `occurred_at`, `ingested_at`, `seq`, and `event`; nested payloads remain schema-valid."

patterns-established:
  - "Mapper tests validate every emitted payload with `validate_event`."
  - "Writer tests read JSONL back from a temporary path and validate nested payloads."
  - "Hook tests prove configured recording writes four records without changing outbound context keys."

requirements-completed:
  - REQ-hermes-contract-layer
  - REQ-observability-and-replay

duration: 9min
completed: 2026-06-28
---

# Phase 04 Plan 02: Mapper and JSONL Writer Summary

Phase 4 can now convert post-filter Hermes hook context into schema-valid platform event payloads and append them to a local JSONL contract log when configured.

## Accomplishments

- Added `stable_hash_id` for deterministic testable event IDs.
- Added `map_agent_end_context`, which emits `agent_turn`, `route_decision`, `execution_trace`, and `agent_result` payloads with relationship-linked IDs.
- Added reference-first metadata for missing/capped fields, including `content_truncated`, `response_truncated`, `source_status`, `route_source`, `raw_payload_ref`, and unavailable message/feedback sources.
- Added `ContractEventWriter` and `ContractLogRecord` for append-only JSONL envelopes with monotonic in-memory `seq`.
- Integrated mapper/writer behavior into `record_contract_result`; missing log path still returns skipped, and configured paths write four records.

## Verification

- PASS: `PYTHONPATH=services/hermes-contract-layer/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/hermes-contract-layer/tests -v` ran 18 tests successfully.
- PASS: `python -m compileall services/hermes-contract-layer/src services/hermes-contract-layer/tests`.
- PASS: Full Phase 4 verification command ran `compileall`, the contract-test-suite runner with 28 tests, and all 18 service tests successfully.
- PASS: `git diff --check`.
- PASS: No database, queue, daemon, network call, `.github` workflow, feedback normalization, read API, or live Hermes deployment was added.

## Next

Plan 04-03 can add contract-test-suite event-stream replay support and committed JSONL fixtures generated from the Phase 4 envelope shape.
