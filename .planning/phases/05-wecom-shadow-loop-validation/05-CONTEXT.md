# Phase 5: WeCom Shadow Loop Validation - Context

**Gathered:** 2026-06-28T03:05:00Z
**Status:** Ready for planning
**Source:** `$gsd-progress --next --auto` / `$gsd-discuss-phase 5 --auto`

<domain>
## Phase Boundary

Phase 5 proves the existing Hermes lawfirm WeCom loop still works while V2 shadow records result and feedback evidence into standard contract events. It validates the path from lawyer WeCom task, gateway acknowledgment, Hermes execution, post-filter `contract_result_recorder` logging, existing text/file/card delivery, template-card callback capture, and FeedbackEvent-normalizable feedback.

This phase may add validation fixtures, replay support, runbooks, opt-in deployment/validation helpers, and minimal reference-first feedback normalization needed to prove the WeCom loop. It must not rebuild Hermes core, WeCom gateway, router, skill registry, MCP registry, model gateway, session storage, feedback card/shim channel, read-view APIs, databases, queues, or automatic legal skill modification.

</domain>

<decisions>
## Implementation Decisions

### WeCom Loop Validation Boundary

- **D-01:** Treat WeCom as the only V2 acceptance channel for this phase. QQ Bot and WeChat may receive lightweight non-regression checks only; they are not Phase 5 acceptance channels.
- **D-02:** Preserve the existing Hermes channel path: gateway ACK, Hermes lawfirm execution, `response_filter`, template card dispatch, and `wecom_template_card_shim` remain owned by Hermes. Phase 5 validates and observes them instead of replacing them.
- **D-03:** Use the Phase 4 hook artifact as the result-recording path. Deployment into a live Hermes profile must be explicit and reversible, preferably documented or guarded by an opt-in validation helper; repo tests must not mutate `/home/sorawatcher/.hermes`.
- **D-04:** Do not fake live WeCom acceptance. If live Hermes/WeCom credentials, channel state, or sanitized task access are unavailable, plans must produce fixture-backed validation plus a clearly recorded live-validation blocker.

### Evidence and Scenario Coverage

- **D-05:** Phase 5 evidence should cover the PRD sample journeys where feasible: contract review long task with artifact/card feedback, legal retrieval short task with citations/card feedback, and route-mismatch or unknown-task feedback with human-reviewed `skill_candidate` evidence.
- **D-06:** Every validation run must check that lawyer-facing text, files, template cards, gateway behavior, router behavior, skills, MCP behavior, and model configuration are not changed by the shadow recorder.
- **D-07:** Contract log replay remains reference-first. Event streams should validate `AgentTurn`, `RouteDecision`, `ExecutionTrace`, and `AgentResult` from the hook, then connect feedback evidence when available without inventing missing callbacks.
- **D-08:** WeCom timeout evidence should record acknowledgment timing as sanitized timestamps/status references. Exact platform async states may be recorded only when Hermes exposes exact `queued`, `running`, `waiting_for_user`, `succeeded`, `failed`, or `cancelled` signals.

### Feedback Association and Normalization

- **D-09:** Phase 5 must prove or explicitly block on the `message_id` / `feedback_target` chain from `response_filter` through template card callback and `feedback.jsonl`. `AgentResult.feedback_target` should remain `message_id` only when this chain is source-confirmed for the run.
- **D-10:** Implement only the minimum feedback normalization needed for WeCom loop validation: sanitized `feedback.jsonl` plus `pending_previews.jsonl` examples may be converted into schema-valid `FeedbackEvent` records for fixture replay and relationship checks.
- **D-11:** Full `feedback-service` API behavior, pending queue exports, broad classification workflow, and production dedupe service surface remain Phase 6. Phase 5 can define or test an idempotency rule if repeated callbacks are part of the validation evidence.
- **D-12:** Route-mismatch feedback and `skill_candidate` records must always carry `requires_human_review=true` and `no_auto_modify` metadata. Phase 5 must not call `skillopt-runner` or modify legal conclusion skills.

### Privacy and Operational Safety

