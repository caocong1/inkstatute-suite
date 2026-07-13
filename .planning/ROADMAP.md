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
- Complete **v1.9 QQBot Host Composition** - Phases 68-72 shipped 2026-07-10. Thin production webhook host, runtime registration, Protocol-path smoke hardening, controlled live HUMAN GATE. Audit passed (11/11 requirements).
  - Archive: [v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md) | [v1.9-REQUIREMENTS.md](milestones/v1.9-REQUIREMENTS.md) | [v1.9-MILESTONE-AUDIT.md](milestones/v1.9-MILESTONE-AUDIT.md)
- Complete **v1.10 Operator Config Console** - Phases 73-78.1 shipped 2026-07-12. InkStatute-owned operator config for channels, providers/catalog, and vision routing without editing Hermes.
  - Audit: [v1.10-MILESTONE-AUDIT.md](v1.10-MILESTONE-AUDIT.md)

## Current Milestone

**v1.11 Product Console** — Phases 79–87 (planning)

**Goal:** Make the admin console a runnable, product-grade operations control plane — after configuring WeCom/QQBot/provider/model, operators can orchestrate channel host processes and use the channels, with full observability through reports, logs, contract event audit, and health/gate dashboards.

**Carried human gates (not closed by this milestone):**

- Phase 5 live WeCom UAT
- Phase 8 five-workday lawyer trial (artifacts preserved at `.planning/phases/08-lawyer-trial-acceptance/`)
- Operator `--live` QQ OpenAPI acceptance (HUMAN GATE by design)

**Stack constraints (enforced every phase):** stdlib-only (`dependencies = []`); no new DB/queue/SPA; no Flask/FastAPI/Django; no React/Vue SPA; no WebSocket/SSE libs (HTTP polling for logs); no `psutil`; no `celery`/`dramatiq`/`rq`; no TLS termination in-console; no process auto-restart watchdog. All new feature flags default OFF.

**Parallelism:** After Phase 79, Phases 81, 82, 83, 85 can proceed in parallel waves (all read-only or admin-only, independent routes). Phase 80 waits for 79. Phase 84 waits for 79 + 80. Phase 86 waits for 85. Phase 87 waits for all.

## Phases

- [ ] **Phase 79: Entry Points & Threading Foundation** - Runnable `__main__.py` entry points + ThreadingHTTPServer decision/audit (ENTRY-01, ENTRY-02, ENTRY-03)
- [ ] **Phase 80: WeCom HTTP Host + Process Orchestration** - WeCom `http_server.py` + ProcessSupervisor control plane (ORCH-01, ORCH-02, ORCH-03, ORCH-04, ORCH-05)
- [ ] **Phase 81: Reports Dashboard** - ReportsAggregator over existing read models (OBS-01, OBS-02, OBS-03)
- [ ] **Phase 82: Log Viewing** - Byte-offset tail-follow log viewer with privacy scrubbing (OBS-04, OBS-05, OBS-06)
- [ ] **Phase 83: Contract Event Audit** - Paginated audit trail + trace_id reconstruction (OBS-07, OBS-08)
- [ ] **Phase 84: Health & Gate Dashboard Enhancement** - Unified health/gate/flag dashboard with gate honesty (OBS-09, OBS-10)
- [ ] **Phase 85: Login Session Auth** - HMAC-signed session cookies coexisting with Bearer auth (AUTH-01, AUTH-02, AUTH-03, AUTH-04)
- [ ] **Phase 86: Product Polish** - Error pages, nav, responsive layout, one-click startup, env docs (POLISH-01, POLISH-02, POLISH-03, POLISH-04, POLISH-05)
- [ ] **Phase 87: Integration, Smoke & Gate Honesty** - Cross-phase verification, end-to-end smoke, gate-honesty audit (no direct requirement mapping; verifies all)

## Phase Details

### Phase 79: Entry Points & Threading Foundation

**Goal**: Every service is runnable as `python -m <pkg>` with configurable host/port, signal-handling graceful shutdown, and a ThreadingHTTPServer threading model that has been explicitly decided and audited for thread-safety of all shared mutable state before any feature work begins
**Depends on**: Nothing new (existing pure handlers + env); first v1.11 phase
**Requirements**: ENTRY-01, ENTRY-02, ENTRY-03
**Success Criteria** (what must be TRUE):

  1. Operator can start `admin-web-ui` and `admin-console-api` as standalone HTTP servers via `python -m <pkg>` (or entry script) with configurable host/port, SIGINT/SIGTERM graceful shutdown, and a feature-flag gate that refuses to boot when the service flag is OFF
  2. Both services bind `ThreadingHTTPServer` (not single-threaded `HTTPServer`) so blocking operations (log reads, report aggregation, subprocess waits) do not freeze the UI; a socket-level integration test boots each service on an ephemeral port and asserts concurrent requests do not serialize
  3. A threading-model decision artifact documents the ThreadingHTTPServer choice, and a thread-safety audit guards every shared mutable store (`OperatorConfigStore`, `feedback_queue`, `ContractLogReadModel`, process table) with per-store `threading.Lock` or copy-on-rebuild semantics — no unguarded read-modify-write cycle remains

