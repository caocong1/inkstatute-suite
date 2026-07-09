# 墨律 InkStatute

## What This Is

墨律 InkStatute V2 is an InkStatute-owned WeCom service plus backend-neutral platform contract and agent-adapter layer. Hermes `lawfirm` is the first production agent backend; V2 adds WeCom receive/send, industry-neutral contracts, agent adapter contracts, Hermes bootstrap/version boundaries, assistant output filtering, shadow event recording, feedback normalization, read-only views, CI gates, and lawyer trial acceptance.

V2 is for proving that the running lawyer assistant can be received and sent through InkStatute's own WeCom service, observed, replayed, validated, deployed through a low-coupling agent adapter, presented as a pure lawyer WeCom bot, and evolved through a stable platform contract without rebuilding Hermes core systems.

## Core Value

Lawyers can use InkStatute's own WeCom lawyer assistant service while V2 records industry-neutral, privacy-aware contract events that are valid, replayable, feedback-linked, CI-verifiable, and agent-backend-neutral. Hermes lawfirm is the first agent backend, and Hermes gateway/meta/update/command notices must not leak to ordinary users.

## Current Milestone: v1.9 QQBot Host Composition

**Goal:** Assemble the v1.8 QQBot package-level channel into a deployable production webhook host path, harden smoke coverage across the full adapter/session Protocol stack, and enable controlled live QQ integration while keeping live acceptance as a human gate.

**Target features:**
- Thin production webhook host composing `verify_and_ack` → ingress/session/feedback → `deliver`
- Runtime registration of `QQBotChannelAdapter` into `DefaultRunRuntime.channels` / flag→config mapping
- Smoke dry-run hardening that exercises the full adapter/session Protocol path (not leaf helpers only)
- Controlled QQ live integration capability (`--live` remains HUMAN GATE; do not auto-claim live acceptance)

**Not in this milestone's done definition:**
- Phase 5 live WeCom UAT (carried human gate)
- Phase 8 five-workday lawyer trial (carried human gate)
- Claiming deployed live QQBot acceptance without operator evidence


## Previous: v1.8 QQBot Channel Production — SHIPPED

**Shipped:** 2026-07-09
**Status:** COMPLETE with accepted gaps — 10/10 phases shipped (58-67), 28/28 package-level requirements satisfied, 321 qqbot unit tests green. Audit status `gaps_found`: production host webhook composition deferred; smoke dry-run skips full adapter/session Protocol path; live QQ smoke remains a human gate.

**Archive:** [v1.8-ROADMAP.md](milestones/v1.8-ROADMAP.md) | [v1.8-REQUIREMENTS.md](milestones/v1.8-REQUIREMENTS.md) | [v1.8-MILESTONE-AUDIT.md](milestones/v1.8-MILESTONE-AUDIT.md)

## Previous: v1.6 M2 Multi-Backend & Platform Extensions — SHIPPED

**Shipped:** 2026-07-04
**Status:** COMPLETE — 9/9 phases shipped (36-44), 22/22 requirements satisfied, 19/19 V2 gates green (969 tests).

The v1.6 milestone extended the platform beyond Hermes-only by proving agent-backend-neutral contracts (Codex + provider_model prototypes), normalizing routing as an independent service, exposing skill metadata and operational read views, completing conversation-read-view, and adding a second channel (QQBot) to prove ChannelAdapter portability — while keeping all existing V2 gates green and V2 human-gate evidence stable.