- **D-13:** Validation artifacts must use `raw_payload_ref`, synthetic fixtures, or sanitized references. Do not commit runtime logs, callback bodies, customer legal text, documents, tokens, databases, or plaintext secrets.
- **D-14:** Contract logs and validation fixtures must avoid complete ID numbers, phone numbers, bank accounts, addresses, and raw legal payloads by default.
- **D-15:** Recorder failures must remain non-blocking for Hermes outbound behavior. Phase 5 should reuse and extend the Phase 4 safety expectation that hook errors are swallowed and outbound context keys are restored.

### the agent's Discretion

- The planner may choose whether Phase 5 uses a repo-local validation script, contract-test-suite fixture replay additions, a runbook document, or a small feedback-normalization module, provided the result proves the WeCom loop and preserves the Phase 5/Phase 6 boundary.
- The planner may choose exact fixture names and evidence document names. Prefer names that make the live-vs-fixture distinction obvious.
- The planner may defer live WeCom verification behind a documented blocker if runtime access is unavailable; it must not claim live success from synthetic data.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product and Scope

- `AGENTS.md` - V2 source-of-truth rules, thin Hermes boundary, implementation priorities, privacy rules, and GSD continuation protocol.
- `docs/requirements/V2-PRD.md` - Active V2 PRD, especially sections 3.7, 3.8, 4.0, 4.4, 4.6, 4.7, 6.3, 10.3, 10.4, 12.1, and 13.
- `.planning/ROADMAP.md` - Phase 5 goal, success criteria, dependencies, and Phase 6/7/8 boundaries.
- `.planning/REQUIREMENTS.md` - `REQ-wecom-daily-test-loop`, `REQ-feedback-service`, `REQ-security-privacy-baseline`, and thin-layer constraints.
- `.planning/STATE.md` - Current decisions, blockers, and Phase 4 completion status.

### Upstream Phase Decisions

