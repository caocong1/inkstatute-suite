# Phase 03 Integration Risk Matrix

**Plan:** 03-01  
**Created:** 2026-06-27T18:24:49Z  
**Source:** V2 PRD section 13, Phase 03 context decisions D-01 through D-09, and `03-HERMES-SOURCE-INVENTORY.md`.

## Status Tags

Only these tags are used in the matrix:

- `confirmed`: Repo-local contract/schema/test evidence is sufficient for this contract-side decision.
- `assumed`: A provisional design assumption is recorded, but must be replaced by Hermes source/runtime evidence before production dependency.
- `requires Hermes source/runtime`: The decision depends on Hermes source, runtime logs, or sanitized callback/log samples that are not present in this repo.
- `deferred`: The item is real but intentionally belongs to a later phase or milestone.
- `blocked`: Production work must not proceed until the missing evidence or explicit fallback decision is supplied.

## Matrix

| Risk | Decision ID | Source Checked | Status | Evidence | Decision | Fallback | Phase 4 Impact |
|------|-------------|----------------|--------|----------|----------|----------|----------------|
| hook event ordering | D-01, D-02, D-03 | V2 PRD section 13 item 1; `03-HERMES-SOURCE-INVENTORY.md`; repo `rg`/`find` scans | blocked | PRD requires confirming whether `contract_result_recorder` runs after `response_filter`; repo has no Hermes hook loader/source. | Do not treat recorder-after-filter as confirmed. | Mount Hermes source/runtime and prove same-event order, or move recording inside/adjacent to `response_filter`. | Blocks production hook implementation until source/runtime evidence or fallback is selected. |
| inbound event absence | D-02, D-04 | V2 PRD section 13 item 2; inventory rows for `agent:end`, hidden inbound hooks, sessions | requires Hermes source/runtime | PRD says Hermes exposes `agent:end` and no `agent:start`; repo cannot inspect hidden inbound hooks. | AgentTurn input remains provisional and may need reverse inference from session/context. | Use `agent:end` context/session reverse inference and store missing raw input through `raw_payload_ref` references when available. | Phase 4 must include a source/runtime probe or accept documented incomplete AgentTurn fields. |
| message_id stability | D-02, D-05 | V2 PRD section 13 item 3; inventory rows for `message_id`, `response_filter`, callbacks | requires Hermes source/runtime | PRD says `response_filter` generates `message_id`; no implementation, preview row, card payload, or callback sample exists in repo. | Do not lock `feedback_target = message_id` as source-confirmed. | Derive `feedback_target` from confirmed runtime fields such as channel/session/message/card/callback identifiers after samples exist. | Blocks stable feedback association in Phase 4 until callback/preview evidence is supplied. |
| long-task state source | D-02, D-06 | V2 PRD section 13 item 4; `packages/platform-contract/src/platform_contract/enums.py`; inventory task/log rows | requires Hermes source/runtime | Contract enum values are confirmed; Hermes queue/session/task signals are absent. | Target states are `queued`, `running`, `waiting_for_user`, `succeeded`, `failed`, and `cancelled`; runtime mapping is not confirmed. | Mark unavailable states explicitly or derive them from confirmed runtime events only after source/log inspection. | Phase 4 mapper cannot claim complete async state coverage without Hermes task-state evidence. |
| response_filter and template card association | D-02, D-05 | V2 PRD section 13 item 5; inventory rows for `response_filter`, `template_card_dispatcher`, `pending_previews.jsonl` | requires Hermes source/runtime | PRD describes one feedback chain, but repo has no dispatcher source or preview data. | One response must produce one traceable `feedback_target`, but real field source is unconfirmed. | If multiple cards per reply exist, define a deterministic per-card association key and document aggregation behavior. | Phase 4 must verify card cardinality and association before writing production feedback links. |
| feedback idempotency | D-05 | V2 PRD section 13 item 6; inventory rows for callbacks and `feedback.jsonl`; contract `FeedbackEvent` schema | assumed | Contract can represent feedback; no callback-native id or repeated-click sample exists. | Prefer a callback-native stable id if present; otherwise derive an idempotency key from confirmed fields. | Use a documented derived key such as feedback target + action + user + callback timestamp bucket or raw payload hash reference, once real fields are known. | Phase 4/6 must not implement dedupe rules against invented callback fields. |
| raw payload storage | D-07 | V2 PRD section 13 item 7; AGENTS privacy rules; inventory rows for raw runtime artifacts | blocked | Repo has no Hermes raw payload store, retention policy, or runtime logs. AGENTS requires references and no sensitive full text by default. | Contract logs must store `raw_payload_ref` and minimal metadata, not raw sensitive payloads. | Block writer implementation until reference namespace, retention owner, and storage location are known. | Blocks Phase 4 writer defaults where raw source retention/reference cannot be named. |
| redaction | D-07 | V2 PRD section 13 item 8; AGENTS privacy rules; fixture privacy patterns | confirmed | Repo rules and fixtures already require references/minimization; no production payload redaction source exists. | Phase docs and fixtures must not embed sensitive full text, complete ID numbers, phones, bank accounts, addresses, secrets, or customer legal material. | If source redaction is unavailable, writer must omit sensitive fields and keep only references until redaction exists. | Phase 4 must implement conservative minimization even if coverage pressure exists. |
| simple QA route logs | D-04, D-06 | V2 PRD section 13 item 9; RouteDecision schema; inventory for router/session logs | requires Hermes source/runtime | `RouteDecision.mode` supports `simple_qa`, `skipped`, and `zero_match`; repo lacks Hermes router/simple-QA logs. | Simple QA route decisions cannot be source-confirmed locally. | Contract layer may generate a `skipped`/`simple_qa` RouteDecision only if Phase 03-03 documents the rule and Phase 4 confirms missing Hermes logs. | Phase 4 mapper must avoid inventing router evidence without a documented generated-record rule. |
| fixture representativeness | D-08 | V2 PRD section 13 item 10; contract-test-suite fixtures/tests; Phase 03 plans | confirmed | Existing harness validates synthetic fixtures; Plan 03-04 owns route error, long-task failure, repeated feedback, and non-legal fixtures. | Non-happy-path fixture coverage is required before Phase 3 closes. | Keep Phase 03-04 fixtures synthetic and schema-valid; do not use raw Hermes/customer data. | Does not block Plan 03-01, but Phase 3 remains incomplete until Plan 03-04 passes. |
| skill candidate safety | D-09 | V2 PRD section 13 item 11; AGENTS legal safety rules; contract `skill_candidate` fields | confirmed | AGENTS and PRD prohibit automatic legal skill modification; schemas can record candidate evidence. | V2 records `skill_candidate` only and requires human review for high-risk legal changes. | If feedback-service later sees route mismatch, queue it for human review and do not trigger automatic skillopt edits. | Phase 4 must preserve shadow-only behavior and never add automatic legal skill modification. |
| lawyer trial sample limitation | D-01 | V2 PRD section 13 item 12; Roadmap Phase 8 trial acceptance | deferred | Five workday / 15 task trial is an acceptance sample, not long-term legal quality proof. | Treat as Phase 8 acceptance evidence, not Phase 4 implementation evidence. | M2 should plan sustained evaluation after V2. | No Phase 4 blocker; carried as later validation scope. |
| multi-hook same-event order | D-01, D-02, D-03 | V2 PRD section 13 item 13; inventory rows for `agent:end`, `response_filter`, `HOOK.yaml`, `handler.py` | blocked | PRD says `agent:end` already has `admin_notice` and `response_filter`; repo has no hook scheduler/source to verify adding a third hook. | Do not deploy a separate same-event `contract_result_recorder` until hook order is source/runtime-confirmed. | Merge recording into/next to `response_filter` if Hermes cannot guarantee ordering. | Blocks Phase 4 separate-hook design until Plan 03-02 produces hook-order evidence. |

