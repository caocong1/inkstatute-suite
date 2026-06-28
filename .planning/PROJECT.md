# 墨律 InkStatute

## What This Is

墨律 InkStatute V2 is a thin platform contract layer around the existing Hermes `lawfirm` profile. It keeps Hermes as the backend and adds industry-neutral contracts, contract tests, shadow event recording, feedback normalization, read-only views, CI gates, and lawyer trial acceptance.

V2 is for proving that the running lawyer assistant can be observed, replayed, validated, and evolved through a stable platform contract without rebuilding Hermes core systems.

## Core Value

Hermes lawfirm can be used by lawyers in WeCom while V2 records industry-neutral, privacy-aware contract events that are valid, replayable, feedback-linked, and CI-verifiable without changing Hermes outbound behavior.

## Requirements

### Validated

- Existing Hermes `lawfirm` profile is already running as the lawyer assistant backend.
- Existing WeCom, QQ Bot, and WeChat gateway connections exist, with WeCom as the V2 acceptance channel.
- Existing Hermes feedback path is already present: `response_filter` preview, template card dispatch, callback shim, and `feedback.jsonl`.
- Existing Hermes router, skills, gates, MCP tools, model gateway, and session storage remain the operational baseline.
- Phase 3 Hermes integration spike is complete: hook ordering is source-confirmed, AgentTurn strategy is documented, identifier/state/privacy/safety rules are defined, and non-happy-path fixtures validate through the contract-test-suite.

### Active

- [ ] Define the V2 platform contract package with five event schemas, async task states, error categories, JSON Schema, Python bindings, and fixtures.
- [ ] Model AgentTurn, AgentResult, FeedbackEvent, ExecutionTrace, and RouteDecision as platform events with traceable relationships.
- [ ] Build a contract test suite before production Hermes hook work.
- [x] Resolve Hermes integration risks before production hook implementation.
- [ ] Add a thin hook-based Hermes shadow contract layer that does not alter outbound behavior.
- [ ] Preserve and validate the WeCom task-to-reply-to-card-to-feedback loop.
- [ ] Normalize Hermes feedback into FeedbackEvent records with dedupe, classification, and human-reviewed skill candidates.
- [ ] Build read-only conversation/task/feedback APIs from contract logs.
- [ ] Enforce observability, replay, privacy, and legal safety baselines.
- [ ] Enforce composability and industry-neutral contract behavior in CI.
- [ ] Complete the five-workday lawyer trial acceptance criteria.

### Out of Scope

- Retired product V1 as an active requirement source - V2 PRD replaces it.
- Rebuilding Hermes core, session storage, router, skill registry, MCP registry, model gateway, WeCom gateway, or feedback card/jsonl channel - V2 is a thin platform contract layer.
- New independent authoritative conversation database - V2 read models come from contract logs, with Hermes sessions only as a fallback adapter.
- Full Web UI, Tauri desktop, QQBot complete V2 loop, and WeChat complete V2 loop - not part of V2 acceptance.
- Automatic legal skill synthesis or automatic modification of high-risk legal conclusion skills - V2 records `skill_candidate` for human review only.
- Storing raw customer legal payloads in contract logs by default - logs prefer references and minimized sensitive data.

## Context

- Source of truth: `docs/requirements/V2-PRD.md`.
- Intel entry point: `.planning/intel/SYNTHESIS.md`.
- Target runtime: Python packages/services first, with JSON Schema as the cross-language contract format; TypeScript can follow after V2 priority work.
- Primary workflow: high-autonomy GSD with human gates for blockers, legal/safety concerns, and manual lawyer trial validation.
- PRD development order is binding for this roadmap: platform contract, contract test suite, Hermes integration risk resolution, Hermes shadow layer, WeCom loop, read/feedback services, CI/composability, lawyer trial.

## Constraints

- **Source of truth**: V2 PRD is active; retired V1 must not be reintroduced - prevents scope expansion back to the old full-stack platform.
- **Architecture**: Hermes remains the V2 backend - V2 normalizes observable behavior instead of taking over runtime responsibilities.
- **Integration**: Hermes core must remain unchanged - contract work uses thin hooks, mappers, writers, adapters, and tests.
- **Sequencing**: `platform-contract` and `contract-test-suite` come before production Hermes hook work - prevents building hooks against unstable contracts.
- **Risk control**: Hermes hook ordering, inbound turn reconstruction, message IDs, long-task states, feedback targets, idempotency, and redaction rules must be resolved before production hook implementation.
- **Privacy**: Contract logs use `raw_payload_ref` and avoid sensitive full text by default - protects customer legal materials and work product.
- **Legal safety**: High-risk feedback remains human-reviewed - V2 records skill candidates but does not auto-modify legal conclusions.
- **Composability**: Platform schemas and CI must stay industry-neutral - legal-specific fields belong in `industry_context` or profile extensions.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| V2 PRD is the active product specification | V1 scope was retired and too broad for the current validation goal | - Pending |
| Implement V2 as a thin contract layer around Hermes lawfirm | Hermes already runs the lawyer assistant; platform value starts with contracts and acceptance | - Pending |
| JSON Schema and Python bindings come before TypeScript | Current runtime priority is Python packages/services with schema as the cross-language contract | - Pending |
| Contract test suite precedes production Hermes hook implementation | Hook output should be validated against stable schemas and fixtures from the start | - Pending |
| Add an explicit Hermes integration spike before production hook work | PRD risks around hook order, message IDs, feedback targets, and redaction can block implementation | Completed in Phase 3 verification on 2026-06-28 |
| Lawyer trial acceptance remains a manual human gate | Five-workday legal trial metrics require real usage and legal/safety judgment | - Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `$gsd-transition`):
1. Requirements invalidated? Move to Out of Scope with reason.
2. Requirements validated? Move to Validated with phase reference.
3. New requirements emerged? Add to Active.
4. Decisions to log? Add to Key Decisions.
5. "What This Is" still accurate? Update if drifted.

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of all sections.
2. Core Value check - still the right priority?
3. Audit Out of Scope - reasons still valid?
4. Update Context with current state.

---
*Last updated: 2026-06-28 after Phase 3 verification*
