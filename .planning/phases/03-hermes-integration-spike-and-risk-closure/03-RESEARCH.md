# Phase 3: Hermes Integration Spike and Risk Closure - Research

**Researched:** 2026-06-28  
**Domain:** Hermes lawfirm hook/WeCom/feedback integration risk spike  
**Confidence:** MEDIUM - repository-local evidence is HIGH; Hermes runtime/source-dependent claims remain LOW until Hermes source or runtime artifacts are mounted.

## User Constraints

### From Phase 3 CONTEXT.md

Phase 3 closes the V2 implementation risks that would otherwise make Phase 4 hook work speculative. It must produce documented, testable decisions for Hermes hook ordering, AgentTurn input strategy, message and feedback association, long-task state mapping, idempotency, raw payload retention, and redaction. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]

The current repository does not contain the Hermes runtime source. Phase 3 must therefore be planned as an evidence-first spike using the available PRD, GSD state, contract schemas, contract-test-suite, and synthetic fixtures. If Hermes source is later added or mounted, Phase 3 plans should inspect it directly before finalizing decisions. Until then, Phase 3 outputs must mark Hermes-source-dependent assumptions explicitly. [VERIFIED: repo find/rg]

### Locked Decisions

- Phase 3 is a risk-closure spike, not production hook implementation. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]
- Hermes source absence is a first-class evidence gap. Source-dependent decisions must be recorded as `confirmed`, `assumed`, or `requires Hermes source`. [VERIFIED: repo find/rg]
- Hook order decision must resolve whether `contract_result_recorder` can run after `response_filter`; if not confirmed, Phase 4 must block or use an adjacent/inside-`response_filter` fallback. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]
- AgentTurn input strategy must be explicit: prefer a stable inbound hook/source; otherwise document `agent:end` reverse-inference limits. [CITED: docs/requirements/V2-PRD.md]
- Feedback association rules must produce one traceable target per response across `message_id`, `feedback_target`, template card id, callback payload, `result_id`, and `turn_id`. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]
- Long-task mapping must target exactly `queued`, `running`, `waiting_for_user`, `succeeded`, `failed`, and `cancelled`; unavailable states must be recorded as unavailable or derived. [VERIFIED: packages/platform-contract/src/platform_contract/enums.py]
- Raw payload and privacy decisions block Phase 4; contract logs must prefer `raw_payload_ref` and avoid sensitive full text by default. [CITED: AGENTS.md]
- Non-happy-path fixtures are Phase 3 deliverables: route errors, long-task failures, repeated feedback clicks, and at least one non-legal task. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]
- Automatic legal skill modification remains out of scope; route mismatch and skill candidates require human review. [CITED: AGENTS.md]

### the agent's Discretion

- Create an integration decision record that lists every V2 risk from PRD section 13 and marks it `confirmed`, `assumed`, `deferred`, or `blocked`. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]
- Add a source inventory/probe artifact recording whether this repository contains Hermes runtime hooks, WeCom callback shims, feedback JSONL examples, or long-task state sources. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]
- Add mapper rules as data/docs rather than production code: hook order, AgentTurn inference, result/feedback identifiers, async states, idempotency keys, raw payload refs, and redaction. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]
- Add non-happy-path fixtures under a Phase 3-owned fixture location and run them through `packages/contract-test-suite`. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]
- Keep all outputs stdlib/testable where code is needed; do not introduce package-manager dependencies. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]

### Deferred Ideas (OUT OF SCOPE)

- Production Hermes hook, mapper, writer, and event log persistence: Phase 4. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]
- WeCom end-to-end daily-use validation: Phase 5. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]
- Feedback-service normalization and pending queues: Phase 6. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]
- `.github` CI enforcement, real task 95% coverage, and broader privacy gates: Phase 7. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]
- Lawyer trial metrics: Phase 8. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]

### Project Constraints (from AGENTS.md)

- Use `docs/requirements/V2-PRD.md` as the active product source of truth; retired V1 must not return as an active requirement source. [CITED: AGENTS.md]
- Implement V2 as a thin platform contract layer around existing Hermes `lawfirm`; do not rebuild Hermes core, session storage, router, skill registry, MCP registry, model gateway, WeCom gateway, or feedback channel unless a later phase changes scope. [CITED: AGENTS.md]
- Preserve GSD gates and treat `.planning/STATE.md`, `.planning/ROADMAP.md`, and phase artifacts as persistent project memory. [CITED: AGENTS.md]
- Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads. [CITED: AGENTS.md]
- Contract logs should prefer references such as `raw_payload_ref` and must not store sensitive full text by default. [CITED: AGENTS.md]
- Legal-specific fields belong in `industry_context`; platform schemas must remain industry-neutral. [CITED: AGENTS.md]
- High-risk legal feedback must remain human-reviewed; V2 records `skill_candidate` and must not auto-synthesize or auto-modify legal conclusion skills. [CITED: AGENTS.md]
- Keep changes scoped to the active GSD phase and add tests before/with behavior changes, especially schemas, mappers, event ordering, dedupe, and fixture replay. [CITED: AGENTS.md]
- Prefer structured parsers and schema validators over ad hoc string parsing. [CITED: AGENTS.md]
- Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or active GSD plan requires it. [CITED: AGENTS.md]

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-implementation-risk-resolution | Resolve Hermes hook order, inbound turn strategy, message id stability, long-task states, feedback targets, idempotency, raw payload retention/redaction, non-happy-path fixtures, and skillopt safety before production Hermes hook work. [CITED: .planning/REQUIREMENTS.md] | This research maps each risk to available evidence, missing Hermes-source probes, Phase 3 plan slices, fixture deliverables, and Phase 4 blocking decisions. [VERIFIED: repo rg] |

