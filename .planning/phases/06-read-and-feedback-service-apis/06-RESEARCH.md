---
phase: "06"
slug: read-and-feedback-service-apis
status: complete
created: 2026-06-28
requirements:
  - REQ-conversation-read-view
  - REQ-feedback-service
---

# Phase 06 Research - Read and Feedback Service APIs

## Objective

Research how to plan Phase 6 so implementation can deliver read-only operator inspection for conversations, tasks, and pending feedback from V2 contract logs without creating a new authoritative session store or queue service.

## Source Conclusions

- `docs/requirements/V2-PRD.md` sections 4.5 and 4.6 define the minimum external surface: `GET /conversations/{id}`, `GET /tasks/{id}`, and `GET /feedback?status=pending`.
- `.planning/REQUIREMENTS.md` maps this phase to `REQ-conversation-read-view` and `REQ-feedback-service`.
- `.planning/phases/06-read-and-feedback-service-apis/06-CONTEXT.md` narrows the phase to dependency-light Python handlers, contract-log-derived read models, and derived pending feedback queues.
- `AGENTS.md` forbids raw payloads, secrets, runtime databases, customer documents, new authoritative conversation storage, and automatic modification of high-risk legal skills.

## Existing Implementation Signals

### Contract event streams

- `packages/contract-test-suite/src/contract_test_suite/event_stream_replay.py` already loads JSONL envelopes into `EventStreamRecord` values with `event_key`, `occurred_at`, `ingested_at`, `seq`, and nested `event`.
- `load_event_stream` schema-validates each nested event against platform schemas and rejects extra envelope fields.
- `assert_event_stream_integrity` checks core AgentTurn, RouteDecision, ExecutionTrace, and AgentResult relationships. It does not yet provide read-model response shapes.
- `services/hermes-contract-layer/src/hermes_contract_layer/writer.py` provides the append-only envelope shape via `ContractLogRecord`.

### Platform event shape

- `AgentTurn` owns `turn_id`, `conversation_id`, `channel`, `user_id`, `message_type`, `received_at`, content references, attachments, and metadata.
- `RouteDecision` is related by `turn_id` and owns route mode, primary skill, confidence, and `route_decision_id`.
- `ExecutionTrace` is related by `turn_id`, owns `trace_id`, envelope-like `occurred_at`, `ingested_at`, `seq`, steps, tool calls, artifacts, errors, and route references.
- `AgentResult` is related by `turn_id`, owns `result_id`, status, reply type, artifacts, `feedback_target`, route mismatch, skill candidate, and `metadata.trace_id` / `metadata.route_decision_id`.
- `FeedbackEvent` is related by `turn_id`, `conversation_id`, optional `result_id`, and optional `feedback_target`.

### Feedback normalization

- `services/feedback-service/src/feedback_service/wecom_normalizer.py` already converts sanitized Hermes compatibility `feedback.jsonl` plus `pending_previews.jsonl` into schema-valid `FeedbackEvent` dictionaries.
- Existing dedupe key is `feedback_target + action + user_id + created_at_bucket`; this matches Phase 6 D-11 for compatibility inputs.
- Existing route-mismatch handling sets `route_mismatch`, `skill_candidate.requires_human_review`, and `metadata.no_auto_modify`.
- `services/wecom-service/src/wecom_service/normalization.py` already normalizes InkStatute WeCom feedback callbacks directly into `FeedbackEvent` dictionaries for Phase 5.5 tests.

### Package and test pattern

- Existing services use Python src-layout packages with `dependencies = []`.
- Tests use stdlib `unittest` and explicit `PYTHONPATH`.
- Cross-service tests in `packages/contract-test-suite/tests/test_phase5_wecom_loop.py` add service `src` directories to `sys.path`.
- Fixtures are synthetic and reference-first using `fixture://` and `raw_payload_ref`.

## Implementation Strategy

### Read model

Create `services/conversation-read-view/` as a dependency-light package.

