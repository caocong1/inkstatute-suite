# WeCom Shadow Loop Validation

This runbook validates Phase 5 WeCom evidence for the existing Hermes `lawfirm` profile. It separates fixture validation from live WeCom validation so synthetic evidence is never claimed as live acceptance.

Update 2026-06-28: live WeCom acceptance now depends on Phase 5.5 InkStatute WeCom service evidence. This runbook's Phase 5 recorder checks remain valid as legacy/fixture evidence, but a V2 live pass must prove InkStatute receives/sends WeCom directly, Hermes is used only for agent logic, and ordinary users do not see Hermes gateway/update/self-update/command/help/status/credits/insights/memory/tool-progress/debug notices.

## Fixture validation status

Fixture validation uses sanitized contract JSONL streams and repo-local tests only.

Run the local evidence helper:

```bash
PYTHONPATH=services/hermes-contract-layer/src:packages/platform-contract/src:packages/contract-test-suite/src \
  python -m unittest discover -s services/hermes-contract-layer/tests -p 'test_wecom_validation.py' -v
```

Fixture validation can be marked `passed` when:

- The stream has `agent_turn`, `route_decision`, `execution_trace`, and `agent_result`.
- `agent_turn.channel` is `wecom`.
- `agent_result.feedback_target` is present when feedback is expected.
- Optional ACK timing evidence is within the configured timeout.
- The evidence contains no exact `raw_payload` keys, callback bodies, customer documents, tokens, runtime databases, or raw legal payloads.

Fixture validation does not prove live Hermes or live WeCom behavior.

## Live WeCom status

Record live status as exactly one of:

- `passed`: InkStatute WeCom service and Hermes agent adapter were exercised with sanitized evidence references.
- `blocked`: InkStatute WeCom service, Hermes agent adapter, or required evidence was unavailable.

Do not mark live status as `passed` from fixture data. If live runtime credentials, channel state, callback samples, or sanitized task access are unavailable, record `blocked` with the blocker details described below.

## Opt-in hook deployment

Live validation is explicit operator work. Repo tests never deploy, copy, symlink, or mutate files under `/home/sorawatcher/.hermes`.

Before live validation:

1. Confirm the Hermes `lawfirm` profile is the intended target.
2. Configure `INKSTATUTE_CONTRACT_LOG_PATH` to a runtime path outside this repo, for example under a local ignored runtime directory.
3. Deploy the repo-owned hook artifact only after explicit operator approval:

```text
services/hermes-contract-layer/hooks/response_filter_contract_result_recorder/
```

The hook manifest name is `contract_result_recorder`, and the directory is intended to load after Hermes `response_filter`. The hook must remain a shadow recorder: it observes the `agent:end` context and must not alter legal/business agent output, routing, skills, MCP tools, model configuration, or feedback shim behavior. Ordinary WeCom ACK/send/card/callback behavior is owned by InkStatute WeCom service in the updated V2 architecture.

## Runtime evidence to collect

Collect sanitized references, not raw runtime files. Minimum live evidence:

- One short WeCom legal retrieval task received by InkStatute WeCom service that returns text with citations and a template card through InkStatute send.
- One long or document task received by InkStatute WeCom service that returns the expected text/file result and a template card through InkStatute send.
- InkStatute WeCom service ACK start and completion timestamps showing the ACK completed within the expected timeout.
- A contract JSONL stream at `INKSTATUTE_CONTRACT_LOG_PATH` containing the four core result-side events.
- The `AgentResult.feedback_target` value and a sanitized reference proving it matches the template-card callback target.
- A sanitized feedback callback reference showing capture through InkStatute WeCom service; Hermes `feedback.jsonl` is compatibility evidence only.
- Confirmation that QQ Bot and WeChat were not changed as part of validation.

When a feedback callback is available, preserve only the minimum fields needed to normalize into `FeedbackEvent`: stable feedback id or idempotency key, conversation/user references, target/result reference, feedback source/type/action/status, timestamp, and sanitized metadata.

## Rollback

Rollback must be available before deployment:

1. Remove the `contract_result_recorder` hook artifact from the live Hermes `lawfirm` hooks directory, or revert the explicit symlink/copy operation used for validation.
2. Unset `INKSTATUTE_CONTRACT_LOG_PATH` or point it to a disabled runtime location.
3. Restart or reload Hermes only through the existing operator procedure for that profile.
4. Re-run a normal WeCom message and template-card feedback check through InkStatute WeCom service. Existing Hermes gateway/card/shim can be checked separately as migration evidence if needed.

Recorder failures must remain non-blocking for Hermes legal/business agent behavior. InkStatute WeCom service failures are separate: if receive/send/output policy cannot be proven active, live WeCom acceptance remains blocked.

## Privacy rules

Do not commit:

- Runtime contract logs.
- `feedback.jsonl` or `pending_previews.jsonl` from live Hermes.
- Callback bodies.
- Customer legal text, uploaded documents, or generated confidential documents.
- Tokens, secrets, gateway credentials, runtime databases, or complete identifiers.
- Full phone numbers, ID numbers, bank accounts, addresses, or raw legal payloads.

Commit only synthetic fixtures, sanitized excerpts, or references such as `raw_payload_ref` and evidence ids. Legal-specific details belong in `industry_context` when needed; platform-level schemas remain industry-neutral.

## Blocked evidence format

Use this format when live validation cannot be completed:

```text
Live WeCom status: blocked
Date:
Operator:
Blocked reason:
Unavailable evidence:
Fixture validation status:
Next unblock action:
Privacy review:
```

Common blockers include missing WeCom access, unavailable InkStatute WeCom service, unavailable Hermes runtime/agent adapter, missing callback sample, unstable `message_id` to feedback target mapping, missing ACK timestamps, unavailable long-task state source, missing assistant output boundary evidence, or inability to sanitize evidence safely.
