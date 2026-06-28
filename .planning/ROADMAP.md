# Roadmap: 墨律 InkStatute

## Overview

V2 moves from contract definitions to verified production shadow recording, then to InkStatute-owned WeCom service plus agent-adapter hardening, services, CI gates, and real lawyer acceptance. The phase order follows the V2 PRD development order, with an explicit Hermes integration spike before production hook work and a Phase 5.5 insertion so WeCom ingress/egress belongs to InkStatute, Hermes remains a low-coupling agent backend, and ordinary WeCom users never see Hermes meta/gateway/update/command notices.

**Granularity:** fine - chosen to preserve the V2 PRD development order and the required spike, CI, and trial acceptance boundaries.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work.
- Decimal phases (2.1, 2.2): Urgent insertions after planning.

- [x] **Phase 1: Platform Contract Foundation** - Define the pure contract package, schemas, async states, errors, fixtures, and Python-first bindings. (completed 2026-06-27)
- [x] **Phase 2: Contract Test Suite Foundation** - Establish schema validation, fixture replay, relationship checks, and CI-ready harness before Hermes hook work. (completed 2026-06-27)
- [x] **Phase 3: Hermes Integration Spike and Risk Closure** - Resolve hook, message, long-task, feedback, idempotency, fixture, and privacy risks before production hooks. (completed 2026-06-28)
- [x] **Phase 4: Hermes Shadow Event Layer** - Add the non-invasive hook, mapper, and writer that record standard contract events without changing Hermes legal/business behavior. (completed 2026-06-28)
- [x] **Phase 5: WeCom Shadow Loop Validation** - Prove the existing WeCom daily loop still works while contract events and feedback are captured. (completed 2026-06-28)
- [x] **Phase 5.5: InkStatute WeCom Service and Hermes Agent Adapter** - Build the WeCom receive/send service, define the agent backend adapter contract, make Hermes mode reproducible, and enforce a pure lawyer-assistant WeCom boundary. (completed 2026-06-28)
- [x] **Phase 6: Read and Feedback Service APIs** - Deliver read-only conversation/task/feedback APIs plus feedback normalization, dedupe, classification, and pending queues. (completed 2026-06-28)
- [x] **Phase 7: CI, Composability, and Privacy Gates** - Enforce industry-neutral composability, coverage, relationship integrity, thin-layer boundaries, and safety baselines in CI. (completed 2026-06-28)
- [ ] **Phase 8: Lawyer Trial Acceptance** - Run the five-workday lawyer trial and validate V2 acceptance metrics.

## Phase Details

### Phase 1: Platform Contract Foundation

**Goal**: Developers can consume a pure platform-contract package that defines V2 event contracts without any runtime service behavior.
**Depends on**: Nothing (first phase)
**Requirements**: REQ-platform-contract-package, REQ-contract-event-schemas
**Success Criteria** (what must be TRUE):

  1. Developer can validate AgentTurn, AgentResult, FeedbackEvent, ExecutionTrace, and RouteDecision using JSON Schema.
  2. Developer can import Python bindings for the five contract events, async task states, and error categories.
  3. Contract fixtures demonstrate event relationships through turn_id, conversation_id, result_id, feedback_target, and artifact identifiers.
  4. Legal-specific data is accepted only through industry_context or extension containers, not top-level required platform fields.
  5. The package contains definitions, fixtures, and bindings only; no Hermes or service runtime logic is required to use it.

**Plans**: 3 plans

Plans:

- [x] 01-01-PLAN.md — Platform contract package shell.
- [x] 01-02-PLAN.md — JSON Schema event contracts.
- [x] 01-03-PLAN.md — Fixtures and self-checks.

### Phase 2: Contract Test Suite Foundation

