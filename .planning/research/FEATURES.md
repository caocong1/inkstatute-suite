# Features Research: v1.11 Product Console

**Domain:** Local/single-machine ops control plane — process orchestration, observability, auth, product polish
**Milestone:** v1.11 Product Console
**Researched:** 2026-07-13
**Confidence:** HIGH (InkStatute shipped admin-console-api/admin-web-ui/rbac/conversation-read-view/contract events; systemd/supervisor/pm2/admin-console patterns; SSE vs WebSocket tradeoffs for stdlib http.server)

## Scope Note

**Already shipped — do not re-scope as new table stakes:**
- Read-only Admin Console API + Admin Web UI (sessions/tasks/feedback/health/gates), RBAC roles (admin/operator/lawyer/viewer), feature flags default OFF
- WeCom + QQBot channel packages/hosts; dual-knob enable + secret refs at process edge
- Operator config store (channels/providers/catalog/vision) with CSRF-protected SSR forms
- Conversation read-view with cursor pagination, CSV/JSON export, `trace_id` reconstruction
- Contract event recording (AgentTurn, FeedbackEvent) via hermes-contract-layer
- Feedback service with dedup + classification
- Gate honesty banners + human gate status card
- HMAC-SHA256 signed RBAC tokens (`packages/rbac`) with role+tenant claims, 900s default TTL

**This document covers ONLY NEW v1.11 features:** process orchestration UI, real-time log viewing, report dashboards, contract event audit, token management, login session interface, product polish.

**Deployment constraint:** Local/single-machine, stdlib `http.server` SSR, no React SPA / new DB / new queue / TLS / reverse-proxy (per AGENTS.md + PROJECT.md).

---

## Feature Categories

### Process Orchestration

Console as control plane: start/stop/restart/status of WeCom/QQBot host child processes from the web UI, with config-save → orchestrate-restart to apply.

**Table stakes:**
- **Process status panel** — per-host (WeCom, QQBot) card showing running/stopped/unknown state, PID, uptime, last exit code, last started-at timestamp. Operators cannot operate blind. Complexity: LOW–MEDIUM. Depends on: existing host process entry points (new in this milestone), a small process registry (PID + state file or in-memory dict in the console process).
- **Start / stop / restart actions** — buttons that spawn/terminate the channel host subprocess via `subprocess.Popen` and signal handling (SIGTERM graceful, SIGKILL fallback after timeout). Complexity: MEDIUM. Depends on: runnable service entry points (stdlib `http.server` + signal handlers) shipped in this milestone; CSRF tokens (existing `admin_web_ui/csrf.py`) on every mutating action.
- **Config-save → restart-to-apply wiring** — today the runbook says "restart runtime to apply" manually; v1.11 should offer a one-click "Save & Restart" that persists config then restarts the affected host. Complexity: MEDIUM. Depends on: existing config POST handlers + new orchestration actions.
- **Honest state, not fake health** — show actual process state from the OS, not a guessed "enabled" boolean. If the console cannot see the PID, show "unknown / not managed by this console." Complexity: LOW. Aligns with existing gate-honesty pattern.
- **Graceful shutdown ordering** — stop waits for in-flight turns (or a bounded timeout) before killing; restart = stop-then-start, not kill-and-hope. Complexity: MEDIUM. Depends on: signal handlers in host entry points.
- **Failure visibility** — if start fails (port in use, missing env ref, import error), surface the stderr tail in the status card, not a silent 500. Complexity: LOW–MEDIUM.

**Differentiators:**
- **Effective-config + process-state combined view** — show dual-knob enable AND actual running state side by side ("enabled=true but process stopped" is the most common ops confusion). Complexity: MEDIUM. Builds on: existing dual-knob config view + new process status.
- **Per-host independent control** — WeCom can run while QQBot stopped, independent of provider selection (already architecturally true; console should make it obvious). Complexity: LOW.
- **Restart-only-affected-host** — saving WeCom config restarts only WeCom host, not QQBot. Complexity: LOW–MEDIUM. Depends on: per-section config handlers (existing).
- **Startup script / one-click launch** — `scripts/start_inkstatute.sh` (or `.ps1`) that boots admin-web-ui, admin-console-api, and enabled channel hosts with sane env defaults. Complexity: LOW. Pairs with `.env.example` completion (product polish).
- **Process ownership honesty** — console only manages processes it spawned; if an operator started a host manually outside the console, show "externally managed — restart not available" rather than fighting the OS. Complexity: LOW. Differentiator vs naive supervisors that double-spawn.

