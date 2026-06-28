# InkStatute Contract Test Suite

This package provides the Phase 2 local contract harness for InkStatute V2. It consumes the sibling `platform-contract` schemas and fixtures, validates contract event shape, replays fixture bundles, checks relationship continuity, and proves local synthetic composability across non-legal finance/tax, engineering, and education examples.

## Local Command

Run the suite from the repository with:

```bash
cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py
```

The runner is package-local and stdlib-only. It inserts `src` and `../platform-contract/src` into `sys.path`, performs `unittest` discovery against `packages/contract-test-suite/tests`, and exits non-zero on failure.

## Coverage Boundary

This suite validates:

- schema validation for the five platform contract event types
- Phase 1 platform-contract fixtures
- fixture replay and relationship integrity across turn, route, trace, result, artifacts, and feedback
- Phase 4 JSONL event-stream replay for partial Hermes shadow logs
- Phase 5 WeCom result-to-feedback replay using sanitized contract stream and feedback fixtures
- synthetic composability for non-legal finance/tax, engineering, and education tasks
- rejection of legal-only or sensitive top-level fields in platform events

This package does not implement Hermes hooks, real Hermes adapters, live WeCom validation, feedback-service APIs, conversation read-view APIs, or `.github` CI workflows.

Phase 7 owns CI enforcement for this command, including any `.github` workflow wiring and broader composability/privacy gates. Phase 3 and Phase 4 own real Hermes output replay and hook/adaptor work.

## Phase 4 Event Streams

Phase 4 hook-output fixtures are JSONL streams under `fixtures/phase4_*_event_stream.jsonl`. Each line is a writer envelope with `event_key`, `occurred_at`, `ingested_at`, `seq`, and a nested schema-valid `event` payload.

Stream replay validates the available `AgentTurn`, `RouteDecision`, `ExecutionTrace`, and `AgentResult` relationships. It intentionally does not require or fabricate `FeedbackEvent`, because WeCom callback capture and feedback normalization belong to Phase 5/6. Full five-event bundle replay remains unchanged for standard fixture JSON files.

## Phase 5 WeCom Replay

Phase 5 WeCom result-to-feedback fixtures are under `fixtures/phase5_wecom_*`. They prove a sanitized fixture chain from WeCom `AgentTurn` through `AgentResult.feedback_target` to a normalized `FeedbackEvent.feedback_target`.

This is fixture replay, not live validation. Live validation remains an operator-run Hermes lawfirm and WeCom check documented in `.planning/phases/05-wecom-shadow-loop-validation/05-WECOM-VALIDATION.md`; synthetic replay must not be reported as live WeCom acceptance.
