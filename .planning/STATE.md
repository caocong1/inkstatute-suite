---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 06-01-PLAN.md
last_updated: "2026-06-28T07:30:31.653Z"
last_activity: 2026-06-28 -- Phase 06 execution started
progress:
  total_phases: 9
  completed_phases: 6
  total_plans: 23
  completed_plans: 21
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-28)

**Core value:** Lawyers can use InkStatute's own WeCom lawyer assistant service while V2 records industry-neutral, privacy-aware contract events that are valid, replayable, feedback-linked, CI-verifiable, and agent-backend-neutral. Hermes lawfirm is the first agent backend, and Hermes gateway/meta/update/command notices must not leak to ordinary users.
**Current focus:** Phase 06 — read-and-feedback-service-apis

## Current Position

Phase: 06 (read-and-feedback-service-apis) — EXECUTING
Plan: 2 of 3
Status: Ready to execute
Last activity: 2026-06-28 -- Phase 06 execution started

Progress: [██████░░░░] 67% of roadmap phases

## Performance Metrics

**Velocity:**

- Total plans completed: 17
- Average duration: N/A
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3 | - | - |
| 2 | 3 | - | - |
| 3 | 4 | - | - |
| 4 | 3 | - | - |
| 05.5 | 4 | - | - |

**Recent Trend:**

- Last 5 plans: none
- Trend: N/A