**Goal**: Developers can run a contract test harness before Hermes hook implementation and see schema, fixture, and relationship failures clearly.
**Depends on**: Phase 1
**Requirements**: REQ-contract-test-suite
**Success Criteria** (what must be TRUE):

  1. Developer can run schema validation tests for required fields, enums, and invalid values across all five schemas.
  2. Developer can replay golden fixtures and see whether contract events preserve message-to-task-to-route-to-response-to-feedback continuity.
  3. CI-ready checks fail when required fields are missing, schemas are inconsistent, relationships break beyond tolerance, or legal fields leak into top-level required fields.
  4. Non-legal synthetic examples for finance/tax, engineering, and education can be validated without legal-only fields.

**Plans**: 3 plans

Plans:

- [x] 02-01-PLAN.md — Contract test suite foundation.
- [x] 02-02-PLAN.md — Fixture replay and relationship integrity.
- [x] 02-03-PLAN.md — Local synthetic composability and runner.

### Phase 3: Hermes Integration Spike and Risk Closure

**Goal**: Production Hermes hook work is unblocked by documented, tested decisions for V2's known integration risks.
**Depends on**: Phase 2
**Requirements**: REQ-implementation-risk-resolution
**Success Criteria** (what must be TRUE):

  1. Developer can point to confirmed Hermes hook ordering, including whether contract_result_recorder can run after response_filter.
  2. Developer can see the chosen AgentTurn input strategy: inbound hook if available, otherwise documented agent:end reverse-inference limits.
  3. Developer can trace the intended message_id, feedback_target, template card, and callback association rules.
  4. Developer can inspect defined mappings for long-task states, feedback idempotency, raw payload references, retention, and redaction.
  5. Non-happy-path fixtures exist for route errors, long-task failures, repeated feedback clicks, and non-legal tasks.

**Plans**: 4 plans

Plans:

- [x] 03-01-PLAN.md — Source inventory and integration risk matrix.
- [x] 03-02-PLAN.md — Hook ordering and AgentTurn input decision spec.
- [x] 03-03-PLAN.md — Identifier, state, privacy, idempotency, and safety rules.
- [x] 03-04-PLAN.md — Non-happy-path fixtures and contract-test-suite coverage.

### Phase 4: Hermes Shadow Event Layer

**Goal**: Hermes lawfirm produces standard V2 contract logs through a shadow hook layer while preserving existing legal/business outbound behavior.
**Depends on**: Phase 3
**Requirements**: REQ-hermes-contract-layer, REQ-observability-and-replay
**Success Criteria** (what must be TRUE):

  1. Lawyer-facing Hermes legal/business replies, files, cards, gateway business behavior, router behavior, skills, MCP behavior, and model configuration are unchanged by the shadow recorder.
  2. contract_result_recorder records AgentResult after Hermes prepares the response and writes occurred_at, ingested_at, and seq on contract events.
  3. AgentTurn, RouteDecision, ExecutionTrace, and AgentResult relationships can be inferred or recorded for real Hermes tasks.
  4. Replaying 3-5 Hermes task outputs through the contract-test-suite produces schema-valid standard events.
  5. Failed and long-running tasks expose failure stage or status through ExecutionTrace errors and AgentResult status.

**Plans**: 3 plans

Plans:

- [x] 04-01-PLAN.md — Hook artifact and no-outbound-mutation package scaffold.
- [x] 04-02-PLAN.md — Hermes context mapper and JSONL contract event writer.
- [x] 04-03-PLAN.md — Phase 4 event-stream replay fixtures and contract-test-suite support.

### Phase 5: WeCom Shadow Loop Validation

**Goal**: Lawyers can use the existing WeCom loop while V2 shadow records results and feedback into standard events.
**Depends on**: Phase 4
**Requirements**: REQ-wecom-daily-test-loop
**Success Criteria** (what must be TRUE):

  1. Lawyer sends an incoming WeCom task and receives channel acknowledgment within the WeCom timeout window.
  2. Local replay proves legal business text, files, cards, and feedback can be represented as contract events; live acceptance moves to InkStatute WeCom service in Phase 5.5.
  3. contract_result_recorder records the AgentResult after Hermes prepares the response.
  4. Template card feedback is captured by the existing shim and can be normalized into FeedbackEvent.
  5. Existing Hermes lawfirm WeCom feedback behavior does not regress, and QQ Bot/WeChat remain unbroken non-acceptance channels.