**Anti-features:**
- **Full process supervisor / init system (systemd/circumvent)** — rebuilding systemd/supervisord inside a stdlib HTTP server is scope explosion, race-prone, and worse than the OS. Local single-machine ops already have systemd/launchd/Terminal. *Alternative:* console spawns/inspects child processes it owns; document that production persistence should use systemd unit files. Complexity to build properly: VERY HIGH; value: LOW for local.
- **Auto-restart on crash with backoff (watchdog loop)** — tempting but a watchdog inside the same process that serves the UI creates single-point-of-failure coupling and infinite-restart storms. *Alternative:* surface crash + exit code; let operator or systemd restart. Complexity: HIGH; anti for local MVP.
- **Distributed process orchestration / remote hosts** — multi-node control plane is a cloud feature; v1.11 is single-machine. *Alternative:* local-only; remote orchestration is a later milestone if ever. Complexity: VERY HIGH.
- **Hot-reload of secrets/config into running processes** — partial-apply races, dual-knob desync, hard to test (already an anti-feature in v1.10 research). *Alternative:* restart-to-apply with one-click restart.
- **CPU/memory metrics streaming per process** — ops dashboard eye-candy; `psutil` dependency + polling load for a local console. *Alternative:* show PID + uptime + exit code; deep metrics belong in OS tooling. Complexity: MEDIUM; value: LOW.
- **Killing processes the console did not spawn** — PID-recycling safety hazard. *Alternative:* only manage PIDs recorded by this console's start action.

---

### Log Viewing

Real-time online viewing of WeCom/QQBot/adapter runtime logs with level filter and search.

**Table stakes:**
- **Log file discovery + tail view** — console reads the channel host log files (paths from config/env), renders the last N lines (e.g., 200) on a `/logs` page. Operators expect `tail -f` equivalent without SSH. Complexity: LOW–MEDIUM. Depends on: hosts writing to known log paths (structured or plain).
- **Level filter (DEBUG/INFO/WARN/ERROR)** — dropdown that filters displayed lines by severity. Complexity: LOW. Depends on: logs having parseable level prefixes (structured logging or convention).
- **Text search / grep** — substring filter over the visible log window. Complexity: LOW.
- **Per-host log source selector** — choose WeCom / QQBot / adapter / admin-console logs. Complexity: LOW. Depends on: per-host log path config.
- **Refresh / manual reload** — a "Refresh" button that re-reads the tail. Complexity: TRIVIAL. Table stakes because real-time streaming (below) is the differentiator, not the baseline.
- **No raw secrets in log display** — logs may contain ref names but must not echo resolved tokens/keys; display-time scrubbing or fail-closed logging policy. Complexity: LOW. Aligns with SAFE-02 + existing output boundary.

**Differentiators:**
- **Server-Sent Events (SSE) live tail** — `text/event-stream` endpoint that pushes new log lines as they arrive. SSE is the right choice for stdlib `http.server`: unidirectional (server→browser), works over plain HTTP, no WebSocket upgrade handshake, trivial to implement with a generator + `wfile.write`. Complexity: MEDIUM. This is the recommended real-time mechanism for this stack.
- **Follow / pause / clear-view controls** — like `tail -f` pause; stops the SSE stream from scrolling while operator reads. Complexity: LOW–MEDIUM.
- **trace_id correlation jump** — click a `trace_id` in a log line → jump to the contract event audit view filtered to that trace. Complexity: LOW–MEDIUM. Depends on: contract event audit view (this milestone) + trace_id present in logs.
- **Level color coding via CSS only** — server renders `<span class="log-warn">`; CSP already allows `style-src 'self' 'unsafe-inline'`. Complexity: TRIVIAL. Polish, not function.
- **Bounded buffer + backpressure** — SSE stream holds at most N lines in memory; if the browser is slow, drop oldest rather than OOM the console. Complexity: LOW–MEDIUM. Important for a long-running local server.

