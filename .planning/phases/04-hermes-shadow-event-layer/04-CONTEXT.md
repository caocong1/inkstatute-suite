# Phase 4: Hermes Shadow Event Layer - Context

**Gathered:** 2026-06-28T01:47:53Z
**Status:** Ready for planning
**Source:** `$gsd-progress --next --auto` / `$gsd-discuss-phase 4 --auto` inline fallback

<domain>
## Phase Boundary

Phase 4 delivers the repo-owned Hermes shadow contract layer: a non-invasive hook artifact, mapper, writer, tests, and replay evidence that can record standard V2 contract events for Hermes lawfirm tasks without changing Hermes outbound behavior.

This phase may add code under `services/hermes-contract-layer/` and focused test-suite support needed to replay Phase 4 hook-output/event-log fixtures. It must not edit Hermes core, Hermes runtime files under `/home/sorawatcher/.hermes`, WeCom gateway behavior, router behavior, skill/MCP/model configuration, feedback-service normalization, conversation-read-view APIs, databases, queues, or `.github` workflows.

</domain>

<decisions>
## Implementation Decisions

### Hook Placement and Deployment Shape

- **D-01:** Implement the Phase 4 hook as a repo-owned deployment artifact under `services/hermes-contract-layer/`, not by directly modifying the local Hermes runtime or profile directories.
- **D-02:** The hook directory artifact must sort after `response_filter`, for example `response_filter_contract_result_recorder/` or `zz_contract_result_recorder/`, while its `HOOK.yaml` manifest name remains `contract_result_recorder`.
- **D-03:** A directory named exactly `contract_result_recorder/` is forbidden for after-filter recording because Phase 3 source evidence proves it sorts before `response_filter`.
- **D-04:** The hook must register on `agent:end` and treat the hook context as post-filter only when the sorted-directory rule is satisfied. It must not mutate `context["response"]`, outbound text, files, cards, gateway state, router state, skill state, MCP state, model configuration, or feedback channel files.

### Mapper Scope

- **D-05:** Phase 4 maps Hermes hook context into `AgentTurn`, `RouteDecision`, `ExecutionTrace`, and `AgentResult` event payloads. `FeedbackEvent` normalization remains Phase 5/6 scope unless a synthetic test fixture needs a referenced feedback example that is clearly not runtime-captured.
- **D-06:** Prefer source-confirmed `agent:start`/`agent:end` fields from Phase 3 for AgentTurn metadata. Missing or capped fields must be represented as unavailable, reference-backed, or metadata-statused; do not invent full inbound content, attachments, message type, or received_at.
- **D-07:** RouteDecision mapping may create a contract-side `simple_qa`, `zero_match`, or unavailable/skipped route record when Hermes does not expose router output. The mapper must label generated route decisions in metadata and preserve `matched_registered_skill=false` when no registered skill was used.
- **D-08:** ExecutionTrace must include exact platform async state values only. Failure and long-task evidence can record stages/errors when source context provides them; missing runtime signals stay unavailable rather than approximated.
- **D-09:** AgentResult content from the current `agent:end` context is capped by Hermes gateway source. The mapper can record the available response preview but must not claim full outbound response capture unless a full-response source is added and tested.

### Writer and Log Contract

- **D-10:** Use a dependency-free append-only JSONL writer for Phase 4. No database, queue, daemon, service process, or network call is introduced.
- **D-11:** Event payloads must stay valid against `platform-contract` schemas. Because not every event schema currently has top-level `occurred_at`, `ingested_at`, or `seq`, the log writer should use a service-owned envelope or allowed metadata for log clocks/sequence rather than adding forbidden top-level fields to schema payloads.
- **D-12:** Sequence numbers must be monotonic within a writer instance and deterministic enough for tests. Tests should use temporary files/directories and must not write runtime logs into the repo.
- **D-13:** Contract logs use `raw_payload_ref` and non-sensitive metadata only. They must not store raw legal text, full callback bodies, secrets, complete ID numbers, phone numbers, bank accounts, addresses, runtime databases, or customer documents.

### Replay and Verification

- **D-14:** Phase 4 replay evidence should validate logged event payloads through the existing `platform-contract` schemas and the `contract-test-suite` harness. If Phase 4 event logs are partial streams without `FeedbackEvent`, add explicit event-stream validation support rather than fabricating feedback events.
- **D-15:** Add 3-5 synthetic Hermes hook-output/event-log fixtures that represent realistic Phase 4 output, including at least one failed or long-running task path. Fixtures must use `fixture://` or `raw_payload_ref` references only.
- **D-16:** The verification gate must include a behavior-preservation assertion: the hook handler returns without altering the provided response/context values used by Hermes outbound behavior, except for its own private metadata/logging side effects.

### the agent's Discretion

- File/module names inside `services/hermes-contract-layer/` are the agent's discretion, provided they are small, dependency-free, tested, and clear enough for Phase 5/6 to consume.
- The exact JSONL envelope shape is the agent's discretion, provided event payloads remain schema-valid and replay helpers can validate the relationship between turn, route, trace, and result records.
- The fixture count can be 3, 4, or 5 depending on how many cases are needed to cover success, simple QA/zero-match, failed/long task, and artifact references without padding.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product and Scope

