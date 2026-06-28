# Phase 6: Read and Feedback Service APIs - Context

**Gathered:** 2026-06-28T07:12:00Z
**Status:** Ready for planning
**Source:** `$gsd-progress --next --auto` / `$gsd-discuss-phase 6 --auto`

<domain>
## Phase Boundary

Phase 6 delivers the minimum read-only operator API surface and feedback review queue needed after Phase 5.5: operators can inspect conversations, tasks, and pending feedback from V2 contract logs without creating a new authoritative conversation/session database.

This phase may add `services/conversation-read-view/`, extend `services/feedback-service/`, add contract-log read-model helpers, dependency-light GET route handlers, fixtures, and contract-test-suite coverage. It must not create an independent authoritative conversation database, rebuild Hermes sessions, mutate Hermes runtime data, own ordinary WeCom send/receive, introduce queues/databases unless explicitly justified by the plan, or auto-modify legal skills.

</domain>

<decisions>
## Implementation Decisions

### Read Model Source and Authority

- **D-01:** Contract event logs are the primary source for Phase 6 read views. Read models derive from `AgentTurn`, `RouteDecision`, `ExecutionTrace`, `AgentResult`, and `FeedbackEvent` envelopes.
- **D-02:** Do not create an authoritative conversation/session store. If a local cache or index is useful for tests or request handling, it must be rebuilt from contract logs and clearly marked derived.
- **D-03:** Hermes `sessions.db` may appear only behind an explicit Hermes-specific fallback adapter, and only to fill gaps where contract logs do not contain enough data. It must never become the authority or a required dependency for the minimum API.
- **D-04:** Read models must preserve missing or partial source facts honestly with metadata/source-status fields instead of fabricating content, timestamps, task state, or feedback associations.

### Minimum API Surface

- **D-05:** Implement a dependency-light API layer with pure handler/router functions first. Tests should be able to call handlers directly without starting a server. A stdlib HTTP wrapper is allowed only if needed to satisfy the "GET" surface ergonomically.
- **D-06:** The minimum route set is exactly:
  - `GET /conversations/{id}` for conversation summary and recent turns/results.
  - `GET /tasks/{id}` for task/turn status, route, trace, result, artifacts, and errors.
  - `GET /feedback?status=pending` for pending human-review feedback queues.
- **D-07:** Lookup keys must include `conversation_id`, task id, and `trace_id`. Because the platform contract has `turn_id` but no top-level `task_id`, Phase 6 should treat `metadata.task_id` as preferred when present and `turn_id` as the canonical task-id fallback. Do not add a new top-level platform schema field for this phase.
- **D-08:** API responses are read-only dictionaries shaped for operator inspection, not new platform contract events. They may include view-specific fields, but nested contract payloads must remain schema-valid when included.

### Feedback Service and Queue Behavior

- **D-09:** Extend `services/feedback-service/` from the Phase 5 fixture normalizer into a service-local normalization/dedupe/classification library. Reuse existing `normalize_wecom_feedback_records` behavior where possible instead of replacing it.
- **D-10:** Feedback inputs are, in priority order: InkStatute WeCom feedback callback records, contract-log `FeedbackEvent` records, and Hermes `feedback.jsonl`/`pending_previews.jsonl` compatibility records. Hermes files are migration inputs only.
- **D-11:** Dedupe repeated button clicks, WeCom/network retries, and repeated Hermes shim writes using a stable idempotency key. Existing strategy `feedback_target + action + user_id + created_at_bucket` is acceptable for compatibility input; InkStatute callback input may use callback/message ids when available.
- **D-12:** Classification should cover PRD categories: `rating`, `correction`, `fact_missing`, `citation_error`, `route_mismatch`, `format_issue`, `compliance_issue`, and `skill_candidate`. Start rule-based and metadata-driven; do not add an AI classifier unless a plan explicitly justifies it.
- **D-13:** `route_mismatch` feedback must produce pending human-review queue items with `skill_candidate` evidence and `no_auto_modify` metadata. Do not invoke `skillopt-runner` or any automatic legal skill modification.
- **D-14:** Pending queues are derived views over feedback events. They may be exported as JSON/dicts for operators, but this phase does not introduce a durable queue service unless the plan proves it is necessary and still derived from logs.

### Privacy and Ordering

