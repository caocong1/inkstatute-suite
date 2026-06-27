# Phase 03 Hermes Source Inventory

**Plan:** 03-01  
**Created:** 2026-06-27T18:24:49Z  
**Scope:** Repo-local evidence ledger for Hermes source/runtime artifacts needed by Phase 3.

## Summary

This repository contains the V2 PRD, platform contract schemas, synthetic fixtures, and the contract-test-suite. It does not contain repo-local Hermes runtime/profile source, hook implementations, callback payload samples, `feedback.jsonl`, `pending_previews.jsonl`, session databases, task logs, gateway runtime files, or long-task state logs.

PRD prose is treated as product/specification evidence only. It is not treated as source-confirmed Hermes API evidence. Any Phase 4 production hook work that depends on hook order, callback fields, message id stability, inbound hook availability, or long-task states remains `requires Hermes source/runtime`.

No raw logs, runtime databases, customer documents, callback payload bodies, secrets, or legal text were copied into this inventory. Future raw runtime material must be represented by references such as `raw_payload_ref`, not embedded.

## Commands Run

| Command | Purpose | Outcome |
|---------|---------|---------|
| `rg --files` | Enumerate repo-tracked visible files. | Returned project docs, platform-contract files, contract-test-suite files, and synthetic fixtures only. No Hermes runtime/profile source files were listed. |
| `find . -maxdepth 5 -type f \( -name 'HOOK.yaml' -o -name 'handler.py' -o -iname '*hermes*' -o -iname '*hook*' -o -iname '*wecom*' -o -iname '*feedback*' -o -iname '*preview*' -o -iname '*session*' -o -iname '*task*' -o -iname '*gateway*' -o -iname '*callback*' \) -print \| sort` | Target file inventory for hook, gateway, feedback, session, task, and callback artifacts. | Returned only synthetic fixture files. No `HOOK.yaml`, `handler.py`, Hermes hook implementation, runtime JSONL, callback sample, session DB, task log, or gateway source was found. |
| `rg -n "response_filter\|template_card\|wecom_template_card_shim\|message_id\|feedback\|long_task\|agent:end\|gateway:startup" -S .` | Search repo content for required Hermes hook and feedback-chain terms. | Matches were in `README.md`, `AGENTS.md`, `docs/requirements/V2-PRD.md`, planning docs, contract schemas, tests, and synthetic fixtures. No Hermes runtime implementation or runtime data was found. |
| `rg --files \| rg '(^\|/)(HOOK\.yaml\|handler\.py\|feedback\.jsonl\|pending_previews\.jsonl)$\|response_filter\|template_card_dispatcher\|wecom_template_card_shim\|long_task\|agent:end\|gateway:startup\|callback\|session\|task\|gateway\|hermes\|hook\|wecom\|feedback\|preview'` | File-name filtered check for the same artifact classes. | Returned fixture/schema files related to contract feedback and non-legal tasks only. No runtime Hermes evidence files were found. |

## Inventory