**Plans**: TBD (plan-phase will define)
**UI hint**: no

### Phase 80: WeCom HTTP Host + Process Orchestration

**Goal**: WeCom service has a runnable HTTP host mirroring qqbot-service, and operators can start/stop/restart/inspect WeCom and QQBot host subprocesses from the console with graceful shutdown, config-save→restart wiring, and live health probes
**Depends on**: Phase 79 (runnable entry points + threading model)
**Requirements**: ORCH-01, ORCH-02, ORCH-03, ORCH-04, ORCH-05
**Success Criteria** (what must be TRUE):

  1. WeCom service has a runnable HTTP host entry point (`http_server.py` + `__main__.py`) mirroring qqbot-service (POST callback + GET `/health`), so it can be orchestrated as a subprocess
  2. Operator can view a process status panel showing WeCom and QQBot host state (running/stopped/unknown, PID, uptime, last exit code) in real time, and can start/stop/restart each host subprocess with SIGTERM→wait→SIGKILL escalation; secrets are passed to children via environment (never argv)
  3. Saving channel config from the console orchestrates a restart of only the affected channel host (config-save atomic commit → graceful restart → apply), consistent with `apply_semantics=restart_required`; a half-written config is never applied to the child
  4. Console probes each channel host's `/health` endpoint via urllib and displays live/unreachable status; process registry state persists across console restarts (re-attach to running children via PID file reconciliation, warning on orphaned entries without auto-killing unknown PIDs)

**Plans**: TBD (plan-phase will define)
**UI hint**: yes

### Phase 81: Reports Dashboard

**Goal**: Operators can view aggregate report statistics over a selectable time range, aggregated on-demand from existing data sources with bounded scanning and no new database
**Depends on**: Phase 79 (flags/matrix + threading model)
**Requirements**: OBS-01, OBS-02, OBS-03
**Success Criteria** (what must be TRUE):

  1. Operator can view a reports dashboard with aggregate statistics — session count, task completion rate, long-task success rate, and feedback distribution (up/down/none) — over a selectable time range (today/7d/30d)
  2. Reports aggregate on-demand from existing data sources (`ContractLogReadModel`, feedback queue, gate summary) without introducing a new database or time-series store; a "last built at" timestamp and explicit refresh action document staleness
  3. Report aggregation uses bounded scanning (tail-read with limits / reverse-iterate from EOF with early-exit for recent windows, not full-file in-memory load) to avoid OOM on large event logs; a perf test with a large fixture asserts bounded memory and sub-second response

**Plans**: TBD (plan-phase will define)
**UI hint**: yes

### Phase 82: Log Viewing

**Goal**: Operators can view runtime logs in the console with level filtering and keyword search via byte-offset HTTP polling, with every line privacy-scrubbed and no full-file reads
**Depends on**: Phase 79 (flags/matrix + threading model), Phase 80 (host logging config)
**Requirements**: OBS-04, OBS-05, OBS-06
**Success Criteria** (what must be TRUE):

  1. Operator can view runtime logs (contract events, runtime audit, feedback, child-process stdout/stderr) in the console with level filtering (DEBUG/INFO/WARN/ERROR) and keyword search, with a per-host source selector
  2. Log viewing uses byte-offset tail-follow polling (seek + read-to-end + next_offset) so the browser refreshes without re-reading the full file; respects CSP (no EventSource/WebSocket, HTTP polling only); rotation-aware cursor resets on file shrink/inode change
  3. Log viewer passes every line through existing privacy scrubbing (`scrub_contract_payload`) so secrets and raw legal payloads never appear in the console; a path-traversal guard validates service/file names against a fixed allowlist and rejects `..`/absolute/symlink paths

**Plans**: TBD (plan-phase will define)
**UI hint**: yes

### Phase 83: Contract Event Audit

**Goal**: Operators can browse AgentTurn and FeedbackEvent contract events in a paginated audit trail and reconstruct full traces by trace_id using existing conversation-read-view primitives
**Depends on**: Phase 79 (flags/matrix); Phases 81/82 (trace_id cross-link)
**Requirements**: OBS-07, OBS-08
**Success Criteria** (what must be TRUE):

  1. Operator can browse AgentTurn and FeedbackEvent contract events in a paginated audit trail view with timestamp, event type, session_id, and trace_id columns (reverse-chronological, cursor pagination, event-type filter)
  2. Operator can click a trace_id to see the full trace reconstruction (all events sharing that trace_id) using existing conversation-read-view trace reconstruction primitives; a field allowlist displays refs (not resolved secrets) and every value passes through `scrub_contract_payload`/`html.escape`