- **D-15:** All contract-log and feedback readers must reject or ignore exact/raw payload fields and prefer `raw_payload_ref`. API responses must not expose callback bodies, runtime DB paths, customer documents, media bytes, secrets, tokens, or raw legal payloads.
- **D-16:** Contract log replay must tolerate out-of-order records by using envelope `occurred_at`, `ingested_at`, and `seq`. Tests should include at least one out-of-order or mixed conversation fixture if the read model sorts or groups records.
- **D-17:** Relationship integrity matters more than completeness. A response with missing optional associations should be explicit and testable; a broken association between result and feedback should fail fixture validation.

### Testing and Acceptance

- **D-18:** Keep Phase 6 dependency-free or dependency-light like prior packages. Use stdlib `unittest`, `json`, `pathlib`, and explicit `PYTHONPATH` commands.
- **D-19:** Add fixtures/tests proving the three GET surfaces, lookup by `conversation_id`/task id/`trace_id`, pending feedback filtering, dedupe, classification, route-mismatch human review, and privacy/reference-only output.
- **D-20:** Contract-test-suite should validate Phase 6 fixtures through existing schema/event-stream helpers where possible. Add focused read-view tests only for view-specific response shape and API behavior.

### the agent's Discretion

- The planner may choose exact module names inside `services/conversation-read-view/` and `services/feedback-service/`, provided the boundary remains dependency-light and read-only.
- The planner may split Phase 6 into separate plans for read model, API routing, feedback normalization/queue, and fixture integration.
- The planner may defer live/operator HTTP serving behind pure handler tests if no runtime server requirement or deployment environment exists.
- The planner may add small helper types/dataclasses for read models and feedback queue items, as long as they do not become new platform contract schemas unless explicitly planned.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product and Scope

- `AGENTS.md` - V2 source-of-truth rules, phase priority order, privacy, Hermes boundary, and no authoritative conversation database rule.
- `docs/requirements/V2-PRD.md` - Active V2 PRD, especially sections 4.5, 4.6, 6.3, 6.4, 10.2, 10.3, 12.1, and 13.
- `.planning/PROJECT.md` - Current project constraints and out-of-scope list.
- `.planning/REQUIREMENTS.md` - `REQ-conversation-read-view`, `REQ-feedback-service`, privacy baseline, and V2 development order.
- `.planning/ROADMAP.md` - Phase 6 goal, dependencies, and success criteria.
- `.planning/STATE.md` - Current blockers and accumulated decisions.

### Upstream Phase Evidence

- `.planning/phases/05.5-inkstatute-wecom-service-and-hermes-agent-adapter/05.5-CONTEXT.md` - InkStatute WeCom service, adapter, no-channel-io, output-boundary, and live-blocked decisions.
- `.planning/phases/05.5-inkstatute-wecom-service-and-hermes-agent-adapter/05.5-VERIFICATION.md` - Phase 5.5 automated verification and live WeCom follow-up boundary.
- `.planning/phases/05.5-inkstatute-wecom-service-and-hermes-agent-adapter/05.5-WECOM-LIVE-ACCEPTANCE.md` - Live-vs-fixture evidence split and blocked live acceptance checklist.
- `.planning/phases/05-wecom-shadow-loop-validation/05-CONTEXT.md` - Phase 5 feedback normalization and fixture/live separation.
- `.planning/phases/04-hermes-shadow-event-layer/04-CONTEXT.md` - Contract log writer, mapper, event-stream replay, privacy, and no-outbound-mutation decisions.

### Existing Code and Fixtures

