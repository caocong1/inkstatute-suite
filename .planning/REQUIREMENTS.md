# Requirements: 墨律 InkStatute

**Defined:** 2026-06-27  
**Source of Truth:** `docs/requirements/V2-PRD.md`  
**Core Value:** Hermes lawfirm can be used by lawyers in WeCom while V2 records industry-neutral, privacy-aware contract events that are valid, replayable, feedback-linked, and CI-verifiable without changing Hermes outbound behavior.

## Active V2 Requirements

Requirements for the current V2 milestone. Retired product V1 is not an active requirement source.

### Platform Boundary and Sequencing

- [ ] **REQ-v2-thin-contract-layer**: InkStatute V2 must be a thin platform contract layer around the existing Hermes lawfirm profile, preserving Hermes as the backend and contract-normalizing observable behavior instead of rebuilding core runtime systems.
  - Hermes remains the V2 backend.
  - V2 adds contract schemas, hook-based normalization, contract logs, read views, feedback normalization, contract tests, and lawyer trial support.
  - V2 does not rebuild Hermes core, session storage, router, skill registry, MCP registry, model gateway, WeCom gateway, or the feedback card/jsonl channel.
  - The V1 full-stack platform scope is not treated as an active requirement source.

- [ ] **REQ-v2-development-order**: Implement V2 in the PRD order: schemas first, then testing, then Hermes shadow recording, then WeCom feedback loop, then read/feedback services, then acceptance validation.
  - Step 1 delivers platform-contract schemas, async state machine, error codes, JSON Schema/Python bindings, and fixtures.
  - Step 2 delivers contract-test-suite framework, golden examples, synthetic task runner, and CI job.
  - Step 3 delivers hermes-contract-layer minimum hook, mapper, and event writer.
  - Step 4 deploys hook and confirms WeCom task-to-reply-to-card-to-feedback-to-FeedbackEvent loop.
  - Step 5 delivers conversation-read-view minimum API.
  - Step 6 delivers feedback-service normalization, dedupe, classification, and skill_candidate generation.
  - Step 7 completes contract CI and composability validation.
  - Step 8 runs the five-workday lawyer trial and metrics collection.

- [ ] **REQ-implementation-risk-resolution**: Resolve V2 implementation risks that do not block PRD finalization but do block development completion.
  - Confirm Hermes hook execution order, especially `contract_result_recorder` after `response_filter`.
  - Confirm whether Hermes has an inbound hook point, or document `agent:end` reverse-inference limits for AgentTurn content.
  - Confirm message_id stability across response_filter, template cards, and feedback callbacks.
  - Define long-task status source mapping to queued, running, waiting_for_user, succeeded, failed, cancelled.
  - Define feedback target, feedback idempotency, raw payload retention, storage, and redaction rules.
  - Include non-happy-path fixtures for route errors, long-task failures, repeated feedback clicks, and non-legal tasks.
  - Ensure feedback-service cannot accidentally trigger automatic legal skill modification.

### Platform Contract

- [ ] **REQ-platform-contract-package**: Provide a pure-definition platform-contract package with five event schemas, async task state machine, error codes, fixtures, and bindings.
  - Defines AgentTurn, AgentResult, FeedbackEvent, ExecutionTrace, and RouteDecision schemas.
  - Provides JSON Schema and Python types first; TypeScript types may follow after V2 priority work.
  - Defines async task states: queued, running, waiting_for_user, succeeded, failed, cancelled.
  - Defines contract_error, runtime_error, and channel_error categories.
  - Contains no runtime service logic.
  - Can be consumed by hermes-contract-layer, conversation-read-view, feedback-service, and contract-test-suite.

- [ ] **REQ-contract-event-schemas**: The five contract objects must be modeled as platform events, not database table definitions, and must support traceable end-to-end relationships.
  - AgentTurn includes required turn_id, conversation_id, channel, user_id, message_type, received_at.
  - AgentResult includes required result_id, turn_id, status, reply_type and optional artifacts, execution_trace, route_mismatch, skill_candidate, error, metadata.
  - FeedbackEvent includes required feedback_id, turn_id, conversation_id, user_id, source, event_type, status, created_at.
  - ExecutionTrace includes V2-required trace_id, turn_id, started_at, ended_at, active_skill_name, matched_registered_skill, occurred_at, ingested_at, seq.
  - RouteDecision includes required route_decision_id, turn_id, primary_skill, confidence, mode, created_at.
  - All events can be related through turn_id, conversation_id, feedback_target, result_id, and artifact identifiers.
  - Legal-specific fields are placed under industry_context or other extension containers, not top-level required schema fields.

