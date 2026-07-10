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
- 🚧 **v1.10 Operator Config Console** - Phases 73-78 (in progress). InkStatute-owned operator config for channels, providers/catalog, and vision routing without editing Hermes.

## Current Milestone

**v1.10 Operator Config Console** — Phases 73–78

**Goal:** Deliver an InkStatute-owned operator configuration console so operators can configure QQ/WeCom channels, providers (built-in vendors + custom OpenAI-compatible), built-in model catalogs, and vision/image-routing (dedicated vision model when the main model lacks vision) — without editing Hermes.

**Carried human gates (not closed by this milestone):**

- Phase 5 live WeCom UAT
- Phase 8 five-workday lawyer trial (artifacts preserved at `.planning/phases/08-lawyer-trial-acceptance/`)
- Operator `--live` QQ OpenAPI acceptance (HUMAN GATE by design)

## Phases

- [ ] **Phase 73: Operator Config Foundation** - Refs-only store, schemas, validators, and default-OFF feature flag
- [ ] **Phase 74: Admin Config API + RBAC** - Flag-gated `/config/*` mutate surface with role checks; read views stay read-only
- [ ] **Phase 75: Channel Config Apply** - QQ/WeCom channel config apply with dual-knob visibility and secret-ref credentials
- [ ] **Phase 76: Provider Registry + Model Catalog** - Built-in vendors, custom OpenAI-compatible providers, catalog selection, connection probe
- [ ] **Phase 77: Vision Routing Runtime** - Vision policy + image-turn routing with fail-closed notices and output-boundary safety
- [ ] **Phase 78: Console SSR, Docs & Gate Honesty** - Complete SSR config pages, operator docs, and `not_live_acceptance` honesty

## Phase Details

### Phase 73: Operator Config Foundation

**Goal**: Operators have an InkStatute-owned, refs-only config authority that is off by default and never treats Hermes filesystem paths as config source of truth
**Depends on**: Nothing (first v1.10 phase; builds on shipped admin/channel/provider surfaces)
**Requirements**: CFG-01, CFG-02, CFG-03
**Success Criteria** (what must be TRUE):

  1. Operator can persist channel/provider/catalog/vision config documents in an InkStatute store that accepts secret refs only and never stores raw secret values
  2. When `operator_config_enabled` is OFF (default), config mutate paths refuse writes
  3. Config schemas/validators reject Hermes `~/.hermes` / profile filesystem paths as config authority

**Plans:** 3 plans

Plans:

- [x] 73-01-PLAN.md — Empty-deps package scaffold, refs-only schemas, shape-only secret-ref normalize
- [x] 73-02-PLAN.md — Document validators + Hermes filesystem/profile ban-list (CFG-03)
- [x] 73-03-PLAN.md — Atomic JSON store, operator_config_enabled gate, V2 gate registration

### Phase 74: Admin Config API + RBAC

**Goal**: Admin/operator roles can read and write config through an explicit `/config/*` API while lawyer/viewer roles cannot mutate and existing operational views stay read-only
**Depends on**: Phase 73
**Requirements**: ADM-01, ADM-03
**Success Criteria** (what must be TRUE):

  1. Admin/operator roles can GET and PUT config resources under `/config/*`
  2. Lawyer/viewer roles are denied config mutate (and cannot bypass via other admin routes)
  3. Existing sessions/tasks/feedback/health/gates views remain read-only; config writes only succeed on the explicit `/config/*` surface
  4. When the operator-config flag is OFF, PUT `/config/*` refuses writes even for admin/operator

**Plans**: TBD

### Phase 75: Channel Config Apply

**Goal**: Operators can configure QQ and WeCom channel enablement and credential refs with dual-knob effective state visible, without collapsing safety knobs or echoing resolved secrets
**Depends on**: Phase 74
**Requirements**: CHAN-01, CHAN-02, CHAN-03, CHAN-04
**Success Criteria** (what must be TRUE):

  1. Operator can configure QQBot channel settings (enable knobs, credential refs, callback-related refs) via admin config API (and channel SSR form when present)
  2. Operator can configure WeCom channel settings (enable knobs, credential refs) via admin config API (and channel SSR form when present)
  3. Operator can see dual-knob effective enablement (platform flag AND host enabled) for QQ and equivalent WeCom flags — UI/API does not collapse to a single bypass toggle
  4. Credential fields accept secret refs only (`env:…` / `secret://…`); GET responses never echo resolved secret values

**Plans**: TBD
**UI hint**: yes

### Phase 76: Provider Registry + Model Catalog

**Goal**: Operators can select built-in vendor providers or define custom OpenAI-compatible endpoints, pick a catalog main model with vision capability metadata, and probe connectivity without leaking secrets
**Depends on**: Phase 74 (can run in parallel with Phase 75 after 74)
**Requirements**: PROV-01, PROV-02, PROV-03, PROV-04
**Success Criteria** (what must be TRUE):

  1. Operator can select a built-in vendor provider profile (base URL + key ref conventions + catalog binding) without editing Hermes
  2. Operator can define a custom OpenAI-compatible provider (`api_base_url` + `api_key_ref` + explicit model allowlist)
  3. Operator can pick a main model from a built-in selectable catalog that includes `supports_vision` metadata
  4. Operator can run a non-destructive connection probe for main (and vision when configured) that fail-closes on missing refs and does not log response bodies/secrets

**Plans**: TBD
**UI hint**: yes

### Phase 77: Vision Routing Runtime

**Goal**: On image-bearing turns, runtime routes multimodal main vs vision→main mix (or fail-closed InkStatute notice) according to operator policy, without vision on text-only turns or meta leaks to lawyers
**Depends on**: Phase 76 (needs catalog `supports_vision`); Phase 75 optional for channel image ingress paths already shipped
**Requirements**: VIS-01, VIS-02, VIS-03, VIS-04
**Success Criteria** (what must be TRUE):

  1. Operator can configure vision routing mode (`auto` | `always_preprocess` | `main_only`) plus optional dedicated vision provider/model
  2. On image-bearing turns, runtime uses multimodal main when `supports_vision`; otherwise vision→main mix when vision is configured; otherwise fail-closed with an InkStatute-owned notice (never silent image drop)
  3. Text-only turns never invoke the vision model; contract/audit evidence stays reference-first (no raw image bytes in contract logs)
  4. Vision/provider error paths pass through the assistant output boundary (no provider stack traces or gateway meta to ordinary users)

**Plans**: TBD
**UI hint**: yes

### Phase 78: Console SSR, Docs & Gate Honesty

**Goal**: Operators have complete CSRF-protected SSR config pages and honest docs/smoke evidence that never auto-claims carried live acceptance gates
**Depends on**: Phases 75, 76, 77
**Requirements**: ADM-02, DOC-01, DOC-02
**Success Criteria** (what must be TRUE):

  1. Admin Web UI exposes config pages for channels, providers/catalog, and vision as SSR forms with CSRF protection, extending the existing stdlib admin-web-ui (not a new SPA stack)
  2. Operator docs (README / `.env.example` / runbook) document console fields ↔ env/ref keys, dual-knob, vision policy, and “do not edit Hermes for InkStatute providers”
  3. Config/smoke evidence never auto-claims Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ `--live` acceptance (`not_live_acceptance` honesty preserved)

**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 73. Operator Config Foundation | v1.10 | 3/3 | Complete   | 2026-07-10 |
| 74. Admin Config API + RBAC | v1.10 | 0/TBD | Not started | - |
| 75. Channel Config Apply | v1.10 | 0/TBD | Not started | - |
| 76. Provider Registry + Model Catalog | v1.10 | 0/TBD | Not started | - |
| 77. Vision Routing Runtime | v1.10 | 0/TBD | Not started | - |
| 78. Console SSR, Docs & Gate Honesty | v1.10 | 0/TBD | Not started | - |
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

v1.10 Future Requirements (deferred): CFG-F01..F03, PROV-F01..F03, VIS-F01..F02, HOST-F01..F03 — see [REQUIREMENTS.md](REQUIREMENTS.md). Promote via `$gsd-new-milestone` or `$gsd-review-backlog`.

---
*Last updated: 2026-07-10 — v1.10 Operator Config Console roadmap created (Phases 73–78)*