**Key deliverables shipped:**
- Codex adapter prototype (`packages/backends/codex`) — proves BackendAdapter contract portability via `codex exec --json` subprocess.
- Provider model adapter prototype (`packages/backends/provider_model`) — direct LLM provider mode via `AsyncOpenAI` lazy SDK import.
- Independent Router Service (`packages/router-service`) — standalone router library with RULE and SKILL modes, injectable into hermes-contract-layer mapper.
- Skill Registry read (`packages/skill-registry`) — read-only registry exposing Hermes skill metadata as `NeutralSkillDescriptor` records with list/get/search + `/.well-known/agent-skills/index.json`.
- Conversation Read-View completion (`services/conversation-read-view`) — cursor-based pagination, time-range/dimension filters, trace reconstruction by `trace_id`, CSV/JSON export, read-time privacy scrubbing.
- Admin Console API (`services/admin-console-api`) — read-only admin API with static token auth, sessions/tasks/feedback/gates/health views, field allowlist excluding secrets.
- QQBot channel loop (`packages/channels/qqbot` + `packages/channel-core`) — channel-generic logic extracted into shared package, QQBot ChannelAdapter implements 6-method Protocol, fixture-driven loop proof.
- Gate coverage meta-test (`packages/contract-test-suite/tests/test_gate_coverage.py`) — enforces every `packages/*/src` and `services/*/src` directory is covered by a gate. 19 gates, 969 tests.

**Safety preserved:**
- Contract freeze maintained (`packages/platform-contract/` unchanged during M2).
- All 6 M2 feature flags default to `False`.
- BackendAdapter Protocol (9 methods) and ChannelAdapter Protocol (6 methods) frozen.
- Output boundary enforced for all new backends.
- V2 human gate evidence stable.

**Archive:** [v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md) | [v1.6-REQUIREMENTS.md](milestones/v1.6-REQUIREMENTS.md) | [v1.6-MILESTONE-AUDIT.md](milestones/v1.6-MILESTONE-AUDIT.md)

</details>

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
- [WECOM-01] Build InkStatute-owned WeCom service for receive/send, ACK, message normalization, text/file/card delivery, feedback callbacks, idempotency, retry, and output policy. — Phases 5, 55 (v1.0); audited Phase 33; verified Phase 34.
- [ADAPTER-01] Define and implement the agent backend adapter contract and runtime selector, with Hermes as the first supported mode and Codex/provider-model modes preserved as contract-compatible future modes. — Phases 5, 55 (v1.0); audited Phase 33; verified Phase 34.
- [HERMES-01] Build a reproducible Hermes agent adapter bootstrap path from a sanitized lawfirm profile bundle, version/capability matrix, external secrets/env, and health checks. — Phase 55 (v1.0); audited Phase 33; verified Phase 34.
- [OUTPUT-01] Add an assistant output boundary so ordinary WeCom users see only InkStatute lawyer-assistant output, not Hermes gateway/update/command/meta notices. — Phase 55 (v1.0); audited Phase 33; verified Phase 34.
- [LOOP-01] Preserve and validate the WeCom task-to-agent-to-reply-to-card-to-feedback loop through InkStatute WeCom service. — Phases 5, 55 (v1.0); audited Phase 33; verified Phase 34.
- [FEEDBACK-01] Normalize Hermes feedback into FeedbackEvent records with dedupe, classification, and human-reviewed skill candidates. — Phase 6 (v1.0); audited Phase 33; verified Phase 34.
- [READVIEW-01] Build read-only conversation/task/feedback APIs from contract logs. — Phase 7 (v1.0); audited Phase 33; verified Phase 34.
- [OBSERVE-01] Enforce observability, replay, privacy, and legal safety baselines. — Phase 7 (v1.0); audited Phase 33; verified Phase 34.
- [COMPOSE-01] Enforce composability and industry-neutral contract behavior in CI. — Phase 8 (v1.0); audited Phase 33; verified Phase 34.
- ✓ M3 adapter productization (streaming, artifacts, session memory, multi-provider) — v1.7 (Phases 46-49)
- ✓ M3 platform extensions (MCP registry, model gateway, multi-agent, skill write, hybrid routing) — v1.7 (Phases 50-55)
- ✓ M3 operator & UX layer (Admin Web UI, Lawyer Web Chat) — v1.7 (Phase 57)
- ✓ M3 security & compliance (RBAC, multi-tenant isolation) — v1.7 (Phases 51, 56, 57.1)
- ✓ M3 safety (9 feature flags default False, frozen Protocols preserved, 24 V2 gates green) — v1.7 (Phase 45)

### Active