</phase_requirements>

## Summary

The InkStatute repository currently contains PRD/planning evidence, platform contract schemas, synthetic fixtures, and a dependency-free contract test suite; it does not contain Hermes runtime/profile source, hook implementations, WeCom callback shim code, `feedback.jsonl`, `pending_previews.jsonl`, sessions databases, gateway code, or long-task runtime logs. [VERIFIED: repo find/rg]

Therefore Phase 3 should be planned as a documentation-plus-fixture integration spike against available specs, with explicit external probes for Hermes source/runtime artifacts. The highest-risk Phase 4 blockers are hook ordering after `response_filter`, stable message/feedback association across template cards and callbacks, and long-task state observability. [CITED: docs/requirements/V2-PRD.md]

**Primary recommendation:** Produce Phase 3 artifacts that make unknowns impossible to hide: a source inventory, a risk decision matrix, association/state/redaction decision tables, and non-happy-path fixtures validated by `packages/contract-test-suite`. [VERIFIED: packages/contract-test-suite/README.md]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Hermes hook order discovery | API / Backend | Filesystem/runtime probe | Hook registration/execution belongs to Hermes backend; InkStatute can only document/probe without changing Hermes core. [CITED: docs/requirements/V2-PRD.md] |
| AgentTurn input reconstruction | API / Backend | Database / Storage fallback | PRD says no `agent:start` is currently exposed, so input may need `agent:end` context/session fallback. [CITED: docs/requirements/V2-PRD.md] |
| Message/feedback association | API / Backend | WeCom gateway | `message_id`/template-card/callback data originates in Hermes/WeCom hook chain; contract layer records identifiers but should not own gateway behavior. [CITED: docs/requirements/V2-PRD.md] |
| Long-task state mapping | API / Backend | Database / Storage | Runtime/task lifecycle signals are backend/runtime facts; contract enum is already defined in platform-contract. [VERIFIED: packages/platform-contract/src/platform_contract/enums.py] |
| Feedback idempotency and classification rules | API / Backend | Database / Storage | Phase 3 should define rules; Phase 6 implements feedback-service processing. [CITED: .planning/ROADMAP.md] |
| Raw payload references/redaction | API / Backend | Database / Storage | Contract logs must store references/minimized payloads; raw payload storage/retention depends on runtime artifact location. [CITED: AGENTS.md] |
| Non-happy-path fixtures | Contract test tier | API / Backend | Fixtures belong to schema/replay validation and inform Phase 4 mapper behavior. [VERIFIED: packages/contract-test-suite/README.md] |

## Phase Boundary and Non-Goals

Phase 3 owns evidence and decisions, not production integration. It may create phase docs, probe scripts/specs, decision tables, and validated non-happy-path fixtures. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]

Phase 3 must not implement production `contract_result_recorder`, Hermes mapper/writer persistence, feedback-service normalization, conversation-read-view APIs, WeCom gateway changes, `.github` workflows, runtime databases, queues, or automatic legal skill modification. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]

If Hermes source remains absent, Phase 3 can only close decisions that are contract-side or documentation-side; Hermes-source-dependent decisions must remain `requires Hermes source/runtime` and block Phase 4 implementation until probed. [VERIFIED: repo find/rg]

## Existing Code/Doc Evidence by Focus Area

### Hermes Hook System and Hook Ordering

| Evidence | Finding | Confidence |
|----------|---------|------------|
| PRD states Hermes hooks use `HOOK.yaml` plus `handler.py`, with existing `agent:end` and `gateway:startup` events; `agent:end` context includes `response/platform/user_id/chat_id/session_id/active_skill_name`, and hooks can write back to context. [CITED: docs/requirements/V2-PRD.md] | This is the only available description of Hermes hook API in this repo. | MEDIUM |
| PRD states existing feedback chain is `response_filter` -> `pending_previews.jsonl` -> `template_card_dispatcher` -> template card -> `wecom_template_card_shim` -> `feedback/feedback.jsonl`. [CITED: docs/requirements/V2-PRD.md] | Chain is documented but not source-verified in this repo. | MEDIUM |
| Repository `rg`/`find` found no Hermes hook source, no `HOOK.yaml`, no `handler.py`, no `response_filter`, no `template_card_dispatcher`, and no `wecom_template_card_shim` implementation. [VERIFIED: repo find/rg] | Hook ordering cannot be confirmed locally. | HIGH |
| PRD explicitly identifies same-event hook order as a risk and fallback possibility: record inside/adjacent to `response_filter` if stable ordering cannot be confirmed. [CITED: docs/requirements/V2-PRD.md] | Phase 3 must make this a blocking Phase 4 decision. | HIGH |