**Anti-features:**
- **WebSocket for log streaming** — bidirectional, requires upgrade handshake + frame handling + ping/pong in stdlib `http.server` (no async framework); adds complexity for zero benefit since log streaming is one-way. *Alternative:* SSE. Complexity to do well in stdlib: HIGH; value over SSE: NONE.
- **Polling every 1s for "real-time"** — wastes CPU, feels laggy, generates noise. *Alternative:* SSE push, or manual refresh with a longer poll interval (5–10s) only if SSE is deferred. Complexity: LOW but UX-poor.
- **Full-text search across all historical logs (Elasticsearch/Loki stack)** — scope explosion, new dependency, not local-single-machine friendly. *Alternative:* grep over the current tail window; ship historical search only if a later milestone adds a log store. Complexity: VERY HIGH.
- **Log aggregation from remote machines** — cloud feature. *Alternative:* local files only.
- **Storing logs in a database** — violates "no new DB" constraint and duplicates what the filesystem already does. *Alternative:* read log files directly.
- **Streaming logs that contain raw legal payloads** — privacy + SAFE-02 violation. *Alternative:* logs use `raw_payload_ref`; display scrubbing.

---

### Reports & Dashboards

Aggregation from event logs: session/task volume, completion rate, long-task success rate, feedback distribution.

**Table stakes:**
- **Volume counts** — sessions, tasks, turns, feedback events over a selectable time window (today / 7d / 30d). Complexity: LOW–MEDIUM. Depends on: conversation-read-view (existing) + contract event log (existing) as data sources; a small aggregation function that scans the read-view.
- **Completion / success rate** — % of tasks in terminal success state vs failed/cancelled; long-task success rate separately. Complexity: MEDIUM. Depends on: task state machine in platform-contract (existing) + read-view exposing status.
- **Feedback distribution** — counts by classification (positive/negative/neutral/escalated) and dedup-aware unique counts. Complexity: LOW–MEDIUM. Depends on: feedback service classification (existing).
- **Time-window selector** — today / 7d / 30d / custom range. Complexity: LOW. Custom range is MEDIUM if it needs date pickers in SSR.
- **Static snapshot, not live-updating** — reports are point-in-time aggregations; a "Refresh" button re-runs the query. Complexity: LOW. Table stakes because live-updating dashboards are a differentiator, not baseline.
- **CSV/JSON export of report tables** — operators expect to pull numbers into their own tools. Complexity: LOW. Reuse: existing conversation-read-view export patterns.
- **Empty-state honesty** — "No sessions in this window" rather than a blank chart. Complexity: TRIVIAL. Aligns with gate-honesty culture.

**Differentiators:**
- **Gate pass-rate dashboard** — extend existing `/gates` with pass-rate-over-time and feature-flag status visualization (PROJECT.md calls this out). Complexity: MEDIUM. Depends on: existing gates view (read-only) + gate results store.
- **Human-gate status visualization** — Phase 5 WeCom UAT / Phase 8 lawyer trial / QQ `--live` acceptance as explicit "not yet accepted" cards with evidence links. Complexity: LOW. Builds on: existing carried-human-gates card.
- **trace_id-linked drill-down** — click a metric (e.g., "3 failed long-tasks") → filtered contract event audit view for those traces. Complexity: MEDIUM. Depends on: contract event audit view (this milestone).
- **Feedback → turn linkage** — show which AgentTurns received negative feedback, jump to audit. Complexity: MEDIUM. Depends on: feedback dedup + AgentTurn recording (existing).
- **Cost/latency hints from model-gateway** — if model-gateway is enabled, surface per-provider token spend + p50/p95 latency. Complexity: MEDIUM–HIGH. Depends on: model-gateway cost_tracker (exists). Differentiator but optional; defer if gateway not in deployment.

**Anti-features:**
- **Time-series database (Prometheus/Influx)** — new dependency, new ops burden, violates "no new DB." *Alternative:* compute aggregations on-demand from the event log/read-view. Complexity: VERY HIGH.
- **Live-updating animated charts (React SPA)** — violates no-SPA constraint; SSR + refresh button is enough. *Alternative:* server-rendered tables/SVG on refresh. Complexity: HIGH if SPA; LOW if SSR.
- **Custom report builder / SQL editor** — scope explosion, security surface. *Alternative:* fixed report templates + CSV export for custom analysis. Complexity: HIGH.
- **Predictive analytics / anomaly detection** — ML feature, not ops console table stakes. *Alternative:* raw numbers + operator judgment. Complexity: VERY HIGH.
- **Multi-tenant spend allocation / billing** — cloud SaaS feature. *Alternative:* single-tenant aggregate. Complexity: HIGH.
- **Claiming report numbers as live-acceptance evidence** — reports show operational volume, not human-gate closure. *Alternative:* gate-honesty notice on every report page (existing pattern).