- [ ] v1.9 HOST-*: Thin QQBot production webhook host composing verify_and_ack → ingress/session/feedback → deliver (default-OFF).
- [ ] v1.9 HOST-*: Runtime registration of QQBotChannelAdapter into DefaultRunRuntime.channels / flag→config mapping.
- [ ] v1.9 SMOKE-*: Harden smoke dry-run to exercise full adapter/session Protocol path.
- [ ] v1.9 LIVE-*: Controlled QQ live integration path (`--live` remains HUMAN GATE).
- [ ] Complete the five-workday lawyer trial acceptance criteria. (human gate — carried, not v1.9 done definition)
- [x] Define the V2 platform contract package with five event schemas, async task states, error categories, JSON Schema, Python bindings, and fixtures.
- [x] Model AgentTurn, AgentResult, FeedbackEvent, ExecutionTrace, and RouteDecision as platform events with traceable relationships.
- [x] Build a contract test suite before production Hermes hook work.
- [x] Resolve Hermes integration risks before production hook implementation.
- [x] Add a thin hook-based Hermes shadow contract layer that does not alter legal/business outbound behavior.
- [x] M2-01: Codex adapter prototype proving agent-backend-neutral contract beyond Hermes. — Phase 39 (v1.6)
- [x] M2-02: Direct provider_model adapter prototype proving contract-compatible direct LLM provider mode. — Phase 40 (v1.6)
- [x] M2-03: Independent Router Service normalizing routing decisions as a standalone service. — Phase 38 (v1.6)
- [x] M2-04: Skill Registry read exposing Hermes skill metadata as a read-only registry. — Phase 37 (v1.6)
- [x] M2-05: conversation-read-view completion with full PRD-spec read-only views, pagination, and filtering. — Phase 41 (v1.6)
- [x] M2-06: Admin Console API (read-only) exposing operational views for operators. — Phase 42 (v1.6)
- [x] M2-07: QQBot complete loop as second channel proving ChannelAdapter portability. — Phase 43 (v1.6)
- [x] M2-08: Gate coverage meta-test enforcing every packages/*/src and services/*/src directory is covered by a V2 gate. — Phase 44 (v1.6)

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
- Production Codex or direct provider-model adapters - V2 defines the contract and configuration shape, but only Hermes mode is required to be production-ready.
- Intel entry point: `.planning/intel/SYNTHESIS.md`.
- Target runtime: Python packages/services first, with JSON Schema as the cross-language contract format; TypeScript can follow after V2 priority work.
- Full Web UI, Primary wotop, QQBot complere V2 lokf,low: high-autonomy GSD with human gates for blockers, legal/safety concerns, and manual lawyer trial validation.
- PRD development order is binding for this roadmap: platform contract, contract test suite, Hermes integration risk resolution, Hermes shadow layer, WeCom loop, read/feedback services, CI/composability, lawyer trial.


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
| Start M2 (v1.6) before formal V2 acceptance, accepting the PRD §11 dependency violation as risk | V2 code closure is READY (9/9 code reqs, 479 tests, 0 gaps); the only remaining V2 gates are human (Phase 5 live WeCom UAT + Phase 8 lawyer trial) which run in parallel. Blocking all M2 code work on human gates would waste autonomous capacity. Risk accepted: M2 features are contract-compatible extensions, not V2-acceptance-critical paths. | Decided 2026-07-03 |
| Start v1.9 QQBot Host Composition to close v1.8 host-level gaps | v1.8 delivered package-level QQBot production loop with audit `gaps_found`; next value is a thin production webhook host + smoke Protocol-path hardening + controlled live integration, without claiming live acceptance | Decided 2026-07-09 |

## Shipped Milestones

### v1.7 M3 Platform Extensions (Shipped: 2026-07-06)

Promoted adapter prototypes to production-grade (streaming, artifacts, multi-provider, session memory), extended platform surface (MCP registry, model gateway, multi-agent, skill write + hybrid routing), added operator and lawyer-facing Web UI, and introduced RBAC + multi-tenant isolation. Gap closure phase 57.1 wired TenantGuard into Web UI data access paths. All 9 feature flags default False, no frozen Protocol surfaces modified, 24 V2 gates green (1,547+ tests). Audit passed 38/38.