**Research conclusion:** Plan a Phase 3 source/runtime probe for Hermes hook order. Until probed, `contract_result_recorder after response_filter` is an intended design, not a confirmed fact. [VERIFIED: repo find/rg]

### `message_id` Stability and Feedback Target Association

| Evidence | Finding | Confidence |
|----------|---------|------------|
| PRD says `response_filter` generates `message_id` and writes it back to context. [CITED: docs/requirements/V2-PRD.md] | `message_id` generation is documented but not locally source-verified. | MEDIUM |
| PRD requires confirming whether this ID is stable across Hermes, WeCom, feedback card, and callback mapping. [CITED: docs/requirements/V2-PRD.md] | Stability is an open risk, not a closed decision. | HIGH |
| Platform schemas and fixtures already support `AgentResult.feedback_target` and `FeedbackEvent.feedback_target`, and relationship replay checks them. [VERIFIED: packages/platform-contract/src/platform_contract/events.py; packages/contract-test-suite/src/contract_test_suite/fixture_replay.py] | Contract-side association field exists and is tested on synthetic fixtures. | HIGH |
| No local callback payload samples, template card payloads, `feedback.jsonl`, or `pending_previews.jsonl` exist in repo. [VERIFIED: repo find/rg] | Real association fields must be captured from Hermes runtime/source before Phase 4. | HIGH |

**Recommended association rule:** Use `feedback_target = message_id` only if Hermes source/runtime confirms the same value is embedded in template card callback payload and preview storage. Otherwise define `feedback_target` as a derived stable key from confirmed fields, for example `{channel}:{session_id}:{message_id}:{card_id}`. [ASSUMED]

### Long-Task State Sources