**Plans**: 3 plans

Plans:

- [x] 05-01-PLAN.md — WeCom validation harness and runbook.
- [x] 05-02-PLAN.md — Minimal FeedbackEvent normalization for WeCom callbacks.
- [x] 05-03-PLAN.md — End-to-end WeCom loop replay and live evidence gate.

**Verification**: Local fixture verification passed; live WeCom validation is blocked pending InkStatute WeCom service + Hermes agent adapter evidence. See `05-VERIFICATION.md` and `05-WECOM-VALIDATION.md`.

### Phase 5.5: InkStatute WeCom Service and Hermes Agent Adapter

**Goal**: InkStatute owns WeCom receive/send while running Hermes only as a low-coupling agent backend, presenting a pure lawyer-assistant WeCom bot that does not leak Hermes system/gateway/update/command notices.
**Depends on**: Phase 5
**Requirements**: REQ-inkstatute-wecom-service, REQ-agent-backend-adapter-contract, REQ-hermes-adapter-bootstrap, REQ-assistant-output-boundary, REQ-wecom-daily-test-loop
**Success Criteria** (what must be TRUE):

  1. InkStatute WeCom service can receive WeCom callbacks, verify/decrypt where required, dedupe retries, normalize messages/files/buttons into AgentTurn or FeedbackEvent, and return ACK within the WeCom timeout window.
  2. InkStatute WeCom service can send lawyer-assistant text, files, and template cards, receive feedback callbacks directly, and preserve idempotency for repeated callbacks or send retries.
  3. Developer can select `agent_backend.mode=hermes` and inspect an agent adapter manifest that declares Hermes version, profile, hook/event support, invocation mode, feedback target support, artifact return support, and no-channel-io capability.
  4. Operator can run Hermes bootstrap check on this machine without exposing secrets, verifying lawfirm profile location, hook links, MCP/scripts/skills references, agent invocation, and contract log path.
  5. A sanitized lawfirm profile bundle or bundle manifest exists with SOUL/profile structure, hooks, skill/MCP/script references, agent adapter config, and required external secret/env names, while excluding WeCom secrets, keys, tokens, DBs, logs, customer files, feedback payloads, and raw legal payloads.
  6. Hermes version compatibility matrix documents verified Hermes source/version, required hook and agent-invocation capabilities, config switches, known gateway direct-send paths to avoid, and fallback behavior for version drift.
  7. Assistant output boundary inside InkStatute WeCom service blocks or rewrites Hermes gateway lifecycle, update/self-update, slash command/help/status/credits/insights, memory/tool progress, dangerous command approval, delivery failure debug, ADMIN_NOTICE, stack traces, internal paths, commands, tokens, and profile/runtime details before ordinary WeCom delivery.
  8. Live WeCom acceptance can proceed only after evidence shows ordinary users receive messages from InkStatute WeCom service and Hermes is used only for agent logic, not ordinary user channel IO.

**Plans**: TBD

### Phase 6: Read and Feedback Service APIs

**Goal**: Operators can inspect conversations, tasks, and pending feedback from contract logs without creating a new authoritative session store.
**Depends on**: Phase 5.5
**Requirements**: REQ-conversation-read-view, REQ-feedback-service
**Success Criteria** (what must be TRUE):

  1. Operator can call GET /conversations/{id}, GET /tasks/{id}, and GET /feedback?status=pending against contract-log-derived data.
  2. Operator can look up records by conversation_id, task_id, and trace_id.
  3. FeedbackEvent output includes source, event_type, action, status, raw_payload_ref, and available turn/result/conversation associations.
  4. Repeated button clicks, network retries, and repeated shim writes dedupe through a stable idempotency key.
  5. Route-mismatch feedback produces pending human-review queues with skill_candidate evidence and never auto-modifies legal conclusion skills.