---

### Contract Event Audit

AgentTurn/FeedbackEvent stream view with trace_id tracking.

**Table stakes:**
- **Event stream view** — `/audit` page listing AgentTurn + FeedbackEvent records in reverse-chronological order with cursor pagination (reuse conversation-read-view pagination). Complexity: LOW–MEDIUM. Depends on: contract event log (existing) + conversation-read-view read model (existing).
- **trace_id filter + reconstruction** — enter/select a `trace_id` → see the full ordered event chain (turn → feedback → sub-events) for that trace. Complexity: MEDIUM. Depends on: `get_task_by_trace_id` already in tenant_read_model; `execution_trace.trace_id` in platform-contract schema (existing).
- **Event type filter** — AgentTurn only / FeedbackEvent only / all. Complexity: LOW.
- **Field allowlist (no secrets, no raw payloads)** — display refs (`raw_payload_ref`) not resolved values; reuse admin-console-api field allowlist (existing). Complexity: LOW. Aligns with SAFE-02.
- **Timestamp + actor + role per event** — who/when/what-type. Complexity: LOW. Depends on: contract event fields (existing).
- **CSV/JSON export** — pull an audit slice for compliance review. Complexity: LOW. Reuse: existing export module.

**Differentiators:**
- **Turn ↔ feedback linkage view** — for a given AgentTurn, show attached FeedbackEvent(s) with classification + dedup state. Complexity: MEDIUM. Depends on: feedback service dedup (existing) + AgentTurn recording (existing).
- **trace_id jump from logs and reports** — cross-link from log lines and report metrics into the audit view (bidirectional with log viewing + reports). Complexity: LOW–MEDIUM. High UX value; ties the three observability surfaces together.
- **Event ordering guarantee visualization** — show sequence numbers / occurred_at so operators can verify causal order, not just list order. Complexity: LOW.
- **Privacy-scrubbed preview** — optional `raw_payload_ref` preview that resolves only if the operator has admin role and the payload is non-sensitive; fail-closed otherwise. Complexity: MEDIUM. Must respect output boundary + SAFE-02.
- **Audit of config changes** — who changed which config field when (field-level diff, refs redacted). Complexity: MEDIUM. Note: v1.10 research listed this as a differentiator for config; in v1.11 it becomes part of the unified audit surface. Depends on: config change logging (may need a small append-only change log).

**Anti-features:**
- **Storing raw legal payloads / full text in audit** — SAFE-02 violation; contract logs prefer refs. *Alternative:* refs only, with admin-gated preview. Complexity: LOW to avoid.
- **Immutable blockchain-style event chaining** — over-engineering for a local ops console; HMAC + append-only file is enough. *Alternative:* append-only JSONL with sequence numbers. Complexity: VERY HIGH; value: NONE for local.
- **Real-time event stream over WebSocket** — same reasoning as logs; SSE if live is wanted. *Alternative:* SSE or refresh. Complexity: HIGH for WS.
- **Editing / redacting past audit events from the UI** — audit trails must be append-only; mutable audit destroys the purpose. *Alternative:* append-only; corrections are new events. Complexity: LOW to avoid building.
- **Full-text search over event payloads** — privacy + performance; payloads are refs. *Alternative:* search over metadata fields (trace_id, type, actor, time). Complexity: MEDIUM if scoped to metadata; VERY HIGH + unsafe if payloads.
- **Cross-tenant audit without explicit tenant filter** — tenant isolation must be enforced (existing RBAC tenant claim). *Alternative:* tenant-scoped queries only. Complexity: LOW to enforce.

---

### Auth (Token + Session)

Token management (issue/revoke/expire) + login session interface (reserved username/password + session cookie, MVP token-only but extensible).

