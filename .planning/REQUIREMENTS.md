# Requirements: 墨律 InkStatute — v1.11 Product Console

**Defined:** 2026-07-12
**Core Value:** Lawyers can use InkStatute's own WeCom lawyer assistant service while V2 records industry-neutral, privacy-aware contract events that are valid, replayable, feedback-linked, CI-verifiable, and agent-backend-neutral. Hermes lawfirm is the first agent backend, and Hermes gateway/meta/update/command notices must not leak to ordinary users.

**Milestone Goal:** Make the admin console a runnable, product-grade operations control plane — after configuring WeCom/QQBot/provider/model, operators can orchestrate channel host processes and use the channels, with full observability through reports, logs, contract event audit, and health/gate dashboards.

## v1.11 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Service Entry Points

- [x] **ENTRY-01**: Operator can start admin-web-ui as a standalone HTTP server via `python -m admin_web_ui` (or entry script) with configurable host/port, signal-handling graceful shutdown, and feature-flag gate
- [x] **ENTRY-02**: Operator can start admin-console-api as a standalone HTTP server via `python -m admin_console_api` (or entry script) with configurable host/port, signal-handling graceful shutdown, and feature-flag gate
- [x] **ENTRY-03**: admin-web-ui and admin-console-api use ThreadingHTTPServer (not single-threaded) so blocking operations (log reads, report aggregation, subprocess waits) do not freeze the UI; thread-safety of shared mutable state is audited and guarded

### Process Orchestration

- [ ] **ORCH-01**: Operator can view a process status panel in the console showing WeCom host and QQBot host process state (running/stopped, PID, uptime, last exit code) in real time
- [ ] **ORCH-02**: Operator can start, stop, and restart WeCom and QQBot host subprocesses from the console UI with graceful shutdown (SIGTERM → wait → SIGKILL escalation)
- [ ] **ORCH-03**: WeCom service has a runnable HTTP host entry point (`http_server.py` + `__main__.py`) mirroring qqbot-service, so it can be orchestrated as a subprocess
- [ ] **ORCH-04**: Saving channel config from the console orchestrates a restart of the affected channel host process (config-save → graceful restart → apply), consistent with existing `apply_semantics=restart_required`
- [ ] **ORCH-05**: Console probes each channel host's `/health` endpoint via urllib and displays live/unreachable status; process registry state persists across console restarts (re-attach to running children)

### Observability — Reports

- [ ] **OBS-01**: Operator can view a reports dashboard with aggregate statistics: session count, task completion rate, long-task success rate, and feedback distribution (up/down/none) over a selectable time range
- [ ] **OBS-02**: Reports aggregate on-demand from existing data sources (ContractLogReadModel, feedback queue, gate summary) without introducing a new database or time-series store
- [ ] **OBS-03**: Report aggregation uses bounded scanning (tail-read with limits, not full-file in-memory load) to avoid OOM on large event logs

### Observability — Log Viewing

- [ ] **OBS-04**: Operator can view runtime logs (contract events, runtime audit, feedback, child-process stdout/stderr) in the console with level filtering and keyword search
- [ ] **OBS-05**: Log viewing uses byte-offset tail-follow polling (seek + read-to-end + next_offset) so the browser can refresh without re-reading the full file; respects CSP (no EventSource/WebSocket, uses HTTP polling)
- [ ] **OBS-06**: Log viewer passes every line through existing privacy scrubbing (scrub_contract_payload) so secrets and raw legal payloads never appear in the console

### Observability — Contract Event Audit

- [ ] **OBS-07**: Operator can browse AgentTurn and FeedbackEvent contract events in a paginated audit trail view with timestamp, event type, session_id, and trace_id columns
- [ ] **OBS-08**: Operator can click a trace_id to see the full trace reconstruction (all events sharing that trace_id) using existing conversation-read-view trace reconstruction primitives

### Observability — Health & Gate Dashboard

