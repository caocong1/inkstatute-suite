---
phase: 05-wecom-shadow-loop-validation
fixture_status: passed
live_wecom_status: blocked
updated: 2026-06-28T05:36:29Z
---

# Phase 05 WeCom Validation Evidence

## Fixture validation

Fixture-backed validation passed for the Phase 5 WeCom result-to-feedback replay.

Evidence:

- `packages/contract-test-suite/fixtures/phase5_wecom_contract_stream.jsonl`
- `packages/contract-test-suite/fixtures/phase5_wecom_feedback_loop_fixture.json`
- `packages/contract-test-suite/fixtures/phase5_wecom_feedback_sample.jsonl`
- `packages/contract-test-suite/fixtures/phase5_wecom_pending_previews_sample.jsonl`
- `packages/contract-test-suite/tests/test_phase5_wecom_loop.py`

Verified behavior:

- The contract stream replays with zero broken core relationships.
- The full bundle validates all five platform event schemas.
- `AgentResult.feedback_target` equals `FeedbackEvent.feedback_target`.
- `AgentResult.result_id` equals `FeedbackEvent.result_id`.
- Minimal normalizer output matches the fixture FeedbackEvent shape for the canonical rating callback.
- Route-mismatch feedback remains human-reviewed and carries no-auto-modify metadata.

## Live WeCom validation

Live WeCom status: blocked

No live Hermes lawfirm profile and connected WeCom validation run was completed in this session. Fixture replay is not live acceptance and is not being claimed as such.

After the 2026-06-28 InkStatute WeCom service requirement update, live WeCom acceptance requires InkStatute-owned WeCom receive/send evidence plus Hermes agent adapter evidence. A live run that proves Hermes gateway can send text/files/cards is not sufficient for V2 acceptance.

Required live evidence before this can be marked `passed`:

- One short WeCom legal retrieval task received by InkStatute WeCom service with ACK, Hermes agent processing, InkStatute text/card delivery, and InkStatute feedback callback capture.
- One long or document task received by InkStatute WeCom service with ACK, Hermes agent processing, InkStatute result push, file/text/card delivery, and InkStatute feedback callback capture.
- Active InkStatute WeCom service/output-boundary evidence showing gateway lifecycle, update/self-update, slash command/help/status/credits/insights, memory/tool-progress, delivery debug, ADMIN_NOTICE, stack traces, internal paths, commands, tokens, and profile/runtime details are blocked or rewritten before ordinary WeCom delivery.
- Operator confirmation that ordinary lawyer users interact with InkStatute WeCom service only, while Hermes is used only for agent logic.
- Sanitized `INKSTATUTE_CONTRACT_LOG_PATH` reference outside the repo.
- Sanitized InkStatute feedback callback reference proving the template-card callback target matches `AgentResult.feedback_target`; Hermes `feedback.jsonl` can be included only as compatibility evidence.
- Operator confirmation that Hermes gateway was not used as the ordinary user channel for V2 live acceptance.

## ACK timing

Fixture ACK timing evidence:

- `ack_started_at`: `2026-06-28T03:20:00Z`
- `ack_completed_at`: `2026-06-28T03:20:04Z`
- elapsed: 4 seconds
- status reference: `fixture://ack/phase5-wecom-loop-001`

Live ACK timing: blocked until the live runbook is completed.

## Outbound behavior preservation

Fixture evidence uses only sanitized replay records and does not mutate Hermes runtime files. It preserves the Phase 4 expectation that recorder failures are non-blocking and outbound Hermes fields are not changed by validation logic.

Live outbound preservation is blocked pending operator-run InkStatute WeCom service validation and Phase 5.5 output-boundary evidence. The live run must confirm legal business text, file, and template-card delivery through InkStatute WeCom service, while Hermes meta/gateway/update/command notices are blocked or rewritten before ordinary WeCom delivery and Hermes is used only for agent logic.

## Feedback normalization

Phase 5 normalization evidence is fixture-backed:

- `normalize_wecom_feedback_records` converts sanitized `feedback.jsonl` and `pending_previews.jsonl` records into schema-valid `FeedbackEvent` dictionaries.
- Repeated card clicks collapse into one canonical event using `feedback_target + action + user_id + created_at_bucket`.
- Route-wrong feedback produces `route_mismatch=true`, `requires_human_review=true`, and `no_auto_modify` metadata.
- Full feedback-service APIs, queues, broad classification, and pending review exports remain Phase 6 scope.

## QQ Bot and WeChat non-acceptance status

QQ Bot and WeChat are not V2 acceptance channels for Phase 5. No live non-regression check was performed in this session.

Status: blocked pending operator confirmation that the Phase 5 shadow validation did not alter QQ Bot or WeChat channel behavior.

## Privacy review

Fixture privacy checks passed:

- No exact `raw_payload` keys are present in Phase 5 fixtures.
- Raw runtime payloads are represented by `raw_payload_ref` or `fixture://raw/...` references.
- No tokens, secrets, runtime databases, callback bodies, customer documents, full ID numbers, phone numbers, bank accounts, addresses, or raw legal payloads are committed.
- Legal/profile-specific context remains under `industry_context` or metadata.

Live privacy review remains blocked until live evidence is collected and sanitized outside the repo.

## Blockers

- Live InkStatute WeCom service and Hermes agent adapter validation was not executed in this session.
- InkStatute WeCom service and assistant output boundary have not yet been planned or verified; live WeCom acceptance cannot pass until Phase 5.5 proves they are active.
- No sanitized live InkStatute feedback callback reference is available.
- No live long/document task evidence is available.
- QQ Bot and WeChat non-regression status has not been operator-confirmed.