**Table stakes:**
- **Token management page** — `/auth/tokens` listing issued tokens (role, tenant, issued-at, expires-at, last-used-at) with issue + revoke actions. Complexity: MEDIUM. Depends on: existing `packages/rbac` token issue/verify (existing) + a token registry (new: in-memory or JSON file since no new DB).
- **Issue token with role + tenant + TTL** — form to mint a new RBAC token for a given role/tenant with selectable TTL. Complexity: LOW–MEDIUM. Reuse: `rbac.token.issue_token` (existing).
- **Revoke token** — mark a token as revoked before its natural expiry. Complexity: MEDIUM. *Note:* current RBAC tokens are stateless HMAC — revocation requires a revocation list (denylist) checked at verify time. This is the main new piece of logic. Depends on: a small revocation store (JSON file or in-memory with persistence).
- **Expiry visibility** — show exp timestamp; expired tokens auto-fail (existing `verify_token` already rejects expired). Complexity: LOW.
- **CSRF on all token mutate actions** — reuse existing `admin_web_ui/csrf.py`. Complexity: TRIVIAL (existing).
- **Never display token secret after first issuance** — show token once on issue, then only a fingerprint/hash thereafter. Complexity: LOW. Aligns with secret-ref-only culture.
- **Login session interface (reserved, MVP token-only)** — a `/login` page that accepts username/password but in MVP validates against a configured operator credential (env or config) and issues an RBAC token stored in a session cookie. Complexity: MEDIUM. *Extensible:* swap the credential check for a real user store later. Depends on: existing RBAC token + a session cookie helper (stdlib `http.cookies`).
- **Session cookie + token coexistence** — requests may authenticate via either `Authorization: Bearer` (API/tooling) or `session_cookie` (browser UI). Complexity: MEDIUM. The auth resolver checks cookie first, then bearer header. Depends on: existing `admin-console-api/auth.py` extended to accept both.

**Differentiators:**
- **Role-aware token issuance guardrails** — admin can issue operator/lawyer/viewer tokens but not escalate beyond own role; operator cannot issue admin tokens. Complexity: LOW–MEDIUM. Depends on: existing RBAC matrix.
- **Token last-used-at tracking** — update a timestamp on each successful verify; helps spot stale tokens. Complexity: MEDIUM. Requires a small side-store (not in the stateless HMAC token itself).
- **Session timeout + re-login** — session cookie expires; UI redirects to `/login`. Complexity: LOW. Aligns with 900s default TTL.
- **Audit log of token issue/revoke** — who issued/revoked which token when; feeds the contract event audit surface. Complexity: LOW–MEDIUM. Depends on: audit view (this milestone).
- **Reserved username/password from `.env`** — `INKSTATUTE_OPERATOR_USER` / `INKSTATUTE_OPERATOR_PASSWORD_HASH` for the MVP login; no user database needed. Complexity: LOW. Keeps "no new DB" constraint.
- **Logout (revoke session)** — clear cookie + mark session token revoked. Complexity: LOW.

**Anti-features:**
- **Full user management database (users table, password reset flow, email verification)** — scope explosion, new DB, cloud-SaaS feature. *Alternative:* env-based operator credential for MVP; document extensibility. Complexity: VERY HIGH.
- **OAuth/OIDC/SAML SSO** — cloud/enterprise feature; local single-machine does not need it. *Alternative:* token + simple session. Complexity: VERY HIGH.
- **MFA/TOTP** — valuable but not table stakes for a local ops console behind a trusted network; defer. *Alternative:* strong operator password + token TTL. Complexity: HIGH.
- **Storing raw passwords** — store a hash (or env ref to a hash) only. *Alternative:* `secrets.compare_digest` against a pre-hashed env value. Complexity: LOW to avoid the anti-feature.
- **Long-lived non-expiring tokens** — current default TTL is 900s; do not ship "never expires" as a UI option. *Alternative:* max TTL cap (e.g., 24h) in the issue form. Complexity: LOW.
- **Token issuance by non-admin roles** — lawyer/viewer must not mint tokens. *Alternative:* admin-only issuance. Complexity: LOW to enforce.
- **JWT with embedded claims + no revocation** — stateless JWT cannot be revoked without a denylist; if revocation is required (it is), plain HMAC token + revocation list is simpler and already shipped. *Alternative:* extend existing RBAC token with revocation list. Complexity: HIGH to retrofit JWT; LOW to extend existing.
- **Session storage in a database** — violates no-new-DB. *Alternative:* signed session cookie containing the RBAC token (stateless session). Complexity: LOW.

---

### Product Polish

Error pages, navigation, responsive layout, one-click startup, `.env.example` completion.

