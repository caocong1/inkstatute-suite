# Requirements: 墨律 InkStatute — v1.9 QQBot Host Composition

**Defined:** 2026-07-09
**Core Value:** Lawyers can use InkStatute's own WeCom lawyer assistant service while V2 records industry-neutral, privacy-aware contract events that are valid, replayable, feedback-linked, CI-verifiable, and agent-backend-neutral. Hermes lawfirm is the first agent backend, and Hermes gateway/meta/update/command notices must not leak to ordinary users.

**Milestone Goal:** Assemble the v1.8 QQBot package-level channel into a deployable production webhook host path, harden smoke coverage across the full adapter/session Protocol stack, and enable controlled live QQ integration while keeping live acceptance as a human gate.

## v1.9 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Host Webhook

- [ ] **HOST-01**: Operator can deploy a thin InkStatute-owned QQBot webhook host that composes `verify_and_ack` → ingress/session/feedback → `deliver` without reimplementing package crypto/normalize/send logic
- [ ] **HOST-02**: Webhook host returns verify-and-ACK promptly (op=13 validation challenge and op=12 body ACK) before heavy agent work
- [x] **HOST-03**: When QQBot is disabled (flags/config OFF), webhook refuses live IO with explicit non-success behavior (e.g. 503/refuse) and does not call OpenAPI transports

### Runtime Registration

- [x] **REG-01**: Host factory maps `RuntimeFeatureFlags.qqbot_channel_enabled` → `QQBotChannelConfig.enabled` and injects token_manager/transport only when live-ready (`_live_io_ready`)
- [x] **REG-02**: Host constructs `DefaultRunRuntime` with explicit `channels=(QQBotChannelAdapter,)` injection — no auto-discovery inside platform-runtime

### Smoke Hardening

- [ ] **SMOKE-01**: `scripts/smoke_test.py --dry-run` exercises the full adapter/session Protocol path (verify_and_ack → ingress/session → deliver) using Fake transports — not leaf helpers only
- [ ] **SMOKE-02**: Protocol-path dry-run emits sanitized evidence under the existing allowlist schema (`not_live_acceptance=true`; no secrets/raw bodies)

### Live Integration

- [ ] **LIVE-01**: Controlled `--live` path remains available with fail-closed env checks and is explicitly a HUMAN GATE (CI/phase complete must not auto-claim live acceptance)
- [ ] **LIVE-02**: Operator runbook documents host enablement, dual-knob mapping, dry-run vs live, and interaction ACK safety windows

### Safety Baseline

- [x] **SAFE-01**: Host layer preserves ADAPTER-04 invariants: Protocol freeze (ChannelAdapter 6 methods), no `wecom_service` import into qqbot host/package path, feature flags default OFF
- [x] **SAFE-02**: Secrets remain refs in config; values resolve only at process edge — never committed; evidence/logs stay reference-first

## Future Requirements

Deferred beyond v1.9. Tracked but not in current roadmap.

### Host / Ops

- **HOST-F01**: Durable wakeup/idempotency stores for multi-instance hosts
- **HOST-F02**: Async verify→enqueue→ACK queue service under load
- **HOST-F03**: Host health/readiness endpoints aligned with admin-console views

### Platform

- **PLAT-F01**: Multi-channel mega-gateway unifying WeCom + QQ + WeChat in one process
- **PLAT-F02**: WebSocket QQ ingress mode
- **PLAT-F03**: Auto live acceptance / synthetic lawyer trial from smoke

## Out of Scope

Explicitly excluded for v1.9. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Reimplement signature/normalize/send in the host | Package owns channel logic; host is composition only |
| Unfreeze ChannelAdapter / add webhook Protocol method | Contract freeze; host HTTP calls existing 6 methods |
| Import wecom_service into qqbot host | ADAPTER-04 / no-wecom isolation |
| New queue/DB/Redis for v1.9 scale | Not required to close host gap; adds ops surface early |
| Enable QQBot flag by default | Accidental live IO; default-OFF safety culture |
| Auto-claim live QQ acceptance from CI | Live needs secrets, fresh msg_id, human judgment |
| Phase 5 live WeCom UAT as v1.9 done | Carried human gate — not host-composition scope |
| Phase 8 five-workday lawyer trial as v1.9 done | Carried human gate — not host-composition scope |
| Auto-synthesize/modify legal skills from QQ feedback | Legal safety: human-reviewed `skill_candidate` only |
| Delete `.planning/phases/08-lawyer-trial-acceptance/` | Carried human-gate artifacts must be preserved |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| HOST-01 | Phase 70 | Pending |
| HOST-02 | Phase 70 | Pending |
| HOST-03 | Phase 69 | Complete |
| REG-01 | Phase 69 | Complete |
| REG-02 | Phase 69 | Complete |
| SMOKE-01 | Phase 71 | Pending |
| SMOKE-02 | Phase 71 | Pending |
| LIVE-01 | Phase 72 | Pending |
| LIVE-02 | Phase 72 | Pending |
| SAFE-01 | Phase 68 | Complete |
| SAFE-02 | Phase 68 | Complete |

**Coverage:**

- v1.9 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0

| Phase | Requirements |
|-------|--------------|
| 68 Host Skeleton + Safety Baseline | SAFE-01, SAFE-02 |
| 69 Runtime Registration / Wiring | REG-01, REG-02, HOST-03 |
| 70 Webhook Composition Path | HOST-01, HOST-02 |
| 71 Smoke Protocol-Path Hardening | SMOKE-01, SMOKE-02 |
| 72 Controlled Live Integration | LIVE-01, LIVE-02 |

---
*Requirements defined: 2026-07-09*
*Last updated: 2026-07-09 after v1.9 roadmap creation (Phases 68-72)*