- [ ] **OBS-09**: Operator can view an enhanced health/gate dashboard showing service health (admin API, WeCom host, QQBot host), gate pass rate, feature flag states, and carried human gate status in one unified view
- [ ] **OBS-10**: Health/gate dashboard preserves gate honesty — automated gate results and probe/smoke evidence never claim Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ live acceptance

### Auth — Login Session

- [ ] **AUTH-01**: Operator can log in to the console via username/password (env-based credentials for MVP) and receive a signed session cookie that authenticates subsequent requests
- [ ] **AUTH-02**: Session cookie auth coexists with existing Bearer token auth — Bearer header takes priority (API path unchanged), cookie auth is fallback for browser sessions; both paths pass through the same RBAC guard pipeline
- [ ] **AUTH-03**: Session cookies are HMAC-signed with RBAC_TOKEN_SECRET, have configurable TTL, and are invalidated on logout; session store interface is extensible (env-credential MVP, future cred store swappable)
- [ ] **AUTH-04**: Login/logout flows are CSRF-protected (login CSRF prevention) and session cookies use HttpOnly + SameSite attributes

### Product Polish

- [ ] **POLISH-01**: Console has proper 404 and 500 error pages (SSR, escaped, with navigation back to dashboard) instead of raw stack traces or blank responses
- [ ] **POLISH-02**: Console navigation is consistent across all pages — dashboard, config, observability, and auth pages share a common nav header with active-state indication
- [ ] **POLISH-03**: Console layout is responsive and readable on common laptop/desktop widths (no mobile-first requirement, but no horizontal scroll on 1280px)
- [ ] **POLISH-04**: A one-click startup script (`start-console.sh` or equivalent) launches admin-web-ui + admin-console-api with sensible defaults, env loading, and PID tracking
- [ ] **POLISH-05**: `.env.example` documents all new environment variables (ports, flags, credentials, log paths, session TTL) with inline comments explaining each variable

## Future Requirements

Deferred beyond v1.11. Tracked but not in current roadmap.

### Config / Ops (carried from v1.10)
- **CFG-F01**: Hot-reload operator config without process restart
- **CFG-F02**: Config change audit trail (who/when/field diffs; never resolved secrets)
- **CFG-F03**: Effective-config / dual-knob audit dashboard beyond MVP visibility

### Provider (carried from v1.10)
- **PROV-F01**: Live `/models` refresh for custom endpoints with short cache + explicit allowlist
- **PROV-F02**: LiteLLM-style budgets / virtual keys control plane
- **PROV-F03**: Per-lawyer self-serve model switching

### Vision (carried from v1.10)
- **VIS-F01**: Optional classical OCR enhancer alongside VLM (not sole vision path)
- **VIS-F02**: User-visible "正在识别图片…" service notice polish as first-class product copy variants

### Host / Ops (carried from v1.9)
- **HOST-F01**: Durable wakeup/idempotency stores for multi-instance hosts
- **HOST-F02**: Async verify→enqueue→ACK queue under load
- **HOST-F03**: Host health/readiness endpoints aligned with admin-console views

### Console (new from v1.11)
- **CON-F01**: RBAC token management UI (issue/revoke/expire management page with denylist)
- **CON-F02**: SSE-based real-time log streaming (replaces polling when CSP allows)
- **CON-F03**: User credential store (replace env-based login with persisted user DB)
- **CON-F04**: Multi-user session management (active sessions list, force logout)
- **CON-F05**: TLS/HTTPS support with reverse-proxy guidance for production deployment
- **CON-F06**: Process auto-restart watchdog (supervisor-mode crash recovery)
- **CON-F07**: Report export (CSV/JSON download of dashboard data)
- **CON-F08**: Config diff viewer (before/after comparison on config save)

## Out of Scope

