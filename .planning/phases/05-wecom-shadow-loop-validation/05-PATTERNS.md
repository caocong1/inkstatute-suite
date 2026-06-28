# Phase 5: WeCom Shadow Loop Validation - Patterns

## Pattern Map

Phase 5 should extend the Phase 4 shadow layer and contract-test-suite patterns without introducing a live service process.

## Existing Repo Patterns

| Pattern | Existing Source | Apply To |
|---------|-----------------|----------|
| Dependency-free Python packages | `packages/platform-contract/pyproject.toml`, `services/hermes-contract-layer/pyproject.toml` | `services/feedback-service/pyproject.toml` if introduced; keep stdlib-only. |
| Safe hook boundary | `services/hermes-contract-layer/src/hermes_contract_layer/hook.py` and `tests/test_hook.py` | Live validation must not mutate outbound context or propagate recorder errors. |
| Plain dict contract payloads | `services/hermes-contract-layer/src/hermes_contract_layer/mapper.py` | Feedback normalization should produce plain JSON-compatible dicts validated by schema helpers. |
| JSONL envelope replay | `packages/contract-test-suite/src/contract_test_suite/event_stream_replay.py` | Reuse event stream records and relationship reports for result-side evidence. |
| Full fixture relationship checks | `packages/contract-test-suite/src/contract_test_suite/fixture_replay.py` | Use full bundle fixtures when FeedbackEvent is present. |
| Synthetic reference-first fixtures | `packages/contract-test-suite/fixtures/phase3_*.json` and `phase4_*.jsonl` | Phase 5 fixtures must use `fixture://` or `raw_payload_ref`, not raw legal payloads. |

## Proposed Phase 5 Layout

```text
services/hermes-contract-layer/
  docs/wecom_shadow_loop_validation.md
  src/hermes_contract_layer/wecom_validation.py
  tests/test_wecom_validation.py

services/feedback-service/
  pyproject.toml
  README.md
  src/feedback_service/__init__.py
  src/feedback_service/wecom_normalizer.py
  tests/test_wecom_normalizer.py

packages/contract-test-suite/
  fixtures/phase5_wecom_feedback_loop_fixture.json
  fixtures/phase5_wecom_contract_stream.jsonl
  tests/test_phase5_wecom_loop.py
```

The exact layout is planner/executor discretion, but keep validation and normalization code small and dependency-free.

## Data Flow

```text
WeCom lawyer task
  -> Hermes gateway ACK and lawfirm execution
  -> response_filter writes message_id / preview
  -> response_filter_contract_result_recorder writes AgentResult stream
  -> existing template card path writes feedback.jsonl
  -> minimal normalizer emits FeedbackEvent
  -> contract-test-suite validates message -> result -> feedback relationships
```

## Normalizer Conventions

- Inputs are sanitized examples or runtime file paths supplied outside committed fixtures.
- `feedback_id` should be deterministic from feedback target, action, user, timestamp bucket, and callback reference when possible.
- `source` should be `card_button` for WeCom template-card callback samples.
- `event_type` should map `up` to `rating`, `down`/`needs_fix` to the closest available category, and `route_wrong` to `route_mismatch`.
- `status` defaults to `pending` for actionable feedback.
- `raw_payload_ref` is required in generated evidence; never write full callback bodies into contract logs or fixtures.

## Validation Conventions

- Separate fixture-backed validation from live validation in docs and outputs.
- Treat missing live runtime evidence as a blocker, not a pass.
- Check `AgentResult.feedback_target` and `FeedbackEvent.feedback_target` equality when feedback evidence exists.
- Keep exact async states only; unavailable long-task state sources should be surfaced as unavailable.

## Anti-Patterns to Avoid

- Writing runtime WeCom logs or callback bodies into the repo.
- Mutating `/home/sorawatcher/.hermes` in tests or without explicit operator action.
- Creating a persistent queue, database, web API, or production daemon in Phase 5.
- Treating synthetic fixtures as live lawyer acceptance.
- Auto-modifying legal skills or invoking `skillopt-runner`.