| Evidence | Finding | Confidence |
|----------|---------|------------|
| Platform enum defines exact states `queued`, `running`, `waiting_for_user`, `succeeded`, `failed`, `cancelled`. [VERIFIED: packages/platform-contract/src/platform_contract/enums.py] | Target contract vocabulary is locked. | HIGH |
| PRD requires WeCom 5s ACK plus async completion push for long tasks. [CITED: docs/requirements/V2-PRD.md] | Product behavior is specified, but runtime source is absent. | MEDIUM |
| Repository contains no long-task runtime code, queue, task logs, sessions database, gateway source, or Hermes status samples. [VERIFIED: repo find/rg] | Source mapping cannot be confirmed locally. | HIGH |
| Existing synthetic fixtures use execution trace `steps[].state` values like `succeeded`; they do not cover `queued`, `running`, `waiting_for_user`, `failed`, or `cancelled`. [VERIFIED: packages/platform-contract/fixtures/*.json] | Phase 3 fixture gaps remain. | HIGH |

**Proposed mapping to validate in Hermes source/runtime:** queued = accepted before execution; running = active skill/tool execution; waiting_for_user = clarification gate pending; succeeded = final response/artifact sent; failed = runtime/channel/contract error terminal; cancelled = explicit user/operator cancellation or timeout-cancel event. [ASSUMED]

### Feedback Callback Data and Idempotency Signals

| Evidence | Finding | Confidence |
|----------|---------|------------|
| FeedbackEvent schema supports `feedback_id`, `turn_id`, `result_id`, `conversation_id`, `user_id`, `source`, `event_type`, `action`, `feedback_target`, `related_skill`, `related_route_decision`, `status`, and `raw_payload_ref`. [VERIFIED: packages/platform-contract/src/platform_contract/events.py] | Contract can represent callback association and dedupe outputs. | HIGH |
| PRD requires dedupe for repeated button clicks, network retries, and repeated shim writes. [CITED: docs/requirements/V2-PRD.md] | Idempotency is a required decision. | HIGH |
| No real callback payload samples or `feedback.jsonl` exist in this repo. [VERIFIED: repo find/rg] | Idempotency key cannot be confirmed from real fields. | HIGH |

**Recommended idempotency strategy:** Prefer a callback-native stable ID if Hermes/WeCom provides one; otherwise derive a key from confirmed callback fields in this order: `callback_event_id`, `feedback_target + action + user_id + created_at_bucket`, or `raw_payload_hash` stored as metadata while keeping raw payload by reference only. [ASSUMED]

### Raw Payload Storage, Retention, and Redaction

| Evidence | Finding | Confidence |
|----------|---------|------------|
| AGENTS and PRD require contract logs to prefer `raw_payload_ref` and avoid sensitive full text by default. [CITED: AGENTS.md; docs/requirements/V2-PRD.md] | Privacy boundary is locked. | HIGH |
| Fixture README states synthetic fixtures are not production logs/legal documents/customer records/Hermes runtime data, and raw/sensitive data should be represented by references. [VERIFIED: packages/platform-contract/fixtures/README.md] | Fixture privacy pattern is established. | HIGH |
| No Hermes raw payload storage implementation, retention policy, redaction implementation, or runtime log samples are present in repo. [VERIFIED: repo find/rg] | Retention/redaction cannot be source-confirmed locally. | HIGH |

**Minimum Phase 3 decision:** `raw_payload_ref` may point to runtime-owned source records, but Phase 4 contract logs must never embed full legal document text, full callback raw payload, secrets, complete ID numbers, full phone numbers, bank accounts, or addresses by default. [CITED: AGENTS.md]

### Non-Happy-Path Fixture/Spec Locations

| Evidence | Finding | Confidence |
|----------|---------|------------|
| Platform fixtures live under `packages/platform-contract/fixtures/` and are synthetic, relationship-focused golden examples. [VERIFIED: packages/platform-contract/fixtures/README.md] | Keep stable contract examples here only if they are broadly useful to platform-contract. | HIGH |
| Contract-test-suite local fixtures live under `packages/contract-test-suite/fixtures/`; package README says Phase 3/4 own real Hermes output replay and hook/adaptor work. [VERIFIED: packages/contract-test-suite/README.md] | Phase 3 non-happy-path fixtures should be accepted by this harness and can live under test-suite or phase-owned fixtures. | HIGH |
| Phase-specific planning artifacts live under `.planning/phases/03-hermes-integration-spike-and-risk-closure/`. [VERIFIED: find .planning/phases] | Risk matrices/probe specs belong here. | HIGH |

**Recommendation:** Put Phase 3 decision docs/probe specs under `.planning/phases/03-hermes-integration-spike-and-risk-closure/`; put reusable schema-valid non-happy-path JSON fixtures under `packages/contract-test-suite/fixtures/` only if Phase 3 includes test harness updates to load them; otherwise keep spike-only examples under the phase directory and make Phase 4/7 promote them. [VERIFIED: packages/contract-test-suite/README.md]

## Standard Stack

### Core

| Library/Tool | Version | Purpose | Why Standard |
|--------------|---------|---------|--------------|
| Python stdlib `unittest/json/pathlib` | Python 3.14.6 available locally | Existing contract-test-suite execution and fixture validation | Phase 2 deliberately kept the suite dependency-free. [VERIFIED: packages/contract-test-suite/README.md; env probe] |
| `packages/platform-contract` | local package | Source of contract schemas, enums, Python dataclasses, and fixtures | Phase 1 verified this as the pure definition package. [VERIFIED: .planning/phases/01-platform-contract-foundation/01-VERIFICATION.md] |
| `packages/contract-test-suite` | local package | Schema validation, replay, relationship integrity, composability fixtures | Phase 2 verified this as the local harness Phase 3 can reuse. [VERIFIED: .planning/phases/02-contract-test-suite-foundation/02-VERIFICATION.md] |
| `rg` | ripgrep 15.1.0 | Source inventory and evidence scans | Required by user focus and fastest local search tool. [VERIFIED: env probe] |
| `find` | GNU findutils 4.10.0 | File inventory | Used to prove Hermes runtime/source absence. [VERIFIED: env probe] |

### Supporting

| Library/Tool | Version | Purpose | When to Use |
|--------------|---------|---------|-------------|
| Markdown phase artifacts | n/a | Risk matrices, probe specs, decision records | Use for Phase 3 deliverables that should not be production code. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md] |
| JSON fixtures | Draft/schema validated by local harness | Non-happy-path examples | Use for route mismatch, long-task failure, repeated feedback callback, and non-legal task examples. [VERIFIED: packages/contract-test-suite/README.md] |

**Installation:** No external package installation is recommended for Phase 3. [VERIFIED: AGENTS.md]

## Package Legitimacy Audit

No external packages should be installed for this phase. `slopcheck` is not required because the recommended stack uses existing local packages and Python standard library only. [VERIFIED: packages/contract-test-suite/README.md]

## Architecture Patterns

### System Architecture Diagram

```text
Available evidence in this repo
  -> PRD / AGENTS / GSD context
  -> platform-contract schemas + fixtures
  -> contract-test-suite replay checks
  -> Phase 3 research/planning artifacts

Missing Hermes evidence
  -> Hermes hook source / runtime profile
  -> response_filter / template_card_dispatcher / wecom_template_card_shim
  -> pending_previews.jsonl / feedback.jsonl / callback samples
  -> sessions / gateway / long-task logs

Phase 3 flow
  repo inventory
    -> risk decision matrix
      -> association/state/redaction tables
        -> non-happy-path fixtures
          -> contract-test-suite validation
            -> Phase 4 go/no-go decisions
```

### Recommended Project Structure

```text
.planning/phases/03-hermes-integration-spike-and-risk-closure/
├── 03-RESEARCH.md                         # this file
├── 03-INTEGRATION-RISK-MATRIX.md          # recommended Phase 3 output
├── 03-HERMES-SOURCE-INVENTORY.md          # recommended Phase 3 output
├── 03-IDENTIFIER-STATE-PRIVACY-RULES.md   # recommended Phase 3 output
└── fixtures/                              # optional spike-only examples if not promoted

packages/contract-test-suite/fixtures/
└── *.json                                 # reusable schema-valid non-happy-path fixtures
```

### Pattern 1: Evidence Matrix Before Implementation

**What:** Every Hermes-dependent decision records source, status, confidence, fallback, and Phase 4 blocking effect. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]

**When to use:** Hook order, message id, callback fields, long-task state sources, raw payload storage, retention, and skillopt safety. [CITED: docs/requirements/V2-PRD.md]

**Example:**

```markdown
| Risk | Source Checked | Status | Decision | Phase 4 Impact |
|------|----------------|--------|----------|----------------|
| Hook order after response_filter | repo rg: absent; Hermes source: pending | requires Hermes source | Block production hook until confirmed | Phase 4 checkpoint |
```

### Pattern 2: Fixture-First Spike Closure

**What:** Represent non-happy paths as schema-valid event bundles before writing production hooks. [VERIFIED: packages/contract-test-suite/README.md]

**When to use:** Route mismatch, long-task failure, repeated callback dedupe, non-legal task, waiting-for-user clarification, channel error. [CITED: .planning/REQUIREMENTS.md]

**Example command:**

```bash
cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py
```

### Anti-Patterns to Avoid

- **Inventing Hermes APIs from PRD prose:** PRD documents desired/observed behavior but this repo has no Hermes source to verify call signatures or callback fields. [VERIFIED: repo find/rg]
- **Treating `message_id` as stable before callback proof:** Stability across response filter, card dispatch, and callback is a known open risk. [CITED: docs/requirements/V2-PRD.md]
- **Approximating missing async states silently:** If Hermes has no signal for a platform state, mark it unavailable or derived. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]
- **Putting raw legal payloads into fixtures/log examples:** Existing fixture policy requires synthetic data and references. [VERIFIED: packages/platform-contract/fixtures/README.md]
- **Triggering skillopt/legal modifications from feedback research:** V2 only records `skill_candidate`; high-risk legal changes require human review. [CITED: AGENTS.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema validation | New validator/parser | Existing `contract-test-suite` validator | Already verified in Phase 2 and consumes platform schemas. [VERIFIED: .planning/phases/02-contract-test-suite-foundation/02-VERIFICATION.md] |
| Contract enums/types | New copied enum lists | `packages/platform-contract` | Avoid drift from Phase 1 verified contract definitions. [VERIFIED: .planning/phases/01-platform-contract-foundation/01-VERIFICATION.md] |
| Hermes gateway/feedback channel | New gateway/shim | Existing Hermes chain once source/runtime is available | AGENTS forbids rebuilding Hermes gateway/feedback channel. [CITED: AGENTS.md] |
| Runtime persistence | New database/queue | Phase docs and existing fixture harness | Phase 3 is risk closure, not runtime implementation. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md] |
| Legal skill update automation | Auto skill modification | Human-reviewed `skill_candidate` records only | Legal safety rule is locked. [CITED: AGENTS.md] |

## Decisions Needed Before Phase 4

| Decision | Current Evidence | Required Closure |
|----------|------------------|------------------|
| Can `contract_result_recorder` run after `response_filter`? | PRD says this is desired; repo lacks Hermes hook source. [CITED: docs/requirements/V2-PRD.md; VERIFIED: repo find/rg] | Inspect Hermes hook loader/order or run a local hook-order probe. |
| Is there an inbound hook or stable source for AgentTurn input? | PRD says only `agent:end`/`gateway:startup` are currently exposed. [CITED: docs/requirements/V2-PRD.md] | Confirm from Hermes source; otherwise document exact reverse-inference gaps. |
| What is the canonical `feedback_target`? | Contract has field; real `message_id`/card/callback source absent. [VERIFIED: packages/platform-contract/src/platform_contract/events.py; repo find/rg] | Confirm callback payload includes stable response identifier or define derived key from real fields. |
| How do Hermes long-task signals map to async states? | Contract enum exists; Hermes source/logs absent. [VERIFIED: packages/platform-contract/src/platform_contract/enums.py; repo find/rg] | Identify source/log field for each state or mark unsupported/derived. |
| What idempotency key dedupes repeated callbacks? | Requirement exists; real payload absent. [CITED: .planning/REQUIREMENTS.md; VERIFIED: repo find/rg] | Choose native event id or derived key after callback sample inspection. |
| Where do raw payload refs point and how long are they retained? | Privacy requirement exists; storage policy absent. [CITED: AGENTS.md; VERIFIED: repo find/rg] | Define reference namespace, retention owner, redaction minimum, and non-storage defaults. |
| How is skillopt safety enforced? | V2 prohibits auto legal skill modification; actual skillopt source absent. [CITED: AGENTS.md; VERIFIED: repo find/rg] | Confirm Phase 6/feedback-service cannot call skillopt automatically; record manual-only queue boundary. |

## Recommended Phase 3 Plan Slices

1. **Source Inventory and Evidence Ledger**: create a phase artifact showing repo scan commands/results, Hermes source absence, and exact files checked. [VERIFIED: repo find/rg]
2. **Hook Order and AgentTurn Probe Spec**: define the Hermes source/runtime probe needed to confirm `agent:end`, `gateway:startup`, hidden inbound hooks, context fields, and same-event ordering. [CITED: docs/requirements/V2-PRD.md]
3. **Identifier and Feedback Association Rules**: document candidate mappings among `message_id`, `feedback_target`, `result_id`, `turn_id`, template card id, callback id, `pending_previews.jsonl`, and `feedback.jsonl`; mark unconfirmed fields. [CITED: .planning/REQUIREMENTS.md]
4. **Async State Mapping Rules**: map confirmed/derived/unavailable Hermes signals to `queued/running/waiting_for_user/succeeded/failed/cancelled`; add fixture examples for failure and waiting. [VERIFIED: packages/platform-contract/src/platform_contract/enums.py]
5. **Privacy and Raw Payload Policy**: define `raw_payload_ref` namespace, forbidden inline fields, redaction minimums, and retention assumptions; keep legal payloads out of fixtures. [CITED: AGENTS.md]
6. **Non-Happy-Path Fixtures**: add route mismatch, long-task failure, repeated feedback callback, and non-legal examples, then run `packages/contract-test-suite` locally. [VERIFIED: packages/contract-test-suite/README.md]

## Risks, Open Gaps, and Verification Commands/Probes

| Risk / Gap | Impact | Verification Command or Probe |
|------------|--------|-------------------------------|
| Hermes source absent from repo | Hook order, context fields, callbacks, and long-task states cannot be confirmed locally. [VERIFIED: repo find/rg] | `find . -maxdepth 4 -type f \( -iname '*hermes*' -o -iname '*hook*' -o -iname '*wecom*' \) -print` |
| Hook order unknown | Phase 4 might record unfiltered/admin-only response text. [CITED: docs/requirements/V2-PRD.md] | In Hermes source/runtime: add temporary order probe hooks on `agent:end` and inspect context before/after `response_filter`. [ASSUMED] |
| AgentTurn input may be incomplete | Contract coverage and replay may lack original user text/attachments. [CITED: docs/requirements/V2-PRD.md] | Inspect Hermes context/session object at `agent:end`; check whether last inbound message and attachment refs are present. [ASSUMED] |
| Feedback callback fields unknown | Dedupe and association may be wrong. [VERIFIED: repo find/rg] | Capture one sanitized template-card callback payload and one `feedback.jsonl` row, then map fields to `FeedbackEvent`. [ASSUMED] |
| Long-task cancellation/waiting states may have no source | Async state coverage may be incomplete. [VERIFIED: repo find/rg] | Inspect Hermes long-task queue/log/session state and force clarification/failure/cancel scenarios. [ASSUMED] |
| Raw payload retention unknown | Contract logs could over-store sensitive legal data or lose traceability. [CITED: AGENTS.md] | Locate Hermes raw payload/log stores and document retention/redaction owner before Phase 4. [ASSUMED] |
| Non-happy-path fixtures missing | Phase 4 mapper may only handle happy paths. [VERIFIED: packages/platform-contract/fixtures/*.json] | `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py` |

## Code Examples

### Existing Fixture Relationship Check

```python
# Source: packages/contract-test-suite/src/contract_test_suite/fixture_replay.py
report = assert_relationship_integrity(max_breakage_rate=0.05)
```

This validates that fixture events share `turn_id`, feedback links match `result_id` and `feedback_target`, route decisions connect, and artifacts are referenced by execution traces. [VERIFIED: packages/contract-test-suite/src/contract_test_suite/fixture_replay.py]

### Existing Contract Test Command

```bash
cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py
```

This command passed locally during research: 21 tests ran successfully. [VERIFIED: local command]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Rebuild platform backend and feedback loop | Thin contract layer around Hermes lawfirm | V2 PRD dated 2026-06-27 | Phase 3 must resolve integration risks without rebuilding Hermes systems. [CITED: docs/requirements/V2-PRD.md] |
| Treat fixtures as happy-path schema examples only | Use fixture replay for relationships and composability | Phase 1/2 completed 2026-06-27 | Phase 3 should add non-happy-path examples through same harness. [VERIFIED: .planning/phases/02-contract-test-suite-foundation/02-VERIFICATION.md] |
| Store raw payload content in logs | Prefer `raw_payload_ref` and minimized fields | V2 PRD / AGENTS | Phase 4 writer must default to references, not raw legal text. [CITED: AGENTS.md] |

**Deprecated/outdated:**
- V1 platform rebuild scope is retired and must not be used as Phase 3 authority. [CITED: AGENTS.md]
- Building new Hermes core/gateway/session/feedback components is out of scope for V2/Phase 3. [CITED: AGENTS.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `feedback_target` may be derived from `{channel}:{session_id}:{message_id}:{card_id}` if `message_id` alone is not stable. | Message ID Stability | Could overcomplicate association or fail if card_id/session_id is unavailable. |
| A2 | Long-task states can be mapped from accepted/executing/clarification/final/error/cancel runtime events. | Long-Task State Sources | Could misrepresent Hermes if it lacks those lifecycle signals. |
| A3 | Callback idempotency can use native callback ID, derived fields, or raw payload hash. | Feedback Callback Data | Could dedupe too aggressively or not enough if callback payload fields differ. |
| A4 | Temporary hook-order probes can be safely run in a Hermes dev/runtime environment. | Risks / Probes | Could be unavailable if Hermes does not support dev hook injection. |

## Open Questions

1. **Where is Hermes source/runtime mounted for Phase 3 execution?**
   - What we know: This repo does not contain it. [VERIFIED: repo find/rg]
   - What's unclear: Whether planner/executor will have access to a sibling Hermes checkout or `~/.hermes/profiles/lawfirm`. [ASSUMED]
   - Recommendation: Add a Phase 3 checkpoint before claiming hook order/message stability as confirmed.
2. **Does Hermes callback payload include a stable message or card identifier?**
   - What we know: PRD says `message_id` exists and callbacks reach `feedback.jsonl`. [CITED: docs/requirements/V2-PRD.md]
   - What's unclear: Actual callback payload field names and whether repeated clicks preserve same identifier. [VERIFIED: repo find/rg]
   - Recommendation: Require one sanitized callback sample and one preview row before locking idempotency.
3. **What states are directly observable for long tasks?**
   - What we know: Platform enum is locked. [VERIFIED: packages/platform-contract/src/platform_contract/enums.py]
   - What's unclear: Hermes source/log signals for queued/waiting/cancelled. [VERIFIED: repo find/rg]
   - Recommendation: Mark each mapping `confirmed`, `derived`, or `unavailable` in Phase 3.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `rg` | repo evidence scan | yes | ripgrep 15.1.0 | `find` plus `grep` if needed. [VERIFIED: env probe] |
| `find` | source inventory | yes | GNU findutils 4.10.0 | `rg --files` for file listing. [VERIFIED: env probe] |
| `python` | contract tests | yes | Python 3.14.6 | `python3` also Python 3.14.6. [VERIFIED: env probe] |
| `gsd-tools` | GSD phase init/context | yes | command available | Node script fallback exists in gsd-core. [VERIFIED: env probe] |
| Hermes runtime/source | hook/callback/state proof | no, not in repo | n/a | Phase 3 must record gap or mount external source/runtime. [VERIFIED: repo find/rg] |

**Missing dependencies with no fallback:**
- Hermes runtime/source for confirming hook order, callback payload fields, and long-task state sources. Documentation-only fallback can produce provisional decisions but cannot fully unblock Phase 4 production hooks. [VERIFIED: repo find/rg]

**Missing dependencies with fallback:**
- None for repo-local fixture/test research. [VERIFIED: local command]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Python stdlib `unittest` through `packages/contract-test-suite`. [VERIFIED: packages/contract-test-suite/README.md] |
| Config file | none - package-local runner uses unittest discovery. [VERIFIED: packages/contract-test-suite/scripts/run_contract_tests.py] |
| Quick run command | `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py` |
| Full suite command | Same as quick run for Phase 3 unless extra fixture files/tests are added. [VERIFIED: packages/contract-test-suite/README.md] |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| REQ-implementation-risk-resolution | Non-happy-path fixtures remain schema-valid and relationship-linked | unit/fixture replay | `cd packages/contract-test-suite && PYTHONPATH=src:../platform-contract/src python scripts/run_contract_tests.py` | yes for harness; new fixtures are Wave 0 gap. [VERIFIED: local command] |
| REQ-implementation-risk-resolution | Hermes source inventory records evidence gaps | doc/probe | `rg -n "response_filter|template_card|wecom_template_card_shim|message_id|feedback|long_task|agent:end" -S .` | Wave 0 artifact gap. [VERIFIED: repo rg] |
| REQ-implementation-risk-resolution | Hook order/message/state decisions are status-tagged | manual/document review | Review Phase 3 risk matrix | Wave 0 artifact gap. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md] |

### Sampling Rate

- **Per task commit:** run contract-test-suite if JSON fixtures or harness docs change. [VERIFIED: packages/contract-test-suite/README.md]
- **Per wave merge:** run contract-test-suite plus rerun repo inventory `rg` command. [VERIFIED: local command]
- **Phase gate:** Phase 3 docs must mark every Hermes-dependent risk as `confirmed`, `requires Hermes source/runtime`, `deferred`, or `blocked`; no silent assumptions. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]

### Wave 0 Gaps

- [ ] `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-HERMES-SOURCE-INVENTORY.md` - records source/runtime absence or mounted evidence. [VERIFIED: repo find/rg]
- [ ] `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-INTEGRATION-RISK-MATRIX.md` - status-tags all PRD section 13 risks. [CITED: docs/requirements/V2-PRD.md]
- [ ] `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-IDENTIFIER-STATE-PRIVACY-RULES.md` - locks provisional rules and marks unconfirmed fields. [CITED: .planning/REQUIREMENTS.md]
- [ ] Non-happy-path fixtures/tests for route mismatch, long-task failure, repeated feedback click, and one non-legal task. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no direct Phase 3 implementation | Do not alter Hermes auth/channel behavior. [CITED: AGENTS.md] |
| V3 Session Management | yes, as evidence mapping only | Treat Hermes sessions as fallback read model, not new authority. [CITED: docs/requirements/V2-PRD.md] |
| V4 Access Control | yes, privacy/admin boundary | Preserve `response_filter` admin notice stripping expectation; do not expose admin-only notices in contract logs. [CITED: docs/requirements/V2-PRD.md] |
| V5 Input Validation | yes | Validate fixtures through platform schemas and contract-test-suite. [VERIFIED: packages/contract-test-suite/README.md] |
| V6 Cryptography | no direct Phase 3 implementation | Do not add new secret storage or crypto; use references/env/Hermes existing mechanisms. [CITED: AGENTS.md] |
| V8 Data Protection | yes | Use `raw_payload_ref`, synthetic fixtures, and redaction/minimization defaults. [CITED: AGENTS.md] |

### Known Threat Patterns for Phase 3

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Sensitive legal payload embedded in logs/fixtures | Information Disclosure | Use `fixture://` and `raw_payload_ref`; ban full legal/customer text by default. [VERIFIED: packages/platform-contract/fixtures/README.md] |
| Recording unfiltered/admin response due to hook order | Information Disclosure | Confirm hook order or block Phase 4; fallback inside/adjacent to `response_filter`. [CITED: docs/requirements/V2-PRD.md] |
| Duplicate feedback callback creates multiple actions | Tampering/Repudiation | Define idempotency key before feedback-service implementation. [CITED: .planning/REQUIREMENTS.md] |
| Auto-modification of legal conclusion skill | Elevation of Privilege/Tampering | Keep `skill_candidate.requires_human_review=true`; no automatic skillopt trigger. [CITED: AGENTS.md] |

## Canonical Files to Read During Planning/Execution

- `AGENTS.md` - project constraints and safety rules. [CITED: AGENTS.md]
- `docs/requirements/V2-PRD.md` - active product spec, especially sections 4.4, 4.6, 6, 7, 10, 12, and 13. [CITED: docs/requirements/V2-PRD.md]
- `.planning/PROJECT.md` - thin contract boundary and project decisions. [CITED: .planning/PROJECT.md]
- `.planning/REQUIREMENTS.md` - `REQ-implementation-risk-resolution`. [CITED: .planning/REQUIREMENTS.md]
- `.planning/ROADMAP.md` - Phase 3 success criteria and Phase 4-8 boundaries. [CITED: .planning/ROADMAP.md]
- `.planning/STATE.md` - current phase status and accumulated decisions. [CITED: .planning/STATE.md]
- `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md` - locked Phase 3 decisions and scope fence. [CITED: .planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md]
- `packages/platform-contract/src/platform_contract/enums.py` and `events.py` - contract enum/dataclass surface. [VERIFIED: repo file read]
- `packages/platform-contract/fixtures/README.md` and `packages/platform-contract/fixtures/*.json` - fixture relationship/privacy patterns. [VERIFIED: repo file read]
- `packages/contract-test-suite/README.md` and `packages/contract-test-suite/src/contract_test_suite/fixture_replay.py` - replay and validation harness. [VERIFIED: repo file read]

## Sources

### Primary (HIGH confidence)

- `AGENTS.md` - project constraints, privacy, scope, and coding rules. [CITED]
- `docs/requirements/V2-PRD.md` - active V2 PRD and Hermes integration risk list. [CITED]
- `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/phases/03-hermes-integration-spike-and-risk-closure/03-CONTEXT.md` - GSD project and phase state. [CITED]
- `packages/platform-contract/src/platform_contract/enums.py`, `events.py`, `fixtures/README.md`, `fixtures/*.json` - verified contract surface and existing fixtures. [VERIFIED]
- `packages/contract-test-suite/README.md`, `src/contract_test_suite/fixture_replay.py`, local command output - verified validation harness. [VERIFIED]
- Repository `rg`/`find` scans - verified absence of Hermes runtime/profile source and runtime artifacts in this repo. [VERIFIED]

### Secondary (MEDIUM confidence)

- PRD descriptions of existing Hermes hook chain, `message_id` behavior, and context fields. These are product/spec evidence but not source-confirmed in this repo. [CITED: docs/requirements/V2-PRD.md]

### Tertiary (LOW confidence)

- Proposed derived association/idempotency/state mappings until Hermes source/runtime payloads are inspected. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - uses existing local packages and stdlib only. [VERIFIED: packages/contract-test-suite/README.md]
- Architecture: MEDIUM - contract-side boundaries are verified; Hermes source/runtime tier details are not locally available. [VERIFIED: repo find/rg]
- Pitfalls: HIGH for scope/privacy risks from PRD/AGENTS; LOW for exact Hermes hook/callback mechanics until runtime/source probe. [CITED: AGENTS.md; docs/requirements/V2-PRD.md]

**Research date:** 2026-06-28  
**Valid until:** 2026-07-05 for Hermes runtime assumptions; 2026-07-28 for repository-local contract/test-suite facts.