## D-01 Through D-09 Coverage

| Decision | Matrix Coverage | Status |
|----------|-----------------|--------|
| D-01 | Phase 3 is a spike, not production implementation; represented in hook ordering, lawyer trial limitation, and multi-hook rows. | confirmed |
| D-02 | Hermes source absence is first-class; represented in every `requires Hermes source/runtime` or `blocked` row. | confirmed |
| D-03 | Hook order must resolve `response_filter`; represented in hook event ordering and multi-hook same-event order rows. | blocked |
| D-04 | AgentTurn input strategy must be explicit; represented in inbound event absence and simple QA route logs rows. | requires Hermes source/runtime |
| D-05 | Feedback association must trace one target per response; represented in message_id stability, card association, and feedback idempotency rows. | requires Hermes source/runtime |
| D-06 | Long-task states must map to exact platform enum values; represented in long-task state source and simple QA route logs rows. | requires Hermes source/runtime |
| D-07 | Raw payload and privacy decisions block Phase 4; represented in raw payload storage and redaction rows. | blocked |
| D-08 | Non-happy-path fixtures are Phase 3 deliverables; represented in fixture representativeness row. | confirmed |
| D-09 | Automatic legal skill modification remains out of scope; represented in skill candidate safety row. | confirmed |

## Evidence Gaps Carried Forward

These gaps should be cited by Plan 03-02 and Plan 03-03 rather than silently closed:

1. Hermes hook loader and same-event ordering for `agent:end`, `admin_notice`, `response_filter`, and a possible `contract_result_recorder`.
2. Hidden inbound hook availability or complete session context for AgentTurn content and attachments.
3. Stable `message_id` propagation across `response_filter`, `pending_previews.jsonl`, template card dispatch, callback payloads, and `feedback.jsonl`.
4. Actual template card and callback payload fields, including a native callback id if one exists.
5. Long-task lifecycle signals for `queued`, `running`, `waiting_for_user`, `succeeded`, `failed`, and `cancelled`.
6. Raw payload reference namespace, retention owner, storage location, and redaction/minimization implementation.

## Phase 4 Gate

Production Hermes hook work remains `blocked` for separate recorder deployment while hook ordering and raw payload storage are unconfirmed. Phase 4 can proceed only after Plan 03-02 and Plan 03-03 either:

- attach Hermes source/runtime or sanitized probe evidence, or
- select and document a fallback that does not depend on unconfirmed source behavior.
