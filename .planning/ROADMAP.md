# Roadmap: 墨律 InkStatute

## Milestones

- Complete **V2 PRD Foundation** - Phases 1-8 completed by 2026-06-30; live Phase 5/8 human gates remain carried.
- Complete **v1.1 Platform Foundation** - Phases 09-13 shipped 2026-06-30.
- Complete **v1.2 Conversational Context and Memory Foundation** - Phases 14-19 shipped 2026-07-02 with accepted validation/operational tech debt.
- Complete **v1.3 Production Memory System and Evaluation Spikes** - Phases 20-25 and 25.1 shipped 2026-07-02.
  - Archive: [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) | [v1.3-REQUIREMENTS.md](milestones/v1.3-REQUIREMENTS.md) | [v1.3-MILESTONE-AUDIT.md](milestones/v1.3-MILESTONE-AUDIT.md)
- Complete **v1.4 Long-Term Memory Productization** - Phases 26-32 shipped 2026-07-03. Productized long-term memory with Hindsight backend, singleton wiring, and contract event observability. Audit passed (20/20 requirements).
  - Archive: [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md) | [v1.4-REQUIREMENTS.md](milestones/v1.4-REQUIREMENTS.md) | [v1.4-MILESTONE-AUDIT.md](milestones/v1.4-MILESTONE-AUDIT.md)
- Complete **v1.5 V2 Acceptance Closure** - Phases 33-35 shipped 2026-07-03. Audited all unchecked V2 Active requirements, closed code gaps, produced acceptance readiness report. Audit passed (23/23 requirements). Autonomous closure READY; V2 acceptance BLOCKED ON HUMAN GATES (Phase 5 live WeCom UAT + Phase 8 five-workday lawyer trial).
  - Archive: [v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md) | [v1.5-REQUIREMENTS.md](milestones/v1.5-REQUIREMENTS.md) | [v1.5-MILESTONE-AUDIT.md](milestones/v1.5-MILESTONE-AUDIT.md) | [v1.5-V2-ACCEPTANCE-READINESS.md](milestones/v1.5-V2-ACCEPTANCE-READINESS.md)
- Complete **v1.6 M2 Multi-Backend & Platform Extensions** - Phases 36-44 shipped 2026-07-04. Codex + provider_model adapter prototypes, independent Router Service, Skill Registry read, conversation-read-view completion, Admin Console API, QQBot channel loop, and gate coverage meta-test. Audit passed (22/22 requirements, 19/19 gates green, 969 tests).
  - Archive: [v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md) | [v1.6-REQUIREMENTS.md](milestones/v1.6-REQUIREMENTS.md) | [v1.6-MILESTONE-AUDIT.md](milestones/v1.6-MILESTONE-AUDIT.md)
- Complete **v1.7 M3 Platform Extensions** - Phases 45-57 + 57.1 gap closure shipped 2026-07-06. Promoted adapter prototypes to production-grade, extended platform surface (MCP, model gateway, multi-agent, skill write + hybrid routing), added operator and lawyer-facing Web UI, and introduced RBAC + multi-tenant isolation. Audit passed (38/38 requirements, 24/24 gates green, 1,547+ tests).
  - Archive: [v1.7-ROADMAP.md](milestones/v1.7-ROADMAP.md) | [v1.7-REQUIREMENTS.md](milestones/v1.7-REQUIREMENTS.md) | [v1.7-MILESTONE-AUDIT.md](milestones/v1.7-MILESTONE-AUDIT.md)
- Complete **v1.8 QQBot Channel Production** - Phases 58-67 shipped 2026-07-09. Promoted QQBot from fixture-only proof to production-grade channel loop (signature, normalize, token, egress, rich media, session/ingress, adapter real IO, feedback+wakeup, smoke toolkit). Audit: gaps_found (host composition deferred; package-level 28/28 + 321 tests green). Live QQ smoke remains a human gate.
  - Archive: [v1.8-ROADMAP.md](milestones/v1.8-ROADMAP.md) | [v1.8-REQUIREMENTS.md](milestones/v1.8-REQUIREMENTS.md) | [v1.8-MILESTONE-AUDIT.md](milestones/v1.8-MILESTONE-AUDIT.md)
- ✅ **v1.9 QQBot Host Composition** - Phases 68-72 shipped 2026-07-10. Thin production webhook host, runtime registration, Protocol-path smoke hardening, controlled live HUMAN GATE. Audit passed (11/11 requirements).
  - Archive: [v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md) | [v1.9-REQUIREMENTS.md](milestones/v1.9-REQUIREMENTS.md) | [v1.9-MILESTONE-AUDIT.md](milestones/v1.9-MILESTONE-AUDIT.md)

## Current Milestone

Awaiting next milestone definition via `$gsd-new-milestone`.

**Carried human gates (not closed by v1.9):**

- Phase 5 live WeCom UAT
- Phase 8 five-workday lawyer trial (artifacts preserved at `.planning/phases/08-lawyer-trial-acceptance/`)
- Operator `--live` QQ OpenAPI acceptance (HUMAN GATE by design)

## Phases

No active phases. Next phase number continues from 73 after `$gsd-new-milestone`.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 68. Host Skeleton + Safety Baseline | v1.9 | 3/3 | Complete | 2026-07-10 |
| 69. Runtime Registration / Wiring | v1.9 | 3/3 | Complete | 2026-07-10 |
| 70. Webhook Composition Path | v1.9 | 3/3 | Complete | 2026-07-10 |
| 71. Smoke Protocol-Path Hardening | v1.9 | 3/3 | Complete | 2026-07-10 |
| 72. Controlled Live Integration | v1.9 | 2/2 | Complete | 2026-07-10 |

## Completed Milestones

<details>
<summary>✅ v1.9 QQBot Host Composition (Phases 68-72) — SHIPPED 2026-07-10</summary>

- [x] Phase 68: Host Skeleton + Safety Baseline (3/3 plans) — completed 2026-07-10
- [x] Phase 69: Runtime Registration / Wiring (3/3 plans) — completed 2026-07-10
- [x] Phase 70: Webhook Composition Path (3/3 plans) — completed 2026-07-10
- [x] Phase 71: Smoke Protocol-Path Hardening (3/3 plans) — completed 2026-07-10
- [x] Phase 72: Controlled Live Integration (2/2 plans) — completed 2026-07-10

**Full archive:** [v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md) | [v1.9-REQUIREMENTS.md](milestones/v1.9-REQUIREMENTS.md) | [v1.9-MILESTONE-AUDIT.md](milestones/v1.9-MILESTONE-AUDIT.md) | [v1.9-phases](milestones/v1.9-phases/)

**Closed v1.8 accepted gaps:** production host webhook composition; smoke Protocol-path hardening; controlled live path (acceptance remains HUMAN GATE).

</details>

<details>
<summary>✅ v1.8 QQBot Channel Production (Phases 58-67) — SHIPPED 2026-07-09</summary>

- [x] Phase 58: v1.8 Pre-Implementation Safety — completed 2026-07-07
- [x] Phase 59: Ed25519 Signature Verification + Validation Challenge — completed 2026-07-07
- [x] Phase 60: QQ Event Normalization — completed 2026-07-07
- [x] Phase 61: Access Token Manager — completed 2026-07-09
- [x] Phase 62: QQ Egress Sender — Text + Markdown + Keyboard — completed 2026-07-09
- [x] Phase 63: QQ Rich Media Inbound + Egress (P2) — completed 2026-07-09
- [x] Phase 64: QQBotSessionRuntime + QQBotIngressRuntime — completed 2026-07-09
- [x] Phase 65: Adapter Integration — Promote to Real IO — completed 2026-07-09
- [x] Phase 66: Feedback Loop Parity + Interaction Recall — completed 2026-07-09
- [x] Phase 67: One-Click Smoke-Test Toolkit — completed 2026-07-09

**Full archive:** [v1.8-ROADMAP.md](milestones/v1.8-ROADMAP.md) | [v1.8-REQUIREMENTS.md](milestones/v1.8-REQUIREMENTS.md) | [v1.8-MILESTONE-AUDIT.md](milestones/v1.8-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v1.7 M3 Platform Extensions (Phases 45-57.1) — SHIPPED 2026-07-06</summary>

- [x] Phase 45: M3 Pre-Implementation Safety (4/4 plans) — completed 2026-07-06
- [x] Phase 46: Streaming Events (A1) (1/1 plan) — completed 2026-07-06
- [x] Phase 47: Artifact Return (A2) (3/3 plans) — completed 2026-07-06
- [x] Phase 48: Multi-Provider Runners (A3) (3/3 plans) — completed 2026-07-06
- [x] Phase 49: Session Memory Wiring (A4) (3/3 plans) — completed 2026-07-06
- [x] Phase 50: MCP Connector Registry (B1) (3/3 plans) — completed 2026-07-06
- [x] Phase 51: RBAC (C1) (3/3 plans) — completed 2026-07-06
- [x] Phase 52: Skill Registry Write (B2) (2/2 plans) — completed 2026-07-06
- [x] Phase 53: Hybrid Routing (B3) (2/2 plans) — completed 2026-07-06
- [x] Phase 54: Model Provider Gateway (B4) (3/3 plans) — completed 2026-07-06
- [x] Phase 55: Multi-Agent Runtime Adapter (B5) (1/1 plan) — completed 2026-07-06
- [x] Phase 56: Multi-Tenant Isolation (C2) (2/2 plans) — completed 2026-07-06
- [x] Phase 57: Admin Web UI + Lawyer Web Chat (C3 + C4) (1/1 plan) — completed 2026-07-06
- [x] Phase 57.1: Gap Closure — TenantGuard wiring (1/1 plan) — completed 2026-07-07

</details>

<details>
<summary>✅ v1.6 M2 Multi-Backend & Platform Extensions (Phases 36-44) — SHIPPED 2026-07-04</summary>

- [x] Phase 36: M2 Pre-Implementation Safety
- [x] Phase 37: Skill Registry Read
- [x] Phase 38: Router Service
- [x] Phase 39: Codex Adapter Prototype
- [x] Phase 40: Provider Model Adapter Prototype
- [x] Phase 41: Conversation Read-View Completion
- [x] Phase 42: Admin Console API
- [x] Phase 43: QQBot Channel loop
- [x] Phase 44: M2 Gate Integration & Full Suite Verification

**Full archive:** [v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md) | [v1.6-REQUIREMENTS.md](milestones/v1.6-REQUIREMENTS.md) | [v1.6-MILESTONE-AUDIT.md](milestones/v1.6-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v1.5 V2 Acceptance Closure (Phases 33-35) — SHIPPED 2026-07-03</summary>

- [x] Phase 33: V2 Requirement Audit & Traceability Infrastructure
- [x] Phase 34: V2 Code Gap Closure
- [x] Phase 35: V2 Acceptance Readiness Report & Traceability Update

**Full archive:** [v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md) | [v1.5-REQUIREMENTS.md](milestones/v1.5-REQUIREMENTS.md) | [v1.5-MILESTONE-AUDIT.md](milestones/v1.5-MILESTONE-AUDIT.md) | [v1.5-V2-ACCEPTANCE-READINESS.md](milestones/v1.5-V2-ACCEPTANCE-READINESS.md)

</details>

## Backlog

No active backlog beyond v1.9 Future Requirements archived in [v1.9-REQUIREMENTS.md](milestones/v1.9-REQUIREMENTS.md) (HOST-F01..F03, PLAT-F01..F03). Promote candidates into the next milestone via `$gsd-new-milestone`.

---
*Last updated: 2026-07-10 after v1.9 QQBot Host Composition milestone complete*