- `AGENTS.md` - Project source of truth, V2 boundary, implementation priorities, safety/privacy rules, and GSD continuation protocol.
- `docs/requirements/V2-PRD.md` - V2 product requirement source, especially sections on `platform-contract`, `hermes-contract-layer`, event contracts, privacy, development order, and implementation risks.
- `.planning/ROADMAP.md` - Phase 4 goal, success criteria, dependencies, and downstream Phase 5/6/7 boundaries.
- `.planning/REQUIREMENTS.md` - `REQ-hermes-contract-layer` and `REQ-observability-and-replay` details.
- `.planning/STATE.md` - Current decisions and Phase 4 blockers/concerns carried from Phase 3.

### Phase 3 Gates Feeding Phase 4

- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HOOK-ORDER-EVIDENCE.md` - Source-confirmed hook ordering and after-filter directory rule.
- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HOOK-AND-TURN-DECISIONS.md` - Hook ordering, `agent:start`/`agent:end` field strategy, response cap, and AgentTurn reverse-inference limits.
- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-IDENTIFIER-STATE-PRIVACY-RULES.md` - Identifier, feedback target, async state, idempotency, raw payload, retention, redaction, and legal-safety rules.
- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-VERIFICATION.md` - Phase 3 passed verification and downstream runtime evidence gates.

### Contract and Test Harness

- `packages/platform-contract/src/platform_contract/events.py` - Python event binding shapes.
- `packages/platform-contract/src/platform_contract/enums.py` - Allowed async, route, feedback, reply, artifact, error, and risk values.
- `packages/platform-contract/src/platform_contract/schemas/` - JSON Schema source of truth for standard event payload validation.
- `packages/platform-contract/fixtures/README.md` - Fixture privacy and relationship expectations.
- `packages/contract-test-suite/src/contract_test_suite/schema_validation.py` - Existing schema validator and forbidden top-level field behavior.
- `packages/contract-test-suite/src/contract_test_suite/fixture_replay.py` - Existing relationship replay logic.
- `packages/contract-test-suite/tests/test_phase3_non_happy_paths.py` - Recent examples for non-happy-path fixture testing.
- `packages/contract-test-suite/scripts/run_contract_tests.py` - Package-local verification command.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `platform_contract.events` dataclasses and JSON schemas provide the event payload target. The Phase 4 mapper should produce plain dictionaries that validate against those schemas rather than creating a new contract shape.
- `contract_test_suite.schema_validation.validate_event` and `validate_event_bundle` are the existing validation primitives. Reuse them for Phase 4 event-stream replay support instead of adding a new validator.
- `contract_test_suite.fixture_replay.assert_relationship_integrity` already checks turn, route, trace, result, artifact, and feedback relationships for complete bundles. Phase 4 can reuse the relationship patterns while allowing partial streams where feedback is unavailable.
- Phase 3 fixture tests show how to enforce `raw_payload_ref`, human-review skill candidate, async state, and non-legal composability constraints with stdlib `unittest`.

### Established Patterns

- Existing packages are Python-first and dependency-free. Phase 4 should preserve that unless the PRD explicitly requires otherwise.
- Current repo has no `services/` directory yet. Creating `services/hermes-contract-layer/` is within the V2 PRD and AGENTS implementation priorities, but it should remain a thin library/artifact layer rather than a running service.
- Existing tests use stdlib `unittest`, `json`, `pathlib`, and explicit `PYTHONPATH` commands. Follow that pattern.

### Integration Points

- Hook artifact path: `services/hermes-contract-layer/hooks/<after-filter-dir>/HOOK.yaml` and handler module, or an equivalent clearly documented layout.
- Mapper/writer package path: `services/hermes-contract-layer/src/hermes_contract_layer/`.
- Test path: `services/hermes-contract-layer/tests/`.
- Replay fixtures/test support: `packages/contract-test-suite/fixtures/` and/or `packages/contract-test-suite/src/contract_test_suite/` only where needed for Phase 4 evidence.

</code_context>

<specifics>
## Specific Ideas

- Preferred after-filter hook directory name for planning: `response_filter_contract_result_recorder/`, because it both sorts after `response_filter` and documents why the prefix exists.
- Preferred writer configuration: explicit file path argument or environment variable for runtime use; tests should pass a temporary path directly.
- Preferred privacy default: store only IDs, enum values, short non-sensitive previews, and `raw_payload_ref` references.
- Preferred replay stance: validate partial Phase 4 event streams honestly rather than creating fake feedback records before Phase 5/6.

</specifics>

<deferred>
## Deferred Ideas

- Deploying or copying the hook into `/home/sorawatcher/.hermes/profiles/lawfirm/hooks/` is deferred until an explicit deployment/validation phase or user instruction.
- WeCom template-card callback capture and `feedback.jsonl` normalization remain Phase 5/6.
- Conversation read APIs remain Phase 6.
- CI workflow wiring, coverage thresholds, and privacy gates remain Phase 7.
- Real lawyer trial validation remains Phase 8.

</deferred>

---

*Phase: 4-Hermes Shadow Event Layer*
*Context gathered: 2026-06-28T01:47:53Z*
