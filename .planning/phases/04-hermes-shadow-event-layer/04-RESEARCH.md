# Phase 4: Hermes Shadow Event Layer - Research

## Research Complete

Phase 4 should implement the smallest repo-owned Hermes contract layer that can be tested locally and later deployed into the Hermes `lawfirm` profile without changing outbound behavior.

## Phase Inputs

### Goal

Hermes lawfirm produces standard V2 contract logs through a shadow hook layer while preserving all existing outbound behavior.

### Requirement IDs

- `REQ-hermes-contract-layer`
- `REQ-observability-and-replay`

### Source Boundaries

- V2 source of truth remains `docs/requirements/V2-PRD.md`.
- Phase 4 may add `services/hermes-contract-layer/`.
- Phase 4 may extend `packages/contract-test-suite/` only where needed to replay/validate Phase 4 hook-output event streams.
- Phase 4 must not modify Hermes core, Hermes runtime profile files under `/home/sorawatcher/.hermes`, WeCom gateway behavior, router behavior, skills, MCP registry, model configuration, feedback-service processing, conversation-read-view APIs, databases, queues, or `.github` workflows.

## Hermes Source Evidence

Phase 3 found the relevant Hermes source/runtime files outside this repo:

| Source | Finding | Phase 4 impact |
|--------|---------|----------------|
| `/home/sorawatcher/.hermes/hermes-agent/gateway/hooks.py` | Hook directories load in lexicographic directory order; handlers for the same event run sequentially with a shared mutable `context`. | Hook artifact directory must sort after `response_filter`. |
| `/home/sorawatcher/.hermes/hermes-agent/gateway/run.py` | `agent:start` context includes platform/user/chat/thread/session and `message_text[:500]`; `agent:end` adds `(response or "")[:500]`. | AgentTurn input is partial; AgentResult response is a preview unless another full-response source is found. |
| `/home/sorawatcher/.hermes/profiles/lawfirm/hooks/response_filter/handler.py` | On `agent:end`, it writes `context["message_id"]` and `context["response"]` after filtering and feedback prompt injection. | A later same-event recorder can read post-filter `message_id` and filtered response preview. |
| `/home/sorawatcher/.hermes/profiles/lawfirm/hooks/template_card_dispatcher/HOOK.yaml` and `wecom_template_card_shim/HOOK.yaml` | Both are `gateway:startup`, not `agent:end`. | Feedback/card callback normalization remains Phase 5/6. |

No raw runtime payloads, callback bodies, customer content, logs, or database rows are needed for Phase 4 planning artifacts.

## Recommended Architecture

### Package Layout

```text
services/hermes-contract-layer/
  pyproject.toml
  README.md
  hooks/
    response_filter_contract_result_recorder/
      HOOK.yaml
      handler.py
  src/hermes_contract_layer/
    __init__.py
    ids.py
    mapper.py
    writer.py
    hook.py
  tests/
    test_hook.py
    test_mapper.py
    test_writer.py
```

This layout keeps deployment artifacts and testable Python code in the repo without writing into the live Hermes profile.

### Hook Artifact

Use `response_filter_contract_result_recorder/` as the recommended hook directory. It sorts after `response_filter` and makes the ordering dependency visible. The manifest should still name the hook `contract_result_recorder` and register `agent:end`.

The handler should:

1. Exit for non-`agent:end` events.
2. Call a package function such as `record_contract_result(event_type, context, writer=...)`.
3. Never mutate outbound context fields such as `response`, `message_id`, `platform`, `user_id`, `chat_id`, `session_id`, or gateway/router/skill state.
4. Catch/log local recorder failures without raising into Hermes.

### Mapper

The mapper should produce schema-valid dictionaries for:

- `AgentTurn`
- `RouteDecision`
- `ExecutionTrace`
- `AgentResult`

Mapping rules:

- Use `session_id` as the default `conversation_id` candidate unless a better confirmed source is passed in.
- Normalize `platform` into the platform contract `Channel` values where possible.
- Use `message` from hook context as capped content and mark that cap in metadata.
- Use deterministic IDs derived from stable context values and timestamps supplied by tests/runtime; avoid random IDs in unit tests.
- Use `message_id` from `response_filter` as `feedback_target` only when present; otherwise use a deterministic result-derived target with metadata marking the fallback.
- Include `execution_trace` on `AgentResult` or link it through `metadata.trace_id`.
- Use exact enum strings from `platform_contract.enums`; do not introduce aliases.
- If router/skill/tool fields are absent, create explicit unavailable/skipped metadata rather than pretending a registered skill was matched.

### Writer

Use a dependency-free JSONL writer. Recommended record shape:

```json
{
  "event_key": "agent_result",
  "occurred_at": "2026-06-28T00:00:00Z",
  "ingested_at": "2026-06-28T00:00:01Z",
  "seq": 3,
  "event": { "... schema-valid event payload ..." }
}
```

The service-owned envelope lets Phase 4 attach log clocks and sequence to every record without violating event schemas that currently reject unknown top-level fields. Tests should validate the `event` payload through `validate_event`.

The writer should accept an explicit path and create parent directories if needed. Tests must use temporary files; runtime log files must not be committed.

### Replay

Existing `validate_event_bundle` requires all five event keys, including `FeedbackEvent`. Phase 4 should avoid fake feedback events. Add event-stream validation support that:

- loads JSONL records or stream fixtures,
- validates each record's `event_key` and nested `event` payload,
- checks available relationships across AgentTurn, RouteDecision, ExecutionTrace, and AgentResult,
- tolerates missing FeedbackEvent until Phase 5/6.

Existing complete-bundle replay must remain unchanged.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Recorder runs before `response_filter` and captures unfiltered/admin text. | Enforce hook directory sorted after `response_filter`; add a test that rejects canonical `contract_result_recorder/` as an after-filter directory. |
| Hook changes outbound behavior. | Handler tests assert context values are unchanged after recording. |
| Mapper stores raw legal/customer payloads. | Tests scan event records for exact `raw_payload` keys and secret/sensitive patterns; only `raw_payload_ref` references are allowed. |
| Schema payloads get polluted with writer envelope fields. | Tests validate nested `event` payloads with existing `validate_event`. |
| Missing router/long-task signals are approximated. | Mapper records unavailable/skipped metadata and exact enum values only. |
| Partial Phase 4 streams are forced into fake full bundles. | Add stream replay support rather than fabricating FeedbackEvent. |

## Validation Architecture

### Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | Python stdlib `unittest` |
| Config file | none |
| Quick run command | `PYTHONPATH=services/hermes-contract-layer/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/hermes-contract-layer/tests -v` |
| Full suite command | `python -m compileall services/hermes-contract-layer/src services/hermes-contract-layer/tests packages/contract-test-suite/src packages/contract-test-suite/tests && cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py && cd ../.. && PYTHONPATH=services/hermes-contract-layer/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/hermes-contract-layer/tests -v` |
| Estimated runtime | under 5 seconds in current repo |

### Required Automated Coverage

- Hook artifact manifest/path validates after-filter ordering.
- Hook handler records on `agent:end` without mutating outbound context.
- Mapper emits schema-valid AgentTurn, RouteDecision, ExecutionTrace, and AgentResult payloads for success, simple-QA/unmatched, failed, and long-task/status paths.
- Writer appends valid JSONL records with monotonic `seq`, `occurred_at`, and `ingested_at` envelope fields.
- Contract-test-suite stream replay validates Phase 4 event-stream fixtures and available relationships without requiring FeedbackEvent.
- Full existing contract-test-suite remains green.

### Manual-Only Verification

No manual verification is required for Phase 4 planning or local implementation. Deployment into a live Hermes profile and real WeCom loop validation belong to Phase 5 or an explicit deployment instruction.

## Planning Recommendation

Use three plans:

1. Scaffold `services/hermes-contract-layer` with the hook artifact, package metadata, README, hook entrypoint, and no-behavior-change tests.
2. Implement mapper and JSONL writer with schema validation tests for AgentTurn, RouteDecision, ExecutionTrace, and AgentResult.
3. Add Phase 4 stream replay support and 3-5 hook-output fixtures to the contract-test-suite, then run the full suite.

## RESEARCH COMPLETE
