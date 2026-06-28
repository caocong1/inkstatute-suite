# Phase 4: Hermes Shadow Event Layer - Patterns

## Pattern Map

Phase 4 has no existing service package in this repo, so implementation should borrow patterns from the established package/test layout and from source-confirmed Hermes hook behavior.

## Existing Repo Patterns

| Pattern | Existing Source | Apply To |
|---------|-----------------|----------|
| Dependency-free Python package | `packages/platform-contract/pyproject.toml`, `packages/contract-test-suite/pyproject.toml` | `services/hermes-contract-layer/pyproject.toml` with no runtime dependencies. |
| Stdlib unittest tests | `packages/platform-contract/tests/test_self_check.py`, `packages/contract-test-suite/tests/*.py` | `services/hermes-contract-layer/tests/*.py`. |
| Schema validation through shared harness | `packages/contract-test-suite/src/contract_test_suite/schema_validation.py` | Mapper/writer tests and Phase 4 stream replay. |
| Relationship diagnostics as structured records | `packages/contract-test-suite/src/contract_test_suite/fixture_replay.py` | Phase 4 stream relationship issues. |
| Synthetic fixtures with `fixture://` references | `packages/contract-test-suite/fixtures/phase3_*.json` | Phase 4 hook-output stream fixtures. |

## Hermes Hook Patterns

| Source | Pattern | Phase 4 Rule |
|--------|---------|--------------|
| `/home/sorawatcher/.hermes/hermes-agent/gateway/hooks.py` | Hook directories load in sorted directory order and handlers append per event. | Use a directory sorted after `response_filter`; test the ordering rule with pure path/name assertions. |
| `/home/sorawatcher/.hermes/hermes-agent/gateway/hooks.py` | `emit()` catches hook exceptions and does not return handler values. | Phase 4 handler must catch local recorder errors and avoid relying on a return value. |
| `/home/sorawatcher/.hermes/hermes-agent/gateway/run.py` | `agent:start` emits capped message context; `agent:end` emits capped response context. | Mapper metadata must record capped/partial fields and use references for missing raw payloads. |
| `/home/sorawatcher/.hermes/profiles/lawfirm/hooks/response_filter/handler.py` | `response_filter` writes `message_id` and filtered `response` back to context. | Recorder can use `message_id` as `feedback_target` only after it runs after `response_filter`. |

## Proposed Service Layout

```text
services/hermes-contract-layer/
  pyproject.toml
  README.md
  hooks/response_filter_contract_result_recorder/HOOK.yaml
  hooks/response_filter_contract_result_recorder/handler.py
  src/hermes_contract_layer/__init__.py
  src/hermes_contract_layer/hook.py
  src/hermes_contract_layer/ids.py
  src/hermes_contract_layer/mapper.py
  src/hermes_contract_layer/writer.py
  tests/test_hook.py
  tests/test_mapper.py
  tests/test_writer.py
```

## Data Flow

```text
Hermes agent:end context
  -> hook handler
  -> mapper builds AgentTurn / RouteDecision / ExecutionTrace / AgentResult dictionaries
  -> schema validation in tests
  -> JSONL writer appends envelope records
  -> contract-test-suite stream replay validates event payloads and relationships
```

## Mapper Conventions

- Keep event dictionaries plain JSON-compatible `dict` objects.
- Validate in tests with `contract_test_suite.schema_validation.validate_event`.
- Use deterministic ID helpers so tests can assert exact relationship IDs.
- Keep missing source fields visible in `metadata`, using values like `source_status`, `content_truncated`, `route_source`, or `raw_payload_ref`.
- Use `industry_context.domain = "lawfirm"` for Hermes lawfirm events and keep legal/profile-specific fields out of platform top-level fields.

## Writer Conventions

- JSONL envelope fields: `event_key`, `occurred_at`, `ingested_at`, `seq`, `event`.
- Nested `event` payload must validate against the platform event schema named by `event_key`.
- Writer state can keep in-memory monotonic sequence for Phase 4; persistence/recovery across process restarts is not required unless the plan explicitly adds a small seq-state file with tests.
- Tests must use `tempfile.TemporaryDirectory` or equivalent and must not write committed runtime logs.

## Replay Conventions

- Preserve existing full-bundle fixture replay behavior.
- Add a separate stream replay helper for Phase 4 JSONL/event-stream records.
- Relationship checks should include at least:
  - all available events share the same `turn_id`,
  - `execution_trace.route_decision.route_decision_id` matches RouteDecision,
  - `agent_result.metadata.trace_id` matches ExecutionTrace,
  - `agent_result.metadata.route_decision_id` matches RouteDecision,
  - AgentResult artifact IDs match ExecutionTrace artifacts when present.
- Missing FeedbackEvent is acceptable in Phase 4 stream replay and must be explicit.

## Anti-Patterns to Avoid

- Creating a live service process, queue, database, or `.github` workflow in Phase 4.
- Writing directly into `/home/sorawatcher/.hermes/profiles/lawfirm/hooks/`.
- Naming the hook artifact directory `contract_result_recorder/`.
- Adding `occurred_at`, `ingested_at`, or `seq` directly to event payloads whose schemas reject unknown fields.
- Fabricating feedback events before Phase 5/6.
- Embedding raw legal/customer payloads or callback bodies.