**Plans**: TBD (plan-phase will define)
**UI hint**: yes

### Phase 84: Health & Gate Dashboard Enhancement

**Goal**: Operators see a unified health/gate/flag dashboard with service health from child `/health` endpoints, gate pass rate, feature flag states, and carried human gate status — preserving gate honesty
**Depends on**: Phase 79 (flags/matrix), Phase 80 (health probes)
**Requirements**: OBS-09, OBS-10
**Success Criteria** (what must be TRUE):

  1. Operator can view an enhanced health/gate dashboard showing service health (admin API, WeCom host, QQBot host), gate pass rate, feature flag states, and carried human gate status in one unified view
  2. Health/gate dashboard preserves gate honesty — automated gate results and probe/smoke evidence never claim Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ live acceptance; human-gate rows render with a distinct non-green visual state ("HUMAN GATE — carried, not auto-closed") and no "mark human gate passed" control exists

**Plans**: TBD (plan-phase will define)
**UI hint**: yes

### Phase 85: Login Session Auth

**Goal**: Operators can log in via username/password (env-credential MVP) and receive an HMAC-signed session cookie that coexists with existing Bearer token auth through the same RBAC guard pipeline
**Depends on**: Phase 79 (flags/matrix)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04
**Success Criteria** (what must be TRUE):

  1. Operator can log in to the console via username/password (env-based credentials for MVP) and receive a signed session cookie that authenticates subsequent requests; logout invalidates the session
  2. Session cookie auth coexists with existing Bearer token auth — Bearer header takes priority (API path unchanged), cookie auth is fallback for browser sessions; both paths resolve to a single `Identity` and pass through the same `RbacGuard` (no route bypasses the guard)
  3. Session cookies are HMAC-signed with `RBAC_TOKEN_SECRET`, have configurable TTL, use `HttpOnly` + `SameSite` attributes, and rotate the session ID on successful login (session fixation prevention); the session store interface is extensible (env-credential MVP, future cred store swappable)
  4. Login/logout flows are CSRF-protected (login CSRF prevention — CSRF token issued on GET `/login`, validated on POST, both session cookie and CSRF token rotated after login)

**Plans**: TBD (plan-phase will define)
**UI hint**: yes

### Phase 86: Product Polish

**Goal**: The console is product-grade — proper error pages, consistent navigation, responsive layout, one-click startup, and complete env documentation
**Depends on**: Phases 79–85 (all pages must exist before polish)
**Requirements**: POLISH-01, POLISH-02, POLISH-03, POLISH-04, POLISH-05
**Success Criteria** (what must be TRUE):

  1. Console has proper 404 and 500 error pages (SSR, escaped, with navigation back to dashboard) instead of raw stack traces or blank responses; no stack trace or secret leaks to the browser
  2. Console navigation is consistent across all pages — dashboard, config, observability, and auth pages share a common nav header with active-state indication
  3. Console layout is responsive and readable on common laptop/desktop widths (no horizontal scroll on 1280px; mobile not required)
  4. A one-click startup script (`start-console.sh` or equivalent) launches admin-web-ui + admin-console-api with sensible defaults, env loading, and PID tracking
  5. `.env.example` documents all new environment variables (ports, flags, credentials, log paths, session TTL) with inline comments explaining each variable

**Plans**: TBD (plan-phase will define)
**UI hint**: yes

### Phase 87: Integration, Smoke & Gate Honesty

**Goal**: Cross-phase verification confirms the console works end-to-end as a product-grade operations control plane and that gate honesty, privacy, and stdlib-only constraints hold across all new surfaces
**Depends on**: Phases 79–86 (all feature phases complete)
**Requirements**: (no direct requirement mapping — verifies ENTRY-01..POLISH-05 end-to-end)
**Success Criteria** (what must be TRUE):

  1. An end-to-end smoke boots the console via the one-click startup script, logs in via session auth, starts a channel host subprocess, views its logs, browses the reports dashboard, and audits a contract event trace — all without errors and within stdlib-only constraints
  2. Gate-honesty audit confirms no new page, report, or dashboard auto-claims Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ `--live` acceptance (`not_live_acceptance` preserved across all new surfaces)
  3. Privacy/XSS audit confirms every new rendering path passes through `html.escape`/`scrub_contract_payload`, no token/secret/bearer literal appears in log files under tests, and every new state-changing route carries CSRF protection
  4. Stdlib-only constraint audit confirms no new third-party dependency, no new DB/queue/SPA, and every new feature flag defaults OFF