### Contract Verification

- [ ] **REQ-contract-test-suite**: Provide a contract test suite that validates schemas, replays fixtures, verifies event relationships, and enforces composability in CI.
  - Schema validation covers required fields, enums, and invalid values for all five schemas.
  - Fixture replay validates golden examples from Hermes hook output.
  - Relationship checks verify message-to-task-to-route-to-response-to-feedback continuity with a breakage rate no greater than 5%.
  - Contract log coverage for real tasks is at least 95% for paired AgentTurn and AgentResult events.
  - CI fails when schemas are inconsistent, required fields are missing, relationships break beyond tolerance, or legal fields leak into top-level required platform schema fields.
  - CI includes non-legal synthetic tasks for finance/tax, engineering, and education scenarios.

- [ ] **REQ-composability-validation**: The platform contract layer must support arbitrary enabled skill, gate, MCP, tool, and output-constraint combinations without platform core changes or legal-field coupling.
  - Synthetic tasks include simple legal Q&A, contract review, legal retrieval, route mismatch, WeCom feedback, long-task failure, and non-legal tasks.
  - Each synthetic task produces schema-valid events with intact relationships.
  - Non-legal tasks do not require legal-specific fields.
  - Legal-specific data remains in industry_context or profile-specific extensions.
  - Tests fail if platform core code or top-level required schemas depend on lawfirm-only fields.

### Hermes Shadow Integration

- [ ] **REQ-hermes-contract-layer**: Add a hook-based shadow contract layer to Hermes lawfirm that maps internal Hermes context and outputs into standard contract events without changing outbound behavior.
  - Provides a `contract_result_recorder` hook on `agent:end` after `response_filter`.
  - Maps final replies into AgentResult and writes contract logs.
  - Records occurred_at, ingested_at, and a monotonic sequence for every contract event.
  - Uses agent:end context and session context to infer AgentTurn where no agent:start event exists.
  - Does not alter Hermes outbound text, gateway behavior, router behavior, skill execution, MCP behavior, or model configuration.
  - Includes mapper and event log writer code under `services/hermes-contract-layer`.
  - Contract-test-suite can replay hook output into valid standard events.

- [ ] **REQ-observability-and-replay**: Contract events must be observable, replayable, and auditable enough to diagnose task flow, failures, routing, tools, gates, artifacts, and feedback.
  - Every AgentResult includes or links to ExecutionTrace.
  - ExecutionTrace can connect messages, tasks, routes, tool calls, gates, artifacts, errors, and feedback.
  - Each contract event includes occurred_at, ingested_at, and seq.
  - Test coverage includes out-of-order replay.
  - Failed long tasks expose failure stage through ExecutionTrace.errors and AgentResult.status=failed.
  - Contract logs support coverage reporting and relationship integrity checks.

### WeCom Loop and Services

- [ ] **REQ-wecom-daily-test-loop**: Preserve and validate the existing WeCom daily-use loop while shadow-recording contract events and normalized feedback.
  - WeCom remains the primary V2 acceptance channel.
  - Incoming lawyer tasks receive a channel acknowledgment within the WeCom timeout window.
  - Hermes continues to send text, files, and template cards through the existing gateway path.
  - contract_result_recorder records AgentResult events after Hermes prepares the response.
  - Template card feedback is captured by the existing shim and normalized into FeedbackEvent.
  - Existing Hermes lawfirm WeCom template-card feedback behavior does not regress.
  - QQ Bot and WeChat remain non-V2 acceptance channels but are not broken.

- [ ] **REQ-conversation-read-view**: Build a read-only conversation and task view from contract logs, using Hermes sessions only as a fallback read model rather than an authoritative new session store.
  - Reads contract event logs as the primary source.
  - Provides GET /conversations/{id}, GET /tasks/{id}, and GET /feedback?status=pending as the V2 minimum API set.
  - Supports lookup by conversation_id, task_id, and trace_id.
  - May use sessions.db only through an explicitly Hermes-specific adapter and only to fill gaps.
  - Does not create an independent authoritative conversation database.

- [ ] **REQ-feedback-service**: Normalize Hermes feedback.jsonl and preview data into FeedbackEvent records, classify feedback, dedupe repeated callbacks, and produce pending queues for human review.
  - Reads Hermes feedback.jsonl and pending_previews.jsonl as input references.
  - Produces FeedbackEvent records with source, event_type, action, status, raw_payload_ref, and association to turn/result/conversation where available.
  - Dedupes repeated button clicks, network retries, and repeated shim writes using an idempotency key.
  - Classifies feedback into rating, correction, fact_missing, citation_error, route_mismatch, format_issue, compliance_issue, and skill_candidate categories.
  - Marks route_mismatch feedback and records skill_candidate evidence.
  - Does not change the feedback channel or template card dispatch flow.
  - Does not automatically modify legal conclusion skills.