**Table stakes:**
- **404 / 500 error pages** — server-rendered, CSP-compliant, no stack trace leakage to browser (log full trace server-side, show generic message + request id to user). Complexity: LOW. Depends on: existing server error handling.
- **Consistent navigation** — sidebar or top nav present on every page with active-state highlighting; today's dashboard has cards but sub-pages may lack consistent nav. Complexity: LOW.
- **Responsive layout** — CSS so the console is usable on a laptop (not just desktop); mobile is bonus, not required for ops console. Complexity: LOW. CSP allows `style-src 'self' 'unsafe-inline'`.
- **`.env.example` completion** — every env var the runnable services need (ports, tokens, log paths, operator credential, RBAC secret) documented with safe placeholder values. Complexity: LOW. Critical for one-click startup.
- **One-click startup script** — `scripts/start_inkstatute.sh` (+ `.ps1`) that sources `.env`, starts admin-web-ui + admin-console-api + enabled channel hosts. Complexity: LOW. Pairs with process orchestration.
- **Loading / empty / error states on every data view** — no blank pages; "Loading…", "No data", "Failed to reach API" states. Complexity: LOW. Aligns with gate-honesty culture.
- **Gate-honesty notices on new pages** — every new observability/auth page carries the existing "this console does not close live acceptance gates" notice where relevant. Complexity: TRIVIAL. Reuse existing pattern.
- **README + runbook updates** — document the new endpoints, startup, token management, log paths. Complexity: LOW. Depends on: runbook pattern (existing).

**Differentiators:**
- **Request-id correlation across pages** — every error shows a short request id that maps to a log line; operator can grep logs. Complexity: LOW–MEDIUM. Pairs with log viewing.
- **Keyboard-accessible nav** — tabbable, focus-visible; ops users value speed. Complexity: LOW. Pure HTML/CSS, no JS framework.
- **Dark mode via CSS `prefers-color-scheme`** — ops consoles are often used at night. Complexity: LOW. CSP-safe.
- **Per-page "Last refreshed" timestamp** — explicit freshness indicator on read views. Complexity: TRIVIAL.
- **Status badges consistent across pages** — running/stopped, enabled/disabled, pass/fail, accepted/not-accepted use a shared badge component. Complexity: LOW. Reduces cognitive load.

**Anti-features:**
- **JavaScript SPA framework (React/Vue/Svelte)** — violates architecture constraint; SSR + minimal vanilla JS only. *Alternative:* stdlib `http.server` SSR + tiny inline JS for SSE/refresh. Complexity: HIGH to introduce; anti by constraint.
- **Heavy client-side charting library (Chart.js/D3 bundle)** — CSP + bundle size + no-SPA constraint. *Alternative:* server-rendered SVG/HTML tables. Complexity: MEDIUM if SVG; HIGH if JS lib.
- **Internationalization (i18n) framework** — scope expansion; console is operator-facing English/Chinese as-is. *Alternative:* hardcoded bilingual strings if needed. Complexity: HIGH.
- **Custom theming / white-label controls** — SaaS feature. *Alternative:* single fixed theme. Complexity: HIGH.
- **Onboarding wizard / tour** — overkill for a local ops console used by trained operators. *Alternative:* runbook + README. Complexity: MEDIUM.
- **Exposing stack traces / internal paths to the browser** — security + unprofessional. *Alternative:* generic error + server-side log. Complexity: LOW to avoid.
- **Auto-refresh meta-refresh on every page** — causes flicker + wasted requests. *Alternative:* explicit Refresh button + SSE where live matters. Complexity: LOW.

---

## Complexity Notes

| Feature | Complexity | Why |
|---------|------------|-----|
| Process status panel | LOW–MEDIUM | PID + state file; OS calls are cheap. |
| Start/stop/restart actions | MEDIUM | `subprocess.Popen` + signal handling + CSRF + failure capture. |
| Graceful shutdown ordering | MEDIUM | Bounded-timeout SIGTERM→SIGKILL; needs host signal handlers. |
| SSE log tail | MEDIUM | Generator + `wfile.write` + bounded buffer; no new deps. |
| WebSocket log tail | HIGH (anti) | Upgrade + frames + ping/pong in stdlib; not worth it. |
| Log level filter + search | LOW | String ops over a tail window. |
| Report volume counts | LOW–MEDIUM | Scan read-view; no aggregation store. |
| Completion/success rate | MEDIUM | Needs task state machine awareness. |
| Gate pass-rate dashboard | MEDIUM | Extend existing `/gates`. |
| Contract event stream view | LOW–MEDIUM | Reuses conversation-read-view pagination. |
| trace_id reconstruction | MEDIUM | `get_task_by_trace_id` exists; UI wiring is new. |
| Token management page | MEDIUM | Issue is trivial; revocation list is the new logic. |
| Token revocation | MEDIUM | Stateless HMAC needs a denylist + verify-time check. |
| Login session (MVP) | MEDIUM | Cookie + env credential; extensible later. |
| Session + token coexistence | MEDIUM | Auth resolver accepts cookie or bearer. |
| 404/500 pages | LOW | Stdlib error handlers. |
| One-click startup script | LOW | Shell + `.env`. |
| `.env.example` completion | LOW | Documentation. |
| Cost/latency hints | MEDIUM–HIGH | Only if model-gateway deployed; optional. |
| Full process supervisor | VERY HIGH (anti) | Rebuilding systemd. |
| Time-series DB | VERY HIGH (anti) | New dependency. |

