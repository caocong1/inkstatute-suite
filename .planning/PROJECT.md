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
- v1.2 conversational context and memory foundation is complete: ordinary WeCom continuation/start flows reach runtime run creation, pending clarification resumes remain interrupt-based, bounded context/memory metadata is reference-first, and external memory providers remain optional sanitized-spike candidates.

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
| Start a new milestone "Platform Foundation" (v1.1, Phase 09–13) as a deliberate refactor toward a reusable agent platform | User intent is a long-term general agent platform where the lawyer assistant is one solution; V2's additive `services/` shape is not the target | Decided 2026-06-29 |
| Design to four neutral interface contracts: ChannelAdapter, BackendAdapter, SolutionLoader, RunRuntime | Channels, agent backends, and solutions must be independently swappable; Hermes/WeCom/lawyer are the first of each, not the platform definition | Decided 2026-06-29 |
| Tech stack: JSON Schema contracts + Python 3.11 async core + TypeScript client SDK/chat component; Rust/Go deferred | Fastest delivery with richest agent ecosystem; first backend (Hermes) and lawyer solution are Python; clients are web/TS; embeddability kept via injectable runtime, not a Rust rewrite | Decided 2026-06-29 |
| Solutions are backend-portable (neutral manifest + per-backend materialization); Hermes profile is the first materialization target | The lawyer pack must later run on Codex/Claude Code/OpenCode/self-built backends without rewriting platform plumbing | Decided 2026-06-29 |
| Clients default to remote/thin; runtime kept embeddable; no local runtime this milestone | Web/desktop/mobile are all consumers of one platform API; desktop local runtime is a north-star option, not now | Decided 2026-06-29 |
| Self-built agent is north star only; this milestone just guarantees BackendAdapter can express it | Avoid over-scoping; ownership of the LLM loop is a future BackendAdapter implementation | Decided 2026-06-29 |
| Autonomy split: Phase 09–13 are code+test+fixtures (autonomous); live cutover and Phase 8 trial are human gates off the autonomous path | Enables hands-free `$gsd-autonomous` while preserving live-safety and legal human review | Decided 2026-06-29 |
| Keep Phase 10 `DefaultRunRuntime` embeddable, default-off, ref-first, and output-boundary-enforced for every yielded run event | The reusable platform core must be injectable and privacy-preserving before Hermes parity work starts | Verified in Phase 10 on 2026-06-29 |
| Keep Hermes one-shot as the default backend lane after Phase 11 | The `/v1/runs` parity spike is implemented but intentionally reports route mismatch evidence; API runs remain default-off behind `INKSTATUTE_HERMES_API_RUNS_ENABLED` until parity and later human gates approve | Verified in Phase 11 on 2026-06-29 |
| Phase 12 channel/client surface is default-off, remote/thin, and not live acceptance across WeCom wrapper, Web/SSE, platform API, SDK, and web chat | The platform channel lane is an embeddable building block, not a production UI; live cutover remains a separate human gate | Verified in Phase 12 on 2026-06-29 |
| Web chat renderer emits DOM-free RenderRecord objects, not HTML strings; host view layer maps records to framework primitives | Eliminates XSS-via-string-concatenation class; forces hosts to use React/Preact/lit-html/raw DOM/server template primitives | Decided 2026-06-29 |
| Start milestone v1.2 "Conversational Context and Memory Foundation" before live promotion | Ordinary users must be able to talk continuously without agent commands, while skill clarification, feedback, and memory stay bounded and privacy-safe | Decided 2026-06-30 |
| Make session continuation automatic rather than user-command-driven | Target users do not understand agent sessions; WeCom should infer whether to continue, resume, or start a new task | Decided 2026-06-30 |
| Build platform-native memory first and evaluate Mem0/Zep as optional adapters | Legal privacy, tenant isolation, deletion/export, and raw-payload rules must be proven before external memory services enter production | Decided 2026-06-30 |
| Treat memory indexes and summaries as derived/cacheable state, not the authority | Contract logs and reference stores remain the audit source; memory is context assembly support | Decided 2026-06-30 |
| Model skill clarification as runtime interrupts | The one-shot conversation path loses ask-user flows; pausing and resuming runs preserves skill questions across user replies | Decided 2026-06-30 |
| Keep platform-native memory as the lawyer-assistant default and route Zep/Hindsight, OpenViking/ReMe, and Mem0 through future sanitized spikes | The component study favors different providers for graph/audit, file-auditable, and PoC use cases, but live legal memory still needs privacy, deletion/export, residency, security, review, benchmark, and license gates | Decided 2026-07-02 |
| Build v1.3 as native production memory first, with external providers as measured adapter spikes | A legal-memory system needs deletion/export, tenant isolation, human review, traceability, and raw-payload controls before provider convenience; external tools must beat or complement the native baseline through sanitized evidence | Decided 2026-07-02 |