- `.planning/phases/04-hermes-shadow-event-layer/04-CONTEXT.md` - Phase 4 hook, mapper, writer, replay, privacy, and no-outbound-mutation decisions.
- `.planning/phases/04-hermes-shadow-event-layer/04-VERIFICATION.md` - Phase 4 verification status and any downstream gates.
- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HOOK-ORDER-EVIDENCE.md` - Source-confirmed hook ordering and after-filter directory rule.
- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HOOK-AND-TURN-DECISIONS.md` - AgentTurn inference limits, response cap, and hook context rules.
- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-IDENTIFIER-STATE-PRIVACY-RULES.md` - Feedback target, idempotency, async state, raw payload, redaction, and legal-safety rules.

### Existing Code and Contract Surface

- `services/hermes-contract-layer/README.md` - Hook artifact shape, runtime boundary, and no live deployment in repo tests.
- `services/hermes-contract-layer/src/hermes_contract_layer/hook.py` - `INKSTATUTE_CONTRACT_LOG_PATH`, safe hook entrypoint, context restoration, and writer invocation.
- `services/hermes-contract-layer/src/hermes_contract_layer/mapper.py` - AgentTurn/RouteDecision/ExecutionTrace/AgentResult mapping, `message_id` feedback target behavior, privacy filtering, and skill candidate safety metadata.
- `services/hermes-contract-layer/src/hermes_contract_layer/writer.py` - Append-only JSONL envelope shape.
- `services/hermes-contract-layer/tests/test_hook.py` - No-outbound-mutation and hook-recording safety tests.
- `services/hermes-contract-layer/tests/test_mapper.py` - Mapper relationship, privacy, async state, and feedback-target tests.
- `packages/contract-test-suite/src/contract_test_suite/event_stream_replay.py` - Existing event-stream replay and relationship checks for partial Phase 4 streams.
- `packages/contract-test-suite/tests/test_event_stream_replay.py` - Current Phase 4 stream replay examples and no-feedback-fabrication expectation.
- `packages/platform-contract/src/platform_contract/events.py` - Python bindings for `AgentResult` and `FeedbackEvent`.
- `packages/platform-contract/src/platform_contract/enums.py` - Allowed channel, message type, async state, feedback source/type/action/status, and route mode values.
- `packages/platform-contract/src/platform_contract/schemas/feedback_event.schema.json` - FeedbackEvent JSON Schema target for Phase 5 normalization evidence.
- `packages/platform-contract/fixtures/legal_wecom_contract_review.json` - Synthetic WeCom legal feedback relationship example.
- `packages/contract-test-suite/fixtures/phase3_repeated_feedback_clicks_contract_fixture.json` - Repeated feedback click/idempotency example.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `services/hermes-contract-layer/hooks/response_filter_contract_result_recorder/` already provides the repo-owned after-filter hook artifact.
- `hermes_contract_layer.hook.record_contract_result` can record four core contract events when `INKSTATUTE_CONTRACT_LOG_PATH` or an explicit log path is configured.
- `hermes_contract_layer.mapper.map_agent_end_context` already normalizes WeCom aliases, maps `message_id` to `AgentResult.feedback_target`, filters `raw_payload`, and marks route-mismatch skill candidates as human-reviewed.
- `ContractEventWriter` writes append-only JSONL envelopes with `event_key`, `occurred_at`, `ingested_at`, `seq`, and nested schema-valid payloads.
- `contract_test_suite.event_stream_replay` can validate event-stream envelopes and relationship integrity without requiring fabricated `FeedbackEvent` records.
- Existing Phase 3 fixtures demonstrate route errors, repeated feedback clicks, long-task failures, and non-legal tasks through schema-valid full bundles.

### Established Patterns

- The repo is Python-first and dependency-free for contract/runtime-adjacent packages. Continue using stdlib `unittest`, `json`, `pathlib`, and explicit `PYTHONPATH` commands unless the active plan justifies otherwise.
- Tests use synthetic fixtures and temporary paths. Runtime logs, customer documents, and live Hermes state do not belong in repo fixtures.
- Phase 4 deliberately kept feedback capture out of event streams; Phase 5 should add feedback evidence only when the source data exists or is sanitized.

### Integration Points

- Result log path: `INKSTATUTE_CONTRACT_LOG_PATH` consumed by `hermes_contract_layer.hook`.
- Live Hermes profile hook deployment target, if explicitly validated: `/home/sorawatcher/.hermes/profiles/lawfirm/hooks/`, using the repo-owned after-filter artifact.
- Existing feedback inputs named by the PRD: `feedback.jsonl` and `pending_previews.jsonl`.
- Future service boundary: `services/feedback-service/` may be introduced for minimal normalization if Phase 5 planning requires it, but Phase 6 owns full APIs, dedupe/classification workflow, and pending queues.
- Contract-test-suite fixtures and tests are the natural place to prove WeCom event/feedback relationship replay before CI wiring in Phase 7.

</code_context>

<specifics>
## Specific Ideas

- Prefer a Phase 5 runbook/evidence artifact that separates "fixture validation passed" from "live WeCom validation passed" so synthetic tests cannot be mistaken for live acceptance.
- Prefer validation cases named around the PRD journeys: `wecom_contract_review_long_task`, `wecom_legal_retrieval_short_task`, and `wecom_route_mismatch_feedback`.
- Prefer keeping the first feedback normalization path small: parse sanitized JSONL lines, resolve preview/message references, emit `FeedbackEvent`, and validate with existing schema/replay helpers.
- Prefer recording unresolved runtime facts as explicit blockers: missing WeCom access, missing callback sample, unstable `message_id`, missing ACK timestamp, or unavailable long-task state source.

</specifics>

<deferred>
## Deferred Ideas

- Full feedback-service APIs, production pending queues, broad classification, and operational queue export remain Phase 6.
- Conversation/task/read APIs remain Phase 6.
- CI workflow enforcement, coverage thresholds, privacy gates, and broad composability gates remain Phase 7.
- Five-workday lawyer trial metrics and acceptance reporting remain Phase 8.
- Automatic synthesis or modification of legal conclusion skills remains out of scope for V2.

</deferred>

---

*Phase: 5-WeCom Shadow Loop Validation*
*Context gathered: 2026-06-28T03:05:00Z*