**Simplest wins (do first):** `.env.example`, startup script, 404/500 pages, nav consistency, log tail view, report volume counts, token issue page.
**Hardest justified work:** process start/stop/restart with graceful shutdown, token revocation list, SSE log streaming, trace_id cross-linking across log/audit/report.

---

## Dependencies on Existing Features

| New Feature | Builds On (Already Shipped) | New Component Required |
|-------------|------------------------------|------------------------|
| Process orchestration (start/stop/restart) | Runnable host entry points (new this milestone), CSRF (`admin_web_ui/csrf.py`), dual-knob config view | Process registry (PID + state), orchestration route handlers, signal handlers in hosts |
| Config-save → restart | Existing config POST handlers (`config_api.py`) | Orchestration action wiring |
| Log viewing | Host log file paths (config/env), CSP, `html.escape` | `/logs` route, SSE endpoint, log path config |
| SSE log tail | stdlib `http.server`, CSP (`style-src 'unsafe-inline'`) | `text/event-stream` handler + bounded buffer |
| Reports (volume/completion/feedback) | `conversation-read-view` (cursor pagination, export), contract event log, feedback service classification, task state machine (`platform-contract`) | Aggregation functions, `/reports` route |
| Gate pass-rate dashboard | Existing `/gates` read view, gate results store | Time-series aggregation + visualization extension |
| Contract event audit view | Contract event log (hermes-contract-layer), `tenant_read_model.get_task_by_trace_id`, `execution_trace.trace_id` schema, field allowlist (`admin_console_api`) | `/audit` route, trace_id filter UI, event type filter |
| trace_id cross-link (logs↔audit↔reports) | `trace_id` in logs + contract events + read-view | Hyperlinks between pages with `?trace_id=` query param |
| Token issue | `packages/rbac` `issue_token` (HMAC, role+tenant, TTL) | `/auth/tokens` route, token registry (JSON file) |
| Token revoke | `packages/rbac` `verify_token` | Revocation list (denylist) + verify-time check |
| Token expiry visibility | `verify_token` already rejects expired | Display exp from token payload |
| Login session (MVP) | `packages/rbac` token, `admin-console-api/auth.py` | `/login` route, session cookie (stdlib `http.cookies`), env operator credential |
| Session + token coexistence | `auth.py` bearer check | Auth resolver: cookie-first, then bearer |
| Audit of auth actions | Contract event audit view (this milestone) | Append-only auth event log |
| 404/500 pages | `admin_web_ui/server.py` error handling | Error handler routes + templates |
| Navigation / responsive | Existing SSR templates, CSP | Shared nav partial + CSS |
| One-click startup | Runnable entry points (new this milestone) | `scripts/start_inkstatute.sh` |
| `.env.example` | Existing env var usage across services | Documented placeholder file |
| Gate-honesty notices on new pages | Existing gate-honesty banner pattern | Reuse partial on `/logs`, `/reports`, `/audit`, `/auth/tokens` |

**Key dependency chain:** Runnable service entry points (new) → process orchestration → config-save-restart. Contract event log (existing) → audit view → trace_id cross-link ← log viewing + reports. RBAC token (existing) → token management page → revocation list → login session → session+token coexistence.

**No new DB / queue / SPA dependency introduced by any table-stakes or differentiator feature above.** All new state (process registry, token revocation list, auth event log) can live as JSON files or in-memory dicts with file persistence, consistent with the operator config store pattern already shipped in v1.10.
