# Phase 5: WeCom Shadow Loop Validation - Research

## Research Complete

Phase 5 should validate the smallest end-to-end WeCom shadow loop that proves Phase 4 result logging and existing Hermes feedback capture can connect to standard V2 contract events without changing Hermes legal/business outbound behavior.

Update 2026-06-28: this Phase 5 research predates the InkStatute WeCom service requirement change. The local fixture validation remains valid, but live WeCom acceptance now depends on Phase 5.5 proving InkStatute-owned WeCom receive/send, Hermes agent-only invocation, and assistant output boundary behavior for Hermes gateway/update/command/meta messages.

## Phase Inputs

### Goal

Lawyers can use the existing WeCom loop while V2 shadow records results and feedback into standard events.

### Requirement IDs

- `REQ-wecom-daily-test-loop`

### Source Boundaries

- V2 source of truth remains `docs/requirements/V2-PRD.md`.
- Phase 5 may add opt-in validation helpers, sanitized fixtures, runbook/evidence docs, and minimal FeedbackEvent normalization needed to prove the loop.
- Phase 5 must not rebuild Hermes core, WeCom gateway, router, skills, MCP registry, model gateway, session storage, feedback card/shim channel, production read APIs, queues, databases, CI workflows, or legal skill auto-modification.
- Live Hermes profile deployment must be explicit and reversible. Repo tests must not mutate `/home/sorawatcher/.hermes`.

## Existing Implementation Surface

| Source | Finding | Phase 5 impact |
|--------|---------|----------------|
| `services/hermes-contract-layer/src/hermes_contract_layer/hook.py` | `INKSTATUTE_CONTRACT_LOG_PATH` controls shadow JSONL recording; recorder errors are swallowed and outbound context keys are restored. | Use this as the live validation log switch and no-regression contract. |
| `services/hermes-contract-layer/src/hermes_contract_layer/mapper.py` | `message_id` maps to `AgentResult.feedback_target` when present; missing source data is recorded as unavailable. | Phase 5 must prove this target matches feedback callback evidence before trusting it. |
| `packages/contract-test-suite/src/contract_test_suite/event_stream_replay.py` | Validates JSONL event envelopes and relationships across AgentTurn, RouteDecision, ExecutionTrace, AgentResult. | Extend validation with feedback evidence instead of replacing Phase 4 stream replay. |
| `packages/platform-contract/src/platform_contract/events.py` | `FeedbackEvent` requires feedback/conversation/user/source/event_type/status/created_at and optional result/target/route/skill fields. | Minimal normalizer can target this schema without a production API. |
| `packages/contract-test-suite/fixtures/phase3_repeated_feedback_clicks_contract_fixture.json` | Defines idempotency metadata for repeated callbacks. | Reuse the dedupe shape if Phase 5 includes repeated callback evidence. |
| `docs/requirements/V2-PRD.md` sections 3.8, 4.6, 4.7, 6.3, 10.3, 13 | Existing feedback chain is `response_filter -> pending_previews.jsonl -> template_card_dispatcher -> card -> wecom_template_card_shim -> feedback.jsonl`; Phase 5 must prove the chain and avoid raw payload storage. | Plan around sanitized feedback/previews and explicit live blockers. |

## Recommended Architecture

Use three implementation slices:

1. **Validation harness and runbook**: a dependency-free evidence validator plus a live validation runbook. It checks contract event stream integrity, expected WeCom channel metadata, result `feedback_target`, optional ACK timing evidence, and no forbidden raw payloads.
2. **Minimal feedback normalization**: a small parser/normalizer for sanitized `feedback.jsonl` and `pending_previews.jsonl` samples that emits schema-valid `FeedbackEvent` payloads. Keep the surface narrow; Phase 6 owns APIs, queues, and broad classification.
3. **End-to-end replay/evidence**: fixture-backed replay that connects result stream records to FeedbackEvent records and an evidence document that separates fixture validation from live WeCom validation.

## Validation Architecture

### Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | Python stdlib `unittest` |
| Config file | none |
| Quick run command | `PYTHONPATH=services/hermes-contract-layer/src:services/feedback-service/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/hermes-contract-layer/tests -v` |
| Full suite command | `python -m compileall services/hermes-contract-layer/src services/hermes-contract-layer/tests services/feedback-service/src services/feedback-service/tests packages/contract-test-suite/src packages/contract-test-suite/tests && cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py && cd ../.. && PYTHONPATH=services/hermes-contract-layer/src:services/feedback-service/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/hermes-contract-layer/tests -v && PYTHONPATH=services/feedback-service/src:packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s services/feedback-service/tests -v` |
| Estimated runtime | under 10 seconds for fixture-backed tests in current repo |

### Required Automated Coverage

- Validation helper rejects malformed or missing core event streams.
- Validation helper proves `AgentResult.feedback_target` is present for WeCom callback association cases or reports a blocker.
- Sanitized feedback/previews normalize into schema-valid `FeedbackEvent` payloads.
- FeedbackEvent relationship checks link `turn_id`, `conversation_id`, `result_id`, and `feedback_target` to the recorded result stream or fixture bundle.
- Repeated callback samples dedupe through a stable idempotency key if included.
- Privacy tests reject exact `raw_payload` keys and secret-like strings in validation fixtures.

### Manual-Only Verification

Live WeCom validation is manual or operator-assisted:

1. Deploy/symlink/copy the repo-owned hook artifact into the Hermes lawfirm profile only after explicit operator action.
2. Configure `INKSTATUTE_CONTRACT_LOG_PATH` to a non-repo runtime path.
3. For legacy migration evidence, send one short legal retrieval task and one long/document task through the existing Hermes-connected WeCom path.
4. For V2 live acceptance, send the same tasks through InkStatute WeCom service so ACK, outbound text/file/template card delivery, and feedback callback capture are owned by InkStatute while Hermes is used only for agent logic.
5. Confirm contract JSONL result records and FeedbackEvent-normalizable sanitized evidence.
6. Record live status in a Phase 5 evidence document. If InkStatute WeCom service is unavailable, record the blocker instead of claiming V2 acceptance.

## Planning Recommendation

Use three plans:

1. Add WeCom loop validation harness and runbook.
2. Add minimal feedback normalizer and sanitized callback fixtures.
3. Add end-to-end replay/evidence integration and final verification commands.

## RESEARCH COMPLETE