Explicitly excluded for v1.11. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Flask/FastAPI/Django or any external web framework | AGENTS.md: keep stdlib http.server SSR |
| React/Vue/Vite SPA or any frontend framework | AGENTS.md: prefer stdlib SSR, no new SPA stack |
| PostgreSQL/Redis/MongoDB or any external database | AGENTS.md: no new DB unless PRD requires; atomic JSON suffices |
| WebSocket or SSE libraries for real-time push | CSP blocks EventSource; polling is sufficient for local ops |
| psutil or external process management libraries | stdlib subprocess.Popen suffices for local orchestration |
| celery/dramatiq/rq or any task queue | AGENTS.md: no new queue; synchronous orchestration is MVP |
| Token management UI page (issue/revoke/expire dashboard) | Deferred to CON-F01; login session covers browser auth MVP |
| TLS/HTTPS termination in the console itself | Local/single-machine deployment; reverse-proxy is future (CON-F05) |
| Process auto-restart watchdog/supervisor | MVP is manual start/stop/restart; watchdog is future (CON-F06) |
| Auto-claim live WeCom/QQ acceptance from console UI | Carried human gates; CI honesty (DOC-02 preserved) |
| Edit Hermes `~/.hermes` / gateway / profile from this console | Breaks adapter boundary; Hermes is agent backend only |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENTRY-01 | Phase 79 | mapped |
| ENTRY-02 | Phase 79 | mapped |
| ENTRY-03 | Phase 79 | mapped |
| ORCH-01 | Phase 80 | mapped |
| ORCH-02 | Phase 80 | mapped |
| ORCH-03 | Phase 80 | mapped |
| ORCH-04 | Phase 80 | mapped |
| ORCH-05 | Phase 80 | mapped |
| OBS-01 | Phase 81 | mapped |
| OBS-02 | Phase 81 | mapped |
| OBS-03 | Phase 81 | mapped |
| OBS-04 | Phase 82 | mapped |
| OBS-05 | Phase 82 | mapped |
| OBS-06 | Phase 82 | mapped |
| OBS-07 | Phase 83 | mapped |
| OBS-08 | Phase 83 | mapped |
| OBS-09 | Phase 84 | mapped |
| OBS-10 | Phase 84 | mapped |
| AUTH-01 | Phase 85 | mapped |
| AUTH-02 | Phase 85 | mapped |
| AUTH-03 | Phase 85 | mapped |
| AUTH-04 | Phase 85 | mapped |
| POLISH-01 | Phase 86 | mapped |
| POLISH-02 | Phase 86 | mapped |
| POLISH-03 | Phase 86 | mapped |
| POLISH-04 | Phase 86 | mapped |
| POLISH-05 | Phase 86 | mapped |

**Coverage:**

- v1.11 requirements: 27 total (3 ENTRY + 5 ORCH + 10 OBS + 4 AUTH + 5 POLISH)
- Mapped to phases: 27/27 (100%)
- Unmapped: 0
- Phase 87 (Integration, Smoke & Gate Honesty) is a cross-phase verification phase with no direct requirement mapping; it verifies all 27 requirements end-to-end.

**Phase → Requirement map:**

| Phase | Theme | Requirements |
|-------|-------|--------------|
| 79 | Entry Points & Threading Foundation | ENTRY-01, ENTRY-02, ENTRY-03 |
| 80 | WeCom HTTP Host + Process Orchestration | ORCH-01, ORCH-02, ORCH-03, ORCH-04, ORCH-05 |
| 81 | Reports Dashboard | OBS-01, OBS-02, OBS-03 |
| 82 | Log Viewing | OBS-04, OBS-05, OBS-06 |
| 83 | Contract Event Audit | OBS-07, OBS-08 |
| 84 | Health & Gate Dashboard Enhancement | OBS-09, OBS-10 |
| 85 | Login Session Auth | AUTH-01, AUTH-02, AUTH-03, AUTH-04 |
| 86 | Product Polish | POLISH-01, POLISH-02, POLISH-03, POLISH-04, POLISH-05 |
| 87 | Integration, Smoke & Gate Honesty | (cross-phase verification; no direct mapping) |

---
*Requirements defined: 2026-07-12*
*Last updated: 2026-07-13 — traceability completed during v1.11 roadmap creation (27/27 requirements mapped to Phases 79–87)*