*Updated after each plan completion*
| Phase 01-platform-contract-foundation P01 | 8min | 2 tasks | 7 files |
| Phase 01-platform-contract-foundation P03 | 4m19s | 2 tasks | 6 files |
| Phase 02-contract-test-suite-foundation P01 | 3m55s | 2 tasks | 6 files |
| Phase 02-contract-test-suite-foundation P02 | 3m57s | 2 tasks | 4 files |
| Phase 02-contract-test-suite-foundation P03 | 4m27s | 3 tasks | 7 files |
| Phase 03 P01 | 3m53s | 2 tasks | 3 files |
| Phase 03 P03 | 3m07s | 2 tasks | 2 files |
| Phase 03 P02 | 10min | 2 tasks | 3 files |
| Phase 03 P04 | 10min | 3 tasks | 7 files |
| Phase 04 P01 | 4min | 2 tasks | 8 files |
| Phase 04 P02 | 9min | 3 tasks | 7 files |
| Phase 04 P03 | 8min | 3 tasks | 6 files |
| Phase 05 P01 | 5min | 2 tasks | 4 files |
| Phase 05 P02 | 5min | 2 tasks | 7 files |
| Phase 05 P03 | 5min | 3 tasks | 6 files |
| Phase 05.5 P01 | 30min | 3 tasks | 11 files |
| Phase 05.5 P02 | 18min | 3 tasks | 12 files |
| Phase 05.5 P03 | 12min | 3 tasks | 7 files |
| Phase 05.5 P04 | 14min | 3 tasks | 7 files |
| Phase 06 P01 | 18 min | 4 tasks | 7 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- V2 PRD is the active product specification; retired V1 is not an active requirement source.
- V2 is an InkStatute-owned WeCom service plus backend-neutral contract and agent adapter layer; Hermes lawfirm is the first production agent backend, not a Hermes rebuild.
- JSON Schema and Python bindings come before TypeScript.
- Contract-test-suite precedes production Hermes hook implementation.
- Hermes integration risks are isolated into Phase 3 before production hook work.
- Lawyer trial acceptance remains a manual human gate.
- InkStatute owns ordinary user WeCom receive/send; Hermes gateway is not the V2 channel boundary.
- Hermes lawfirm is the first agent backend adapter, not the platform or channel boundary.
- Ordinary WeCom users must not see Hermes gateway/update/self-update/command/help/status/credits/insights/memory/tool-progress/debug notices.
- Raw lawfirm profile copying is not a deployable artifact; V2 needs a sanitized profile bundle plus external secrets/env.
- [Phase 01]: Keep platform_contract Python bindings standard-library-only with no runtime dependencies.
- [Phase 01]: Use industry_context and metadata containers for legal/profile-specific extension data instead of legal-only top-level required fields.
- [Phase 01]: Keep Phase 1 fixture validation as a package-local stdlib self-check rather than a Phase 2 contract-test-suite harness. — Plan 01-03 is scoped to package-local fixtures and self-checks; Phase 2 owns the contract-test-suite.
- [Phase 01]: Represent legal sample context only in industry_context or metadata and use raw_payload_ref-style references for sensitive source material. — AGENTS.md and V2 PRD require legal-specific and sensitive data to remain outside platform-level top-level required fields.
- [Phase 02]: Keep the contract-test-suite dependency-free and use only Python stdlib unittest/json/pathlib.
- [Phase 02]: Consume Phase 1 platform-contract schemas and fixtures by path instead of duplicating contract definitions.
- [Phase 02]: Reject forbidden legal/sensitive top-level fields in the validator even if a future schema accidentally allows them.
- [Phase 02]: Keep fixture replay dependency-free and reuse Plan 02-01 validate_event_bundle before relationship checks.
- [Phase 02]: Model relationship failures as structured RelationshipIssue records with fixture id, field path, expected value, and actual value.
- [Phase 02]: Enforce relationship breakage tolerance in assert_relationship_integrity while replay_fixtures returns a structured report.
- [Phase 02]: Keep Phase 2 composability evidence local and synthetic; Phase 7 owns .github CI enforcement. — Plan 02-03 provides a package-local runner command but explicitly defers CI workflow wiring.
- [Phase 02]: Reuse existing schema validation and fixture replay helpers rather than adding another validator. — Composability tests should exercise the same harness introduced by Plans 02-01 and 02-02.
- [Phase 02]: Use fixture:// references for synthetic source material and keep domain-specific fields in industry_context or metadata. — AGENTS.md and the V2 PRD require privacy-aware logs and industry-neutral top-level schemas.
- [Phase 03]: [Phase 03 Plan 01]: Treat PRD descriptions of Hermes hooks and feedback flow as specification evidence, not source-confirmed Hermes API evidence.
- [Phase 03]: [Phase 03 Plan 01]: Block separate Phase 4 contract_result_recorder hook work until Hermes hook ordering after response_filter is source/runtime-confirmed or a fallback is selected.
- [Phase 03]: [Phase 03 Plan 01]: Carry message_id, callback payload, long-task state, and raw payload storage details into downstream plans as requires Hermes source/runtime.
- [Phase 03]: [Phase 03 Plan 03]: Use feedback_target = message_id only after Hermes source/runtime proves message_id survives response filtering, preview storage, card dispatch, callbacks, and feedback rows.
- [Phase 03]: [Phase 03 Plan 03]: Map async task states only to exact platform AsyncTaskState values and mark missing Hermes signals unavailable rather than approximating them.
- [Phase 03]: [Phase 03 Plan 03]: Keep raw payloads reference-first with raw_payload_ref namespaces; storage location, retention owner, and redaction enforcement remain requires Hermes source/runtime.
- [Phase 03]: [Phase 03 Plan 03]: Route mismatch and skill_candidate feedback require human review and must not auto-modify legal skills.
- [Phase 03]: [Phase 03 Plan 02]: A separate recorder can run after response_filter only when its hook directory sorts after response_filter; the manifest name is not the ordering key.
- [Phase 03]: [Phase 03 Plan 02]: A canonical contract_result_recorder/ directory would run before response_filter and is not valid for after-filter recording.
- [Phase 03]: [Phase 03 Plan 02]: AgentTurn should prefer source-confirmed agent:start metadata while full input content, attachments, message type, and received_at remain source-dependent.
- [Phase 03]: [Phase 03 Plan 04]: Non-happy-path evidence lives in contract-test-suite fixtures and reuses validate_event_bundle plus assert_relationship_integrity.
- [Phase 03]: [Phase 03 Plan 04]: Repeated feedback clicks are represented as one canonical FeedbackEvent with idempotency metadata and duplicate callback references.
- [Phase 03]: [Phase 03 Plan 04]: Route mismatch fixtures require skill_candidate.requires_human_review and explicit no-auto-modify metadata.
- [Phase 03 Verification]: Phase 4 may implement a separate recorder only if the hook directory sorts after response_filter; it must not use a canonical contract_result_recorder/ directory for after-filter recording.
- [Phase 03 Verification]: Phase 4 must not claim full outbound response capture from the capped agent:end hook context without a full-response source.
- [Phase 03 Verification]: Runtime-only callback fields, long-task signal sources, and raw payload retention/redaction enforcement remain downstream implementation gates, not hidden assumptions.

### Pending Todos

None yet.

### Blockers/Concerns

- Legal/safety concerns require human review when they affect high-risk legal conclusions or lawyer trial acceptance.
- Phase 4 recorder implementation must encode the source-confirmed after-filter hook directory ordering rule and must not claim full outbound capture from the capped agent:end hook context.
- Phase 4/6 runtime work must obtain sanitized evidence for callback fields, feedback rows, long-task state sources, and raw payload retention/redaction before claiming those details as source-confirmed.
- Live WeCom acceptance is blocked until Phase 5.5 proves InkStatute WeCom service owns receive/send, Hermes is used only for agent logic, and ordinary users see InkStatute lawyer-assistant output rather than Hermes operator UI.
- Hermes agent adapter work must account for version drift with capability probing and a compatibility matrix before relying on hook/event/invocation behavior.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Beyond V2 | Independent Router Service, Skill Registry, full Web UI, Tauri desktop, automatic skill synthesis, complete security platform | Deferred to M2-M4 | V2 initialization |

## Session Continuity

Last session: 2026-06-28T07:30:31.420Z
Stopped at: Completed 06-01-PLAN.md
Resume file: None