## Last Completed Milestone: v1.2 Conversational Context and Memory Foundation

**Shipped:** 2026-07-02

**Goal achieved:** Ordinary WeCom users can continuously talk to InkStatute without knowing agent/session commands, while the platform provides bounded short-term context, privacy-safe long-term memory, recoverable skill clarification, and feedback-informed context assembly.

**Target features:**
- Automatic session/thread resolution for WeCom and platform channels, including active task and pending clarification recovery.
- Bounded short-term context assembly with recent turns, rolling summaries, artifacts, feedback corrections, and deterministic trimming.
- Backend-neutral memory contracts and a platform-native `MemoryStore` with privacy, TTL, source refs, confidence, and deletion metadata.
- Runtime interrupt/resume flow for skill clarification and waiting-for-user states.
- Feedback learning policy that feeds corrections into current context and creates human-reviewed memory/routing candidates.
- Mem0/Zep-style external memory adapter research and synthetic adapter spike, without making either mandatory for legal production.

**Artifacts:**
- Requirements archive: `.planning/milestones/v1.2-REQUIREMENTS.md`
- Roadmap archive: `.planning/milestones/v1.2-ROADMAP.md`
- Audit archive: `.planning/milestones/v1.2-MILESTONE-AUDIT.md`
- Research summary: `.planning/research/SUMMARY.md`

## Current Milestone: v1.3 Production Memory System and Evaluation Spikes

**Goal:** Turn the v1.2 memory foundation into a production-capable platform-native memory loop, while evaluating external memory systems only through sanitized adapter spikes.

**Target features:**
- Durable platform-native memory storage with ref-first privacy, scope isolation, TTL/deletion/export, review state, and deterministic query behavior.
- Policy-driven rolling summaries that preserve intent, constraints, open questions, artifacts, and outcomes through refs, hashes, and lengths rather than raw legal text.
- Memory recall orchestration before backend submission so WeCom continuation/start flows can automatically attach approved memory refs and summary refs to bounded context.
- Feedback-to-memory review workflow where safe corrections affect current context and repeated negative feedback creates human-reviewed memory candidates.
- Sanitized memory evaluation harness covering recall quality, false recall, tenant isolation, deletion/export, privacy gates, and token/latency impact.
- External adapter spikes for Zep/Hindsight, OpenViking/ReMe, and Mem0-style candidates, measured against the native baseline without live legal/customer payloads.

**Strategy:** `docs/architecture/memory/production-memory-system-strategy.md`
**Requirements:** `.planning/REQUIREMENTS.md`
**Roadmap:** `.planning/ROADMAP.md`

## Current State

**Milestone v1.1 — Platform Foundation: SHIPPED (2026-06-30)**

v1.1 delivered the four-contract North Star platform architecture with 5 phases, 20 plans, 99 commits, 195 files, and 25,368 lines added. All 287 V2 gate tests pass. Audit status: passed.

**What shipped:**
- Four North Star contracts (ChannelAdapter, BackendAdapter, SolutionLoader, RunRuntime) as independently swappable seams
- Embeddable DefaultRunRuntime with output boundary and default-off feature flags
- Hermes BackendAdapter (subprocess one-shot + capability probe + /v1/runs parity spike)
- Channel interface (WeCom wrapper + Web/SSE channel) + Platform API server + TypeScript SDK + embeddable web chat renderer
- SolutionLoader with lawfirm solution (sanitizing Hermes materializer) and demo_non_legal solution
- All new lanes default-OFF; live cutover is a separate human gate