| Artifact Class | Status | Repo Evidence | Notes for Downstream Plans |
|----------------|--------|---------------|----------------------------|
| Hermes runtime/profile source root | absent | `rg --files` did not list a Hermes source tree or profile runtime directory. `find` found no matching Hermes runtime files under the repo. | Plan 03-02 and Plan 03-03 must not claim source-confirmed hook or callback behavior from this repo alone. |
| `HOOK.yaml` | absent | Targeted `find` returned no `HOOK.yaml`. PRD mentions the file format at `docs/requirements/V2-PRD.md`. | Hook registration format is specification evidence only until Hermes source/runtime is mounted. |
| `handler.py` | absent | Targeted `find` returned no `handler.py`. PRD mentions hook handler implementation at `docs/requirements/V2-PRD.md`. | Handler call signature and context mutability require Hermes source/runtime confirmation. |
| `response_filter` hook source | absent | `rg -n ... -S .` matched PRD/planning references only; no implementation file exists. | Hook order after filtering cannot be confirmed locally. Phase 4 production recorder work is blocked until source/runtime evidence exists or the fallback is selected. |
| `template_card_dispatcher` hook source | absent | `rg -n ... -S .` matched PRD/planning references only; no implementation file exists. | Template card generation and card identifier fields require Hermes source/runtime or sanitized runtime samples. |
| `wecom_template_card_shim` source | absent | `rg -n ... -S .` matched PRD/planning references only; no implementation file exists. | Callback payload shape, retry behavior, and idempotency fields are unconfirmed. |
| `pending_previews.jsonl` | absent | Targeted `find` returned no file named `pending_previews.jsonl`. | Preview storage path, retention owner, and fields require Hermes runtime evidence. |
| `feedback.jsonl` | absent | Targeted `find` returned no file named `feedback.jsonl`. | Feedback normalization rules cannot be field-confirmed until sanitized rows are supplied. |
| Sessions database or session logs | absent | Targeted `find` returned no session DB/log/runtime files; only synthetic fixture files appeared. | AgentTurn reverse inference from session context is `requires Hermes source/runtime`. |
| Task logs / async task runtime records | absent | Targeted `find` returned no task log/runtime files; only synthetic task fixtures appeared. | Long-task mapping to `queued`, `running`, `waiting_for_user`, `succeeded`, `failed`, and `cancelled` cannot be source-confirmed locally. |
| Long-task state source | requires Hermes source/runtime | Platform enum values exist in `packages/platform-contract/src/platform_contract/enums.py`, but no Hermes runtime source/logs exist in this repo. | Plan 03-03 must mark each runtime signal as confirmed, derived, unavailable, or requires Hermes source/runtime. |
| `agent:end` hook event | requires Hermes source/runtime | PRD states `agent:end` exists and includes response/platform/user/session context. No hook loader/source confirms it locally. | Plan 03-02 may use PRD as design input but must keep event fields unconfirmed until source/runtime evidence is available. |
| `gateway:startup` hook event | requires Hermes source/runtime | PRD states `gateway:startup` exists. No gateway source or hook loader confirms it locally. | Startup hook capability is not enough to infer inbound turn capture. |
| Hidden inbound hook points | requires Hermes source/runtime | No Hermes source is present to search for unadvertised inbound events. | Plan 03-02 must document this as a blocking source probe for complete AgentTurn input. |
| Callback payload samples | absent | Targeted `find` found no callback sample files; content search found no runtime callback bodies. | One sanitized template-card callback sample is needed before locking `message_id` or dedupe rules. |
| `message_id` generation source | requires Hermes source/runtime | PRD says `response_filter` generates `message_id` and writes it to context. No implementation source exists locally. | Treat `message_id` stability as unconfirmed across Hermes, WeCom card dispatch, and feedback callback. |
| `feedback_target` relationship in contract schemas/fixtures | present | `packages/platform-contract/src/platform_contract/events.py`, JSON schemas, and synthetic fixtures contain `feedback_target`; contract-test-suite relationship checks cover it. | Contract-side field exists and is testable, but real Hermes value selection remains requires Hermes source/runtime. |
| Platform async state enum | present | `packages/platform-contract/src/platform_contract/enums.py` defines `queued`, `running`, `waiting_for_user`, `succeeded`, `failed`, and `cancelled`. | Target vocabulary is confirmed. Hermes source mapping remains unconfirmed. |
| Synthetic feedback fixtures | present | `packages/platform-contract/fixtures/*.json` and `packages/contract-test-suite/fixtures/*.json` include synthetic `feedback_event` objects and `raw_payload_ref` references. | Safe for contract-side examples only; not runtime evidence. |
| Production Hermes hook, mapper, writer, gateway, service, DB, or queue code | absent | `rg --files` listed no `services/hermes-contract-layer`, `services/feedback-service`, runtime DB, queue, or gateway implementation files. | Plan 03-01 creates docs only and does not introduce production runtime changes. |

## Evidence Rules for Plan 03-02 and Plan 03-03

- `present` means a repo-local implementation, schema, fixture, or test file exists and was found by the commands above.
- `absent` means the commands above found no repo-local file or runtime sample for that artifact class.
- `requires Hermes source/runtime` means PRD/planning docs describe the behavior, but this repo lacks the implementation or sanitized runtime evidence needed to confirm it.
- PRD references to `HOOK.yaml`, `handler.py`, `response_filter`, `template_card_dispatcher`, `wecom_template_card_shim`, `agent:end`, `gateway:startup`, `feedback.jsonl`, and `pending_previews.jsonl` are useful design inputs, not source-confirmed APIs.

## Phase 4 Go/No-Go Implications

Phase 4 production hook work must not proceed as source-confirmed until Hermes source/runtime evidence answers these items:

1. Whether `contract_result_recorder` can run after `response_filter` on the same `agent:end` event.
2. Whether a hidden inbound hook or stable session context can provide complete AgentTurn input.
3. Whether `message_id` is stable through preview storage, template card dispatch, callback payloads, and feedback rows.
4. Which Hermes runtime source maps each async state.
5. Which fields form the idempotency key for repeated feedback callbacks.
6. Where raw payload references point, who owns retention, and which redaction/minimization rules are enforced.