The core should accept either `EventStreamRecord` instances or equivalent envelope dictionaries. It should:

- Sort records for view assembly by `(occurred_at, ingested_at, seq)` so out-of-order input lists still produce deterministic views.
- Index by `conversation_id`, task id, and `trace_id`.
- Treat `event.metadata.task_id` as the preferred task id when present and `turn_id` as the canonical fallback.
- Build read-only dictionaries for operator inspection; do not define new platform schemas.
- Preserve missing facts as `source_status`, `missing_associations`, and `fallback_source` metadata rather than fabricating values.
- Reject or omit exact `raw_payload` keys recursively while preserving `raw_payload_ref`.

### Feedback queue

Extend `services/feedback-service/` rather than replacing it.

The service-local library should:

- Reuse `normalize_wecom_feedback_records` for compatibility Hermes feedback/previews.
- Accept InkStatute WeCom callback-normalized `FeedbackEvent` dictionaries and contract-log `FeedbackEvent` records as primary inputs.
- Normalize classification using existing `event_type`, `action`, labels, messages, and metadata.
- Cover `rating`, `correction`, `fact_missing`, `citation_error`, `route_mismatch`, `format_issue`, `compliance_issue`, and `skill_candidate`.
- Produce pending queue item dictionaries that include associations, source references, duplicate count/idempotency metadata, skill-candidate evidence, and `no_auto_modify` for route mismatch.
- Keep the queue derived and rebuildable from events, not a durable queue service.

### API layer

Implement pure route handlers first:

- `handle_get(path, query, read_model, feedback_queue=None) -> tuple[int, dict]`
- `GET /conversations/{id}` returns a conversation summary plus recent turns/results/feedback associations.
- `GET /tasks/{id}` returns task/turn status, route, trace, result, artifacts, errors, feedback, and lookup aliases.
- `GET /feedback?status=pending` returns pending human-review feedback queue items.

No HTTP server is required for Phase 6 unless implementation discovers a concrete need. Unit tests can call handlers directly.

## Risks and Mitigations

- Privacy leakage: recursively reject exact `raw_payload` keys in log and feedback readers, preserve only `raw_payload_ref`, and test secret-like patterns in fixtures.
- Authority drift: do not add a database, queue worker, or Hermes session dependency. Any cache/index must be named derived and rebuildable.
- Broken relationships: use existing contract-test-suite validators for fixtures and add read-view tests for missing association reporting.
- Route-mismatch safety: queue output must set human-review-only metadata and must not import or invoke `skillopt-runner`.
- Out-of-order logs: read model sorting must tolerate shuffled records, while canonical fixtures used by `assert_event_stream_integrity` can remain seq-monotonic.

## Validation Architecture

Phase 6 should use automated stdlib `unittest` coverage at three layers:

- Service unit tests for `services/conversation-read-view/tests`.
- Service unit tests for `services/feedback-service/tests`.
- Cross-service contract tests in `packages/contract-test-suite/tests` using synthetic Phase 6 fixtures.

Recommended commands:

- Read-view quick check: `PYTHONPATH=services/conversation-read-view/src:packages/contract-test-suite/src python -m unittest discover services/conversation-read-view/tests`
- Feedback quick check: `PYTHONPATH=services/feedback-service/src:services/wecom-service/src:packages/contract-test-suite/src python -m unittest discover services/feedback-service/tests`
- Contract integration check: `PYTHONPATH=packages/contract-test-suite/src:services/conversation-read-view/src:services/feedback-service/src:services/wecom-service/src python -m unittest discover packages/contract-test-suite/tests`
- Compile check: `python -m compileall services/conversation-read-view/src services/feedback-service/src packages/contract-test-suite/src`

Each plan must include a `<threat_model>` block because security enforcement defaults to enabled. Automated tests should cover privacy/reference-only output, no durable authority, pending human-review route mismatch behavior, and stable dedupe.

## Research Complete

This research is sufficient to plan Phase 6 without external web lookup or new dependencies.