**Archive:** [v1.7-ROADMAP.md](milestones/v1.7-ROADMAP.md) | [v1.7-REQUIREMENTS.md](milestones/v1.7-REQUIREMENTS.md) | [v1.7-MILESTONE-AUDIT.md](milestones/v1.7-MILESTONE-AUDIT.md)

### v1.6 M2 Multi-Backend & Platform Extensions (Shipped: 2026-07-04)

Codex + provider_model adapter prototypes, independent Router Service, Skill Registry read, conversation-read-view completion, Admin Console API, QQBot channel loop, and gate coverage meta-test. Audit passed 22/22, 19/19 gates green, 969 tests.

**Archive:** [v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md) | [v1.6-REQUIREMENTS.md](milestones/v1.6-REQUIREMENTS.md) | [v1.6-MILESTONE-AUDIT.md](milestones/v1.6-MILESTONE-AUDIT.md)

### v1.4 Long-Term Memory Productization (Shipped: 2026-07-03)

Replaced the evaluation-only memory approach with a single, productized long-term memory layer (Hindsight backend). Unified `Memory` interface, Hindsight adapter, focus/retention policies, WeCom runtime integration, retry/observability, singleton wiring, and contract event observability. Audit passed 20/20.

**Archive:** [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md) | [v1.4-REQUIREMENTS.md](milestones/v1.4-REQUIREMENTS.md) | [v1.4-MILESTONE-AUDIT.md](milestones/v1.4-MILESTONE-AUDIT.md)

### v1.3 Production Memory System and Evaluation Spikes (Shipped: 2026-07-02)



### v1.2 Conversational Context and Memory Foundation (Shipped: 2026-07-02)

Automatic WeCom session continuity, interrupt resume, bounded short-term context, platform-native memory, feedback-informed context/candidate behavior, external-memory adapter evaluation, and Phase 19 E2E session-runtime closure. Audit status: `tech_debt` accepted.

**Archive:** [v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) | [v1.2-REQUIREMENTS.md](milestones/v1.2-REQUIREMENTS.md) | [v1.2-MILESTONE-AUDIT.md](milestones/v1.2-MILESTONE-AUDIT.md)

### v1.1 Platform Foundation (Shipped: 2026-06-30)

Four-contract North Star platform architecture (ChannelAdapter, BackendAdapter, SolutionLoader, RunRuntime) with embeddable runtime, Hermes backend adapter, multi-channel interface, and backend-portable solution loader — all default-OFF. 5 phases, 20 plans, 99 commits, 195 files, 25,368 lines. Audit: passed.

**Archive:** [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) | [v1.1-REQUIREMENTS.md](milestones/v1.1-REQUIREMENTS.md) | [v1.1-MILESTONE-AUDIT.md](milestones/v1.1-MILESTONE-AUDIT.md)

## Current State

- **Last shipped:** v1.8 QQBot Channel Production (Phases 58–67) — package-level QQBot production channel loop + dry-run smoke toolkit.
- **Active milestone:** v1.9 QQBot Host Composition — defining requirements.
- **v1.8 accepted gaps in scope for v1.9:** production host webhook composition; smoke Protocol-path hardening; controlled live QQ integration (acceptance remains human gate).
- **Carried human gates (not v1.9 done):** Phase 5 live WeCom UAT; Phase 8 five-workday lawyer trial.


## Evolution

This document evolves at each phase transition and milestone completion.

**After each phase transition** (via `$gsd-execute-phase` → `$gsd-verify-work`):
1. Requirements invalidated? Move to Out of Scope with rationale.
2. Requirements validated? Move to Validated with phase reference.
3. New requirements emerge? Add to Active.
4. Decisions to log? Add to Key Decisions.
5. "What This Is" still accurate? Update if drifted.

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of "What This Is" accuracy.
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state.
5. All shipped requirements moved to Validated.
6. Key Decisions table updated with milestone outcomes.

---
*Last updated: 2026-07-09 — started milestone v1.9 QQBot Host Composition*