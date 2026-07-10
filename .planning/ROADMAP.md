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
- 🚧 **v1.9 QQBot Host Composition** - Phases 68-72 (in progress). Thin production webhook host, runtime registration, Protocol-path smoke hardening, controlled live HUMAN GATE.

## Current Milestone: v1.9 QQBot Host Composition

**Goal:** Assemble the v1.8 QQBot package-level channel into a deployable production webhook host path, harden smoke coverage across the full adapter/session Protocol stack, and enable controlled live QQ integration while keeping live acceptance as a human gate.

**Requirements:** `.planning/REQUIREMENTS.md` (11 requirements: HOST-01..03, REG-01..02, SMOKE-01..02, LIVE-01..02, SAFE-01..02)

**Key context:**

- Close v1.8 accepted audit gaps only — do not re-phase package signature/normalize/token/egress work.
- Host is composition-only (`services/qqbot-service/`); package owns crypto/normalize/send.
- Dual default-OFF knobs: `RuntimeFeatureFlags.qqbot_channel_enabled` → `QQBotChannelConfig.enabled`.
- Explicit `DefaultRunRuntime(channels=(QQBotChannelAdapter,))` injection — no auto-discovery.
- `--live` remains HUMAN GATE; CI must not auto-claim live acceptance.
- Preserve `.planning/phases/08-lawyer-trial-acceptance/` (carried human gate; do not delete).
- Phase numbering continues from v1.8 (next phase = 68).
- Critical path: P68 (host skeleton + safety) → P69 (runtime registration) → P70 (webhook composition) → P71 (smoke Protocol-path) → P72 (controlled live HUMAN GATE).

## Phases

- [x] **Phase 68: Host Skeleton + Safety Baseline** - Create `services/qqbot-service/` layout with empty deps, V2 gate entry, and ADAPTER-04 / secret-ref safety invariants before HTTP composition.
- [x] **Phase 69: Runtime Registration / Wiring** - Flag→config→adapter factory injects `QQBotChannelAdapter` into `DefaultRunRuntime.channels`; disabled path refuses live IO.
- [ ] **Phase 70: Webhook Composition Path** - Thin stdlib webhook host composes `verify_and_ack` → ingress/session/feedback → `deliver` with ACK-first semantics.
- [ ] **Phase 71: Smoke Protocol-Path Hardening** - Extend `--dry-run` to exercise full adapter/session Protocol path with Fake transports and sanitized evidence.
- [ ] **Phase 72: Controlled Live Integration** - Operator-run `--live` path + runbook remain HUMAN GATE; no CI auto-claim of live acceptance.

## Phase Details

### Phase 68: Host Skeleton + Safety Baseline

**Goal:** Operators and CI can verify a deployable `services/qqbot-service/` skeleton exists with ADAPTER-04 isolation and secret-ref discipline before any webhook composition ships.
**Depends on:** v1.8 completion (Phase 67)
**Requirements:** SAFE-01, SAFE-02
**Success Criteria** (what must be TRUE):

1. `services/qqbot-service/` exists with `pyproject.toml` `dependencies=[]` and a V2 gate PYTHONPATH entry covering the new service.
2. ChannelAdapter remains frozen at 6 methods; BackendAdapter remains frozen at 9 methods; no `wecom_service` import appears in the qqbot host/package path.
3. Feature flags that gate QQBot live IO default to OFF (including `qqbot_channel_enabled`).
4. Host config stores secrets as refs only; tests prove values are not committed and resolve only at process edge.
5. `.planning/phases/08-lawyer-trial-acceptance/` remains present (carried human-gate artifacts preserved).

**Plans:** 3 plans

Plans:

- [x] 68-01-PLAN.md — Create `services/qqbot-service/` skeleton with empty deps and V2 gate/compileall coverage
- [x] 68-02-PLAN.md — Host refs-only config + process-edge `resolve_secret_ref` (SAFE-02)
- [x] 68-03-PLAN.md — ADAPTER-04 host isolation: Protocol freeze, no-wecom, flag OFF, Phase 08 preserved

### Phase 69: Runtime Registration / Wiring

**Goal:** Host factory correctly maps dual default-OFF knobs and injects `QQBotChannelAdapter` into `DefaultRunRuntime.channels`, refusing live IO when disabled.
**Depends on:** Phase 68
**Requirements:** REG-01, REG-02, HOST-03
**Success Criteria** (what must be TRUE):

1. Host factory maps `RuntimeFeatureFlags.qqbot_channel_enabled` → `QQBotChannelConfig.enabled` and injects token_manager/transport only when `_live_io_ready`.
2. Host constructs `DefaultRunRuntime` with explicit `channels=(QQBotChannelAdapter,)` — no auto-discovery inside `platform-runtime`.
3. When QQBot is disabled (flags/config OFF), the composed path refuses live IO with explicit non-success behavior (e.g. 503/refuse) and does not call OpenAPI transports.
4. FakeBackend unit tests cover enabled vs disabled wiring without network.

**Plans:** 3 plans

Plans:

- [x] 69-01-PLAN.md — Flag→config factory + live-ready transport injection (REG-01)
- [x] 69-02-PLAN.md — Explicit `DefaultRunRuntime(channels=(adapter,))` registration (REG-02)
- [x] 69-03-PLAN.md — Disabled composed path refuses live IO / zero OpenAPI calls (HOST-03)

### Phase 70: Webhook Composition Path

**Goal:** Operators can deploy a thin InkStatute-owned QQBot webhook that composes package Protocol methods end-to-end with prompt verify-and-ACK before heavy agent work.
**Depends on:** Phase 69
**Requirements:** HOST-01, HOST-02
**Success Criteria** (what must be TRUE):

1. Operator can run a thin webhook host that composes `verify_and_ack` → ingress/session/feedback → `deliver` without reimplementing package crypto/normalize/send logic.
2. Webhook returns verify-and-ACK promptly for op=13 validation challenge and op=12 body ACK before heavy agent work.
3. Pure request handler + stdlib `http.server` wrapper capture raw body once, preserve signature verification, and apply output boundary on egress.
4. Unit tests with Fake transports prove the composition path without live QQ network.

**Plans:** 3 plans

Plans:

- [ ] 70-01-PLAN.md — Pure ACK-first webhook handler (op=13/op=12/refuse) (HOST-02)
- [ ] 70-02-PLAN.md — Post-ACK ingress/feedback/deliver Fake composition (HOST-01)
- [ ] 70-03-PLAN.md — stdlib http.server wrapper + raw-body proofs + README

### Phase 71: Smoke Protocol-Path Hardening

**Goal:** CI dry-run proves the full adapter/session Protocol stack (not leaf helpers only) and emits sanitized non-acceptance evidence.
**Depends on:** Phase 70
**Requirements:** SMOKE-01, SMOKE-02
**Success Criteria** (what must be TRUE):

1. `scripts/smoke_test.py --dry-run` exercises verify_and_ack → ingress/session → deliver using Fake transports (not leaf helpers only).
2. Protocol-path dry-run emits sanitized evidence under the existing allowlist schema with `not_live_acceptance=true` and no secrets/raw bodies.
3. Dry-run exits 0 in CI without network/Urllib live transports.
4. Smoke steps call the same host/package helpers the webhook composition uses (no parallel leaf-only path claimed as host-complete).

**Plans:** TBD

### Phase 72: Controlled Live Integration

**Goal:** Operators can run a controlled QQ live path with fail-closed env checks and documented enablement, while live acceptance remains an explicit HUMAN GATE.
**Depends on:** Phase 71
**Requirements:** LIVE-01, LIVE-02
**Success Criteria** (what must be TRUE):

1. Controlled `--live` path remains available with fail-closed env checks and is explicitly marked HUMAN GATE (CI/phase complete must not auto-claim live acceptance).
2. Operator runbook documents host enablement, dual-knob mapping, dry-run vs live, and interaction ACK safety windows.
3. Live evidence, when collected by an operator, stays sanitized/reference-first and is never required for autonomous phase completion.
4. Phase 5 live WeCom UAT and Phase 8 lawyer trial remain carried human gates — not redefined as v1.9 done.

**Plans:** TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 68. Host Skeleton + Safety Baseline | 3/3 | Complete   | 2026-07-10 |
| 69. Runtime Registration / Wiring | 3/3 | Complete   | 2026-07-10 |
| 70. Webhook Composition Path | 0/TBD | Not started | - |
| 71. Smoke Protocol-Path Hardening | 0/TBD | Not started | - |
| 72. Controlled Live Integration | 0/TBD | Not started | - |

## Completed Milestones

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

**Accepted gaps closed by v1.9:** production host webhook composition; smoke Protocol-path hardening; controlled live path (acceptance remains HUMAN GATE).

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

No active backlog beyond v1.9 Future Requirements in REQUIREMENTS.md (HOST-F01..F03, PLAT-F01..F03).

---
*Last updated: 2026-07-09 after v1.9 QQBot Host Composition roadmap creation*