- `packages/platform-contract/src/platform_contract/events.py` - Python event binding shapes.
- `packages/platform-contract/src/platform_contract/schemas/` - JSON Schema source of truth for event payloads.
- `packages/contract-test-suite/src/contract_test_suite/event_stream_replay.py` - Contract event-stream envelope loader, schema validation, and relationship checks.
- `packages/contract-test-suite/src/contract_test_suite/fixture_replay.py` - Full bundle relationship replay.
- `packages/contract-test-suite/fixtures/phase5_wecom_contract_stream.jsonl` - Existing contract log stream fixture.
- `packages/contract-test-suite/fixtures/phase5_wecom_feedback_loop_fixture.json` - Existing result-to-feedback bundle fixture.
- `packages/contract-test-suite/fixtures/phase5_wecom_feedback_sample.jsonl` - Sanitized compatibility feedback input.
- `packages/contract-test-suite/fixtures/phase5_wecom_pending_previews_sample.jsonl` - Sanitized pending preview compatibility input.
- `packages/contract-test-suite/fixtures/phase55_wecom_service_agent_loop.json` - Phase 5.5 service/adapter/output-policy/feedback fixture.
- `services/feedback-service/src/feedback_service/wecom_normalizer.py` - Existing minimal feedback normalizer, dedupe behavior, route-mismatch skill-candidate safety, and privacy issue handling.
- `services/feedback-service/tests/test_wecom_normalizer.py` - Current feedback-service tests and expected behavior.
- `services/hermes-contract-layer/src/hermes_contract_layer/writer.py` - Contract log envelope writer shape.
- `services/hermes-contract-layer/src/hermes_contract_layer/mapper.py` - Hermes event mapping, `feedback_target` source, and source-status metadata.
- `services/wecom-service/src/wecom_service/normalization.py` - InkStatute WeCom callback-to-contract normalization.
- `services/wecom-service/src/wecom_service/sender.py` - Template-card feedback target send envelope helper.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `contract_test_suite.event_stream_replay.load_event_stream` already parses JSONL envelopes with `event_key`, `occurred_at`, `ingested_at`, `seq`, and `event`.
- `contract_test_suite.event_stream_replay.assert_event_stream_integrity` already enforces turn/route/trace/result relationships and artifact references for stream fixtures.
- `contract_test_suite.fixture_replay.assert_relationship_integrity` already checks complete bundles, including feedback-to-result and feedback-to-route relationships.
- `feedback_service.wecom_normalizer.normalize_wecom_feedback_records` already normalizes sanitized compatibility feedback and preview records into schema-valid `FeedbackEvent` dictionaries.
- `wecom_service.normalization.normalize_wecom_feedback_callback` already handles InkStatute WeCom card/button feedback callbacks for direct callback inputs.
- `hermes_contract_layer.writer.ContractLogRecord` documents the event envelope that read-view ingestion should consume.

### Established Patterns

- Services are currently small Python src-layout packages with `dependencies = []`.
- Tests are stdlib `unittest` with explicit `PYTHONPATH`; no web framework is established.
- Fixtures are synthetic/reference-first and should use `fixture://`, `raw_payload_ref`, or derived metadata instead of raw customer payloads.
- Live evidence and fixture evidence are separate. Phase 6 may build operator views over fixture/live logs, but it must not turn fixture data into live acceptance claims.

### Integration Points

- New read-view package: `services/conversation-read-view/`.
- Existing feedback package to extend: `services/feedback-service/`.
- Primary input format: contract JSONL event envelopes written by `services/hermes-contract-layer`.
- Primary feedback callback input: InkStatute WeCom service normalized callback records.
- Compatibility feedback inputs: sanitized `feedback.jsonl` and `pending_previews.jsonl` records.
- Contract-test-suite is the right place for cross-service fixture replay and relationship checks.

</code_context>

<specifics>
## Specific Ideas

- Prefer read model names like `ConversationView`, `TaskView`, `FeedbackQueueItem`, and `ContractLogReadModel` if dataclasses help tests.
- Prefer pure route handling such as `handle_get(path, query, read_model)` returning `(status, body)` over a live server dependency.
- Prefer explicit response metadata: `source_status`, `derived_from_contract_log`, `fallback_source`, `missing_associations`, and `privacy`.
- Prefer task lookup order: `metadata.task_id`, then `turn_id`, then trace/result association.
- Prefer pending feedback sorting by `created_at`, then envelope `seq`, with stable deterministic output in tests.

</specifics>

<deferred>
## Deferred Ideas

- `.github` CI wiring, coverage thresholds, broad composability gates, and privacy gates remain Phase 7.
- Five-workday lawyer trial metrics and acceptance reporting remain Phase 8.
- Admin console UI, web dashboards, and full operator console are out of Phase 6 unless a later phase adds them.
- Durable queue service, database-backed materialized views, and production deployment topology are out of scope unless a Phase 6 plan explicitly narrows and justifies them.
- Automatic legal skill synthesis or modification remains out of V2 scope.

</deferred>

---

*Phase: 6-Read and Feedback Service APIs*
*Context gathered: 2026-06-28T07:12:00Z*
