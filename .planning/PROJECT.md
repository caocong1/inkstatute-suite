# 墨律 InkStatute

## What This Is

墨律 InkStatute V2 is an InkStatute-owned WeCom service plus backend-neutral platform contract and agent-adapter layer. Hermes `lawfirm` is the first production agent backend; V2 adds WeCom receive/send, industry-neutral contracts, agent adapter contracts, Hermes bootstrap/version boundaries, assistant output filtering, shadow event recording, feedback normalization, read-only views, CI gates, and lawyer trial acceptance.

V2 is for proving that the running lawyer assistant can be received and sent through InkStatute's own WeCom service, observed, replayed, validated, deployed through a low-coupling agent adapter, presented as a pure lawyer WeCom bot, and evolved through a stable platform contract without rebuilding Hermes core systems.

## Core Value

Lawyers can use InkStatute's own WeCom lawyer assistant service while V2 records industry-neutral, privacy-aware contract events that are valid, replayable, feedback-linked, CI-verifiable, and agent-backend-neutral. Hermes lawfirm is the first agent backend, and Hermes gateway/meta/update/command notices must not leak to ordinary users.

## Requirements

### Validated

- Existing Hermes `lawfirm` profile is already running as the lawyer assistant backend.
- Hermes source inspection confirms `agent:end` response filtering is insufficient as a complete user-output boundary because gateway/update/restart/delivery/status paths can send directly through platform adapters.
- Existing Hermes WeCom, QQ Bot, and WeChat gateway connections exist as runtime evidence and migration inputs, with WeCom as the V2 acceptance channel. Target V2 WeCom ingress/egress is owned by InkStatute, not Hermes gateway.
- Existing Hermes feedback path is already present: `response_filter` preview, template card dispatch, callback shim, and `feedback.jsonl`.
- Existing Hermes router, skills, gates, MCP tools, model gateway, and session storage remain the operational baseline.
- Phase 3 Hermes integration spike is complete: hook ordering is source-confirmed, AgentTurn strategy is documented, identifier/state/privacy/safety rules are defined, and non-happy-path fixtures validate through the contract-test-suite.
- Phase 4 Hermes shadow event layer is complete: repo-owned hook artifact, mapper, JSONL writer, and event-stream replay fixtures validate without live Hermes mutation.

### Active

- [x] Define the V2 platform contract package with five event schemas, async task states, error categories, JSON Schema, Python bindings, and fixtures.
- [x] Model AgentTurn, AgentResult, FeedbackEvent, ExecutionTrace, and RouteDecision as platform events with traceable relationships.
- [x] Build a contract test suite before production Hermes hook work.
- [x] Resolve Hermes integration risks before production hook implementation.
- [x] Add a thin hook-based Hermes shadow contract layer that does not alter legal/business outbound behavior.
- [ ] Build InkStatute-owned WeCom service for receive/send, ACK, message normalization, text/file/card delivery, feedback callbacks, idempotency, retry, and output policy.
- [ ] Define and implement the agent backend adapter contract and runtime selector, with Hermes as the first supported mode and Codex/provider-model modes preserved as contract-compatible future modes.
- [ ] Build a reproducible Hermes agent adapter bootstrap path from a sanitized lawfirm profile bundle, version/capability matrix, external secrets/env, and health checks.
- [ ] Add an assistant output boundary so ordinary WeCom users see only InkStatute lawyer-assistant output, not Hermes gateway/update/command/meta notices.
- [ ] Preserve and validate the WeCom task-to-agent-to-reply-to-card-to-feedback loop through InkStatute WeCom service.
- [ ] Normalize Hermes feedback into FeedbackEvent records with dedupe, classification, and human-reviewed skill candidates.
- [ ] Build read-only conversation/task/feedback APIs from contract logs.
- [ ] Enforce observability, replay, privacy, and legal safety baselines.
- [ ] Enforce composability and industry-neutral contract behavior in CI.
- [ ] Complete the five-workday lawyer trial acceptance criteria.

### Out of Scope

- Retired product V1 as an active requirement source - V2 PRD replaces it.
- Rebuilding Hermes core, session storage, router, skill registry, MCP registry, or model gateway - V2 calls Hermes as an agent backend, not a Hermes fork.
- Production Codex or direct provider-model adapters - V2 defines the contract and configuration shape, but only Hermes mode is required to be production-ready.
- Full multi-channel gateway - V2 builds the minimum InkStatute WeCom service only.
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
- **Architecture**: WeCom ingress/egress is owned by InkStatute; agent backend access goes through an adapter contract - Hermes remains the first production agent backend, not the channel boundary.
- **Integration**: Hermes core execution should remain unchanged - contract work uses hooks, mappers, writers, adapter wrappers, output policy, and tests.
- **Sequencing**: `platform-contract` and `contract-test-suite` come before production Hermes hook work - prevents building hooks against unstable contracts.
- **Risk control**: Hermes hook ordering, inbound turn reconstruction, message IDs, long-task states, feedback targets, idempotency, and redaction rules must be resolved before production hook implementation.
- **Privacy**: Contract logs use `raw_payload_ref` and avoid sensitive full text by default - protects customer legal materials and work product.
- **User-facing output**: Ordinary WeCom users must not see Hermes/gateway/update/command/meta notices - InkStatute WeCom service either blocks them or rewrites them into InkStatute-owned service notices.
- **Deployment**: Runtime secrets, tokens, DBs, logs, customer files, feedback payloads, and raw legal payloads stay outside profile bundles and the repo.
- **Legal safety**: High-risk feedback remains human-reviewed - V2 records skill candidates but does not auto-modify legal conclusions.
- **Composability**: Platform schemas and CI must stay industry-neutral - legal-specific fields belong in `industry_context` or profile extensions.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| V2 PRD is the active product specification | V1 scope was retired and too broad for the current validation goal | - Pending |
| Build WeCom receive/send in InkStatute, not Hermes gateway | The user-facing lawyer bot is this product's channel service; Hermes should only provide agent logic | Decided 2026-06-28 |
| Treat Hermes lawfirm as the first agent backend adapter, not the platform or channel boundary | The product must support future Codex/provider-model modes without rewriting platform contracts | Decided 2026-06-28 |
| JSON Schema and Python bindings come before TypeScript | Current runtime priority is Python packages/services with schema as the cross-language contract | - Pending |
| Contract test suite precedes production Hermes hook implementation | Hook output should be validated against stable schemas and fixtures from the start | - Pending |
| Add an explicit Hermes integration spike before production hook work | PRD risks around hook order, message IDs, feedback targets, and redaction can block implementation | Completed in Phase 3 verification on 2026-06-28 |
| Add assistant output boundary before live WeCom acceptance | Hermes gateway/update/restart/command paths can bypass `agent:end`; user-facing WeCom must be owned by InkStatute and remain a pure lawyer assistant bot | Decided 2026-06-28 |
| Use sanitized lawfirm profile bundle plus external secrets for Hermes deployment | Copying the live profile directly risks committing secrets, logs, DBs, feedback, customer documents, and machine-specific paths | Decided 2026-06-28 |
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
*Last updated: 2026-06-28 after InkStatute WeCom service and agent adapter requirement update*
