---
phase: "06"
slug: read-and-feedback-service-apis
status: complete
created: 2026-06-28
---

# Phase 06 Pattern Map

## Package Scaffolding Pattern

Closest analogs:

- `services/feedback-service/pyproject.toml`
- `services/wecom-service/pyproject.toml`
- `services/feedback-service/src/feedback_service/__init__.py`
- `services/wecom-service/src/wecom_service/__init__.py`

Pattern to follow:

- Python `src` layout.
- `requires-python = ">=3.11"`.
- `dependencies = []`.
- Package exports are explicit through `__all__`.
- Tests use `python -m unittest discover ...` with `PYTHONPATH` instead of a runtime framework.

Phase 6 application:

- Add `services/conversation-read-view/pyproject.toml`.
- Add `services/conversation-read-view/src/conversation_read_view/`.
- Add direct unit tests under `services/conversation-read-view/tests/`.

## Contract Log Loading Pattern

Closest analogs:

- `packages/contract-test-suite/src/contract_test_suite/event_stream_replay.py`
- `services/hermes-contract-layer/src/hermes_contract_layer/writer.py`

Pattern to follow:

- Treat event envelopes as dictionaries with exactly `event_key`, `occurred_at`, `ingested_at`, `seq`, and `event`.
- Let `load_event_stream` perform schema validation for JSONL fixtures.
- Use dataclasses for typed internal values when they make tests and indexing clearer.

Phase 6 application:

- Accept `EventStreamRecord` values and envelope dictionaries.
- Create derived indexes in memory from contract events.
- Sort view assembly by `occurred_at`, then `ingested_at`, then `seq`.
- Preserve raw event payloads only after privacy scrubbing.

## Read-Only Response Pattern

Closest analogs:

- `services/wecom-service/src/wecom_service/normalization.py`
- `services/wecom-service/src/wecom_service/sender.py`

Pattern to follow:

- Return plain dictionaries.
- Keep metadata explicit with source-status and audit/status fields.
- Do not start servers or require framework objects for tests.

Phase 6 application:

- Add pure `handle_get(path, query, read_model, feedback_queue=None) -> tuple[int, dict]`.
- Return 200 with dictionaries for known records, 404 with structured error dictionaries for missing records, and 400 for unsupported feedback status values.

## Feedback Normalization Pattern

Closest analogs:

- `services/feedback-service/src/feedback_service/wecom_normalizer.py`
- `services/feedback-service/tests/test_wecom_normalizer.py`
- `services/wecom-service/src/wecom_service/normalization.py`

Pattern to follow:

- Keep feedback output schema-valid as `FeedbackEvent`.
- Group repeated callbacks by stable idempotency key.
- Preserve `raw_payload_ref` and reject exact `raw_payload`.
- Route mismatch feedback must include `skill_candidate.requires_human_review = true` and `metadata.no_auto_modify = true`.

Phase 6 application:

- Add feedback classification helpers instead of changing the platform schema.
- Add derived pending queue item dictionaries for operator review.
- Keep Hermes compatibility inputs as migration/reference inputs only.

## Cross-Service Test Pattern

Closest analogs:

- `packages/contract-test-suite/tests/test_phase5_wecom_loop.py`
- `packages/contract-test-suite/tests/test_event_stream_replay.py`
- `packages/contract-test-suite/fixtures/phase5_wecom_contract_stream.jsonl`
- `packages/contract-test-suite/fixtures/phase55_wecom_service_agent_loop.json`

Pattern to follow:

- Use synthetic fixtures.
- Add service `src` paths to `sys.path` in contract-test-suite integration tests.
- Validate schema and relationships with existing helpers when the fixture shape fits.
- Add service-specific assertions for view shape, routing, sorting, and privacy.

Phase 6 application:

- Add a Phase 6 contract fixture for read/feedback integration.
- Add contract-test-suite tests that import the new read-view and feedback queue helpers.
- Keep out-of-order tolerance as a read-model test using shuffled records; keep canonical replay fixtures seq-monotonic for existing replay helpers.