**Parallel human gates (not autonomous-completable):**
- Phase 8 (Lawyer Trial Acceptance) — 5-workday live WeCom trial pending
- Phase 5 live WeCom UAT — fixture-satisfied, operator confirmation needed
- All v1.1 runtime lanes — default-OFF, live promotion is a human gate

**Archive:** [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) | [v1.1-REQUIREMENTS.md](milestones/v1.1-REQUIREMENTS.md) | [v1.1-MILESTONE-AUDIT.md](milestones/v1.1-MILESTONE-AUDIT.md)

**Milestone v1.2 — Conversational Context and Memory Foundation: SHIPPED (2026-07-02)**

v1.2 delivered automatic WeCom session continuity, interrupt resume, bounded short-term context, platform-native memory, feedback-informed context/candidate behavior, external-memory adapter evaluation, and Phase 19 closure of the runtime E2E wiring gap. Audit status: `tech_debt` accepted, with no remaining critical requirement, integration, or flow blockers.

**What shipped:**
- Backend-neutral memory/context/interrupt schemas and sanitized fixture coverage
- Scoped session resolver and interrupt lifecycle/runtime resume support
- Deterministic short-term context assembly with budget trimming and protected refs
- Platform-native memory store plus feedback learning policy with human review gates
- Sanitized external memory adapter contract, fixture evidence, and recommendation
- WeCom session runtime create-run handoff plus pure ingress orchestration boundary

**Accepted v1.2 debt:**
- Missing/partial Nyquist validation artifacts for Phases 14, 15, 16, 18, and 19
- Service-level feedback-to-memory automation is future integration work
- Live WeCom UAT and five-workday lawyer trial remain human gates

**Archive:** [v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) | [v1.2-REQUIREMENTS.md](milestones/v1.2-REQUIREMENTS.md) | [v1.2-MILESTONE-AUDIT.md](milestones/v1.2-MILESTONE-AUDIT.md)

**Milestone v1.3 — Production Memory System and Evaluation Spikes: SHIPPED (2026-07-02)**

v1.3 made platform-native memory production-capable before any external memory service can handle live legal data. It built durable memory storage, rolling summaries, recall orchestration wired into ordinary WeCom/runtime flows, feedback-to-memory service wiring, evaluation gates with durable SQLite baseline/export evidence, and sanitized external adapter spikes. External providers remain deferred candidates, not defaults. Audit status: `closed`.

**What shipped:**
- Durable native memory store (`SQLiteMemoryStore`) with ref-first privacy, deletion/export/tombstone behavior, and scoped query.
- Rolling summary pipeline and safe summary refs integrated into bounded context assembly.
- Pre-run recall orchestration injected into ordinary WeCom continue/start flows with MemoryUse evidence fail-closed policy.
- Feedback-to-memory human review flow at the service level: correction refs, pending candidates, explicit review actions, and no-auto-modify for high-risk legal/route/skill candidates.
- Memory evaluation harness with hard gates, native baseline, and durable SQLite baseline/export evidence.
- External memory adapter spike report and final `defer_all_external` recommendation.
- Phase 20-25 verification artifacts and Phase 22-25/25.1 validation artifacts; deterministic v1.3 audit closure script.

**Accepted v1.3 debt:**
- Phase 20: file-backed `SQLiteMemoryStore` requires host `db_path` injection in production (deployment configuration).
- Phase 24: `MemoryEvalRunner` supports both in-memory fast CI and SQLite durable baseline modes.
- Phase 25: external adapter spikes remain sanitized manifest/spec simulations; no live provider integration claimed.
- Live WeCom UAT and five-workday lawyer trial remain human gates, not v1.3 dependencies.

**Archive:** [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) | [v1.3-REQUIREMENTS.md](milestones/v1.3-REQUIREMENTS.md) | [v1.3-MILESTONE-AUDIT.md](milestones/v1.3-MILESTONE-AUDIT.md)

## Current State

- **Last shipped:** v1.3 Production Memory System and Evaluation Spikes (2026-07-02).
- **Next step:** Define the next milestone (v1.4 or later) via `/gsd-new-milestone`.
- **Carried human gates:** Phase 5 live WeCom UAT and Phase 8 five-workday lawyer trial remain operator-confirmed human gates.

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
*Last updated: 2026-07-02 after v1.3 milestone definition*