### Safety and Acceptance

- [ ] **REQ-security-privacy-baseline**: V2 must enforce minimum privacy, security, and legal-work-product safeguards without adding a complete M3 security platform.
  - Customer materials, case facts, and contract content are confidential by default.
  - Contract logs reference raw payloads using raw_payload_ref and avoid storing sensitive full text by default.
  - Logs avoid complete ID numbers, phone numbers, bank accounts, addresses, and other sensitive values.
  - Secrets are referenced through Hermes existing secret management or environment variables, not stored in plaintext.
  - Admin-only notices are not exposed to ordinary users.
  - Legal outputs preserve the working-draft-for-lawyer-review principle.
  - High-risk feedback does not automatically alter legal conclusions, statute references, cause-of-action judgments, jurisdiction judgments, or liability conclusions.
  - skill_candidate.requires_human_review is true for V2 skill-candidate flows.

- [ ] **REQ-lawyer-trial-acceptance**: Validate V2 through a five-workday real lawyer trial using the Hermes lawfirm WeCom bot.
  - At least one lawyer uses the WeCom bot continuously for five workdays.
  - At least 15 real tasks are completed, with at least 12 producing clear business output.
  - At least three task categories are covered from contract review, legal retrieval Q&A, document drafting, judgment analysis, and case analysis.
  - Long tasks over 60 seconds have success rate at least 80%.
  - Ordinary tasks have end-to-end success rate at least 85%.
  - Feedback capture rate is at least 60%.
  - Positive feedback share is at least 60%; otherwise a categorized repair plan exists.
  - Negative feedback has a recorded response action within 48 hours.
  - route_mismatch count is no more than 3, and each item has a structured skill_candidate or routing_rule_candidate.

## Deferred Beyond V2

### M2

- Independent Router Service normalization upgrade.
- Skill Registry reading and conversation-read-view completion.
- Admin Console API read-only surface.
- QQBot complete loop.

### M3

- Multi Agent Runtime Adapter.
- MCP Connector Registry and Model Provider Gateway.
- Web frontend.
- Complete security platform: encryption, tenancy, RBAC, retention/destruction, WORM audit logs, key rotation.

### M4

- Full Document Pipeline for Office editing, template inheritance, and style migration.
- Tauri desktop.
- Automatic Skill synthesis.

## Out of Scope

Explicitly excluded from V2 to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Retired V1 platform scope | V2 PRD replaces V1 as the active requirement source. |
| Rebuilding Hermes core/runtime systems | V2 is a thin contract layer around the existing Hermes lawfirm backend. |
| Independent authoritative conversation database | V2 read APIs derive from contract logs; Hermes sessions are fallback only. |
| New WeCom gateway or feedback card channel | Existing Hermes gateway/card/jsonl flow remains the channel. |
| Full Web UI or Tauri desktop | Deferred beyond V2; WeCom is the V2 acceptance channel. |
| Automatic legal skill modification | High-risk legal feedback must remain human-reviewed. |
| Raw legal payload storage in contract logs by default | Contract logs must prefer references and minimize sensitive content. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| REQ-platform-contract-package | Phase 1 | Pending |
| REQ-contract-event-schemas | Phase 1 | Pending |
| REQ-contract-test-suite | Phase 2 | Pending |
| REQ-implementation-risk-resolution | Phase 3 | Pending |
| REQ-hermes-contract-layer | Phase 4 | Pending |
| REQ-observability-and-replay | Phase 4 | Pending |
| REQ-wecom-daily-test-loop | Phase 5 | Pending |
| REQ-conversation-read-view | Phase 6 | Pending |
| REQ-feedback-service | Phase 6 | Pending |
| REQ-composability-validation | Phase 7 | Pending |
| REQ-security-privacy-baseline | Phase 7 | Pending |
| REQ-v2-thin-contract-layer | Phase 7 | Pending |
| REQ-lawyer-trial-acceptance | Phase 8 | Pending |
| REQ-v2-development-order | Phase 8 | Pending |

**Coverage:**
- Active V2 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0

---
*Requirements defined: 2026-06-27*
*Last updated: 2026-06-27 after roadmap traceability creation*