**Plans**: TBD (plan-phase will define)
**UI hint**: no

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 79. Entry Points & Threading Foundation | v1.11 | 0/? | Not started | — |
| 80. WeCom HTTP Host + Process Orchestration | v1.11 | 0/? | Not started | — |
| 81. Reports Dashboard | v1.11 | 0/? | Not started | — |
| 82. Log Viewing | v1.11 | 0/? | Not started | — |
| 83. Contract Event Audit | v1.11 | 0/? | Not started | — |
| 84. Health & Gate Dashboard Enhancement | v1.11 | 0/? | Not started | — |
| 85. Login Session Auth | v1.11 | 0/? | Not started | — |
| 86. Product Polish | v1.11 | 0/? | Not started | — |
| 87. Integration, Smoke & Gate Honesty | v1.11 | 0/? | Not started | — |

## Completed Milestones

<details>
<summary>✅ v1.10 Operator Config Console (Phases 73-78.1) — SHIPPED 2026-07-12</summary>

- [x] Phase 73: Operator Config Foundation (3/3 plans) — completed 2026-07-10
- [x] Phase 74: Admin Config API + RBAC (3/3 plans) — completed 2026-07-10
- [x] Phase 75: Channel Config Apply (5/5 plans) — completed 2026-07-10
- [x] Phase 76: Provider Registry + Model Catalog (4/4 plans) — completed 2026-07-11
- [x] Phase 77: Vision Routing Runtime (4/4 plans) — completed 2026-07-11
- [x] Phase 78: Console SSR, Docs & Gate Honesty (4/4 plans) — completed 2026-07-12
- [x] Phase 78.1: Close gap — wire VisionRouter into turn runtime (3/3 plans) — completed 2026-07-12

**Full archive:** [v1.10-MILESTONE-AUDIT.md](v1.10-MILESTONE-AUDIT.md)

**Key accomplishments:** InkStatute-owned operator config for channels, providers/catalog, and vision routing without editing Hermes; refs-only store with Hermes filesystem ban; dual-knob channel enablement; SSRF-safe provider probe; vision routing runtime wired into `DefaultRunRuntime`; CSRF-protected SSR config pages; gate-honesty banners.

</details>

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
- [x] Phase 41: Conversation Read View
- [x] Phase 42: Admin Console API
- [x] Phase 43: QQBot Channel Loop
- [x] Phase 44: Gate Coverage Meta-Test

**Full archive:** [v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md) | [v1.6-REQUIREMENTS.md](milestones/v1.6-REQUIREMENTS.md) | [v1.6-MILESTONE-AUDIT.md](milestones/v1.6-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v1.5 V2 Acceptance Closure (Phases 33-35) — SHIPPED 2026-07-03</summary>

- [x] Phase 33: V2 Acceptance Audit
- [x] Phase 34: Gap Closure
- [x] Phase 35: Acceptance Readiness Report

**Full archive:** [v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md) | [v1.5-REQUIREMENTS.md](milestones/v1.5-REQUIREMENTS.md) | [v1.5-MILESTONE-AUDIT.md](milestones/v1.5-MILESTONE-AUDIT.md) | [v1.5-V2-ACCEPTANCE-READINESS.md](milestones/v1.5-V2-ACCEPTANCE-READINESS.md)

</details>

<details>
<summary>✅ v1.4 Long-Term Memory Productization (Phases 26-32) — SHIPPED 2026-07-03</summary>

**Full archive:** [v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md) | [v1.4-REQUIREMENTS.md](milestones/v1.4-REQUIREMENTS.md) | [v1.4-MILESTONE-AUDIT.md](milestones/v1.4-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v1.3 Production Memory System and Evaluation Spikes (Phases 20-25.1) — SHIPPED 2026-07-02</summary>

**Full archive:** [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) | [v1.3-REQUIREMENTS.md](milestones/v1.3-REQUIREMENTS.md) | [v1.3-MILESTONE-AUDIT.md](milestones/v1.3-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v1.2 Conversational Context and Memory Foundation (Phases 14-19) — SHIPPED 2026-07-02</summary>

</details>

<details>
<summary>✅ v1.1 Platform Foundation (Phases 09-13) — SHIPPED 2026-06-30</summary>

</details>

<details>
<summary>✅ V2 PRD Foundation (Phases 1-8) — COMPLETED 2026-06-30</summary>

Live Phase 5 WeCom UAT and Phase 8 five-workday lawyer trial remain carried human gates.

</details>

---

*Roadmap updated: 2026-07-13 — v1.11 Product Console roadmap created (Phases 79–87)*