**Plans**: 3 plans
Plans:

- [x] 06-01-PLAN.md — Contract log read model.
- [x] 06-02-PLAN.md — Feedback classification and pending queue.
- [x] 06-03-PLAN.md — Read API and contract fixture integration.

**UI hint**: yes

### Phase 7: CI, Composability, and Privacy Gates

**Goal**: V2 is enforced as an industry-neutral, privacy-aware thin contract and adapter layer through CI and contract evidence.
**Depends on**: Phase 6
**Requirements**: REQ-composability-validation, REQ-security-privacy-baseline, REQ-v2-thin-contract-layer
**Success Criteria** (what must be TRUE):

  1. CI fails on schema inconsistency, missing required fields, relationship breakage beyond tolerance, coverage misses, or top-level legal-field leakage.
  2. Synthetic legal and non-legal tasks produce schema-valid events with intact relationships and no platform core changes.
  3. Contract logs reference raw payloads with raw_payload_ref and avoid sensitive full text, complete ID numbers, phone numbers, bank accounts, addresses, and plaintext secrets by default.
  4. Coverage reports show at least 95% paired AgentTurn and AgentResult coverage for real tasks and relationship breakage no greater than 5%.
  5. Reviewer can verify V2 added contracts, adapter manifests, output-boundary tests, hooks, logs, read APIs, feedback normalization, tests, and trial support without rebuilding Hermes core systems.

**Plans**: TBD

### Phase 8: Lawyer Trial Acceptance

**Goal**: V2 is accepted through real lawyer WeCom usage and metric-backed trial evidence.
**Depends on**: Phase 7
**Requirements**: REQ-lawyer-trial-acceptance, REQ-v2-development-order
**Success Criteria** (what must be TRUE):

  1. At least one lawyer uses the WeCom bot continuously for five workdays and completes at least 15 real tasks.
  2. At least 12 tasks produce clear business output across at least three legal task categories.
  3. Trial metrics show long-task success rate at least 80%, ordinary task success rate at least 85%, and feedback capture rate at least 60%.
  4. Positive feedback share is at least 60%, or a categorized repair plan exists; negative feedback has a response action within 48 hours.
  5. route_mismatch count is no more than 3, each mismatch has structured skill_candidate or routing_rule_candidate evidence, and phase history shows the V2 PRD order was followed before acceptance.
  6. Long-running WeCom document/file tasks use InkStatute-owned task flow with quick ACK, recurring service-owned progress, explicit final/timeout/failure state, no empty-message file+text response, and fast service-owned handling for follow-up user messages while a task is still running.

**Plans**: 4 plans
Plans:

- [x] 08-01-PLAN.md — Trial metrics model and acceptance checker.
- [x] 08-02-PLAN.md — Trial runbook and evidence templates.
- [x] 08-03-PLAN.md — Pending acceptance report and human gate.
- [x] 08-04-PLAN.md — WeCom task flow and progress event runtime.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 5.5 -> 6 -> 7 -> 8.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Platform Contract Foundation | 3/3 | Complete    | 2026-06-27 |
| 2. Contract Test Suite Foundation | 3/3 | Complete    | 2026-06-27 |
| 3. Hermes Integration Spike and Risk Closure | 4/4 | Complete    | 2026-06-28 |
| 4. Hermes Shadow Event Layer | 3/3 | Complete | 2026-06-28 |
| 5. WeCom Shadow Loop Validation | 3/3 | Complete   | 2026-06-28 |
| 5.5. InkStatute WeCom Service and Hermes Agent Adapter | 4/4 | Complete    | 2026-06-28 |
| 6. Read and Feedback Service APIs | 3/3 | Complete    | 2026-06-28 |
| 7. CI, Composability, and Privacy Gates | 3/3 | Complete    | 2026-06-28 |
| 8. Lawyer Trial Acceptance | 4/4 | Human Needed - Live UAT Pending | - |
