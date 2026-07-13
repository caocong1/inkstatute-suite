# Architecture Research: v1.11 Product Console

**Milestone:** v1.11 Product Console
**Researched:** 2026-07-13
**Confidence:** HIGH (sourced from shipped admin-web-ui/admin-console-api pure handlers, qqbot-service `http_server.py` BaseHTTPRequestHandler pattern, hermes-contract-layer JSONL writer + `INKSTATUTE_CONTRACT_LOG_PATH`, conversation-read-view `ContractLogReadModel`, rbac HMAC token + CSRF signed-token, `.env.example` reserved host/port vars, PROJECT.md v1.11 target features)

## Current Architecture (key components)

The platform today is a set of **pure-function cores** wrapped by thin stdlib `http.server` handlers, with **no runnable service entry points** committed. Everything is stdlib-only (`dependencies = []`), persistence is atomic JSON/JSONL files, and there is no external DB/queue/web framework.

| Component | What exists | Entry point? |
|-----------|-------------|--------------|
| `services/admin-web-ui/` | `handle_admin_web_ui_request()` pure core (server.py, 1437 lines); SSR pages via `dashboard.py`/`channels.py`/`providers.py`/`catalog.py`/`vision.py`; `AdminApiClient` proxies to admin-console-api in-process; RBAC + CSRF + CSP | **No** — no `__main__.py`, no `HTTPServer` binding |
| `services/admin-console-api/` | `handle_admin_get`/`handle_admin_put` pure cores (api.py); views (sessions/tasks/feedback), health allowlist, gates via subprocess, config_api PUT; `_authenticate_admin` pipeline (flag → RBAC/static token → tenant scope) | **No** — no `__main__.py`, no server binding |
| `services/qqbot-service/` | `QQBotWebhookServer(BaseHTTPRequestHandler)` in `http_server.py` (POST-only webhook); `build_qqbot_wired_runtime` dual-knob wiring; `webhook.handle_qqbot_webhook_request` pure core | **Library only** — handler class exists, no `serve_forever`/signal entry |
| `services/wecom-service/` | `build_wecom_wired_runtime` wiring; ingress/session/delivery/output_policy pure modules; `runtime_audit.append_runtime_audit` JSONL writer | **No HTTP server at all** — library only (live bridge is a script) |
| `services/conversation-read-view/` | `ContractLogReadModel.from_records()` builds derived conversation/task/trace indexes from JSONL; cursor pagination; privacy scrub; CSV/JSON export | Library (read-only) |
| `services/hermes-contract-layer/` | `ContractEventWriter` append-only JSONL; `hook.record_contract_result`; `INKSTATUTE_CONTRACT_LOG_PATH` env | Library (writer) |
| `services/feedback-service/` | `FeedbackQueueItem` normalization + classification; pending queue | Library |
| `packages/operator-config/` | `OperatorConfigStore` atomic JSON; refs-only schemas; `apply_semantics=restart_required` metadata | Library (shipped v1.10) |
| `packages/rbac/` | HMAC-SHA256 `issue_token`/`verify_token`; `PERMISSIONS_MATRIX`; `RbacGuard` | Library |
| `packages/platform-runtime/` | `RuntimeFeatureFlags` (all default OFF); `DefaultRunRuntime` | Library |
| `scripts/` | `inkstatute_wecom_live_bridge.py` (operator-run, signal handling, subprocess to Hermes); `start-hindsight.sh`; `run_v2_gates.py` | Operator scripts, not service entries |

**Key existing patterns to preserve:**
- Pure-function handler cores (`handle_*`) are testable without `BaseHTTPRequestHandler`; server binding is a thin wrapper.
- Auth pipeline: feature-flag gate → `resolve_identity` (RBAC HMAC token OR static `ADMIN_API_TOKEN`) → `RbacGuard.check` → `TenantGuard`.
- CSRF: signed nonce+HMAC tokens bound to identity+route (csrf.py), no cookies/sessions today.
- Gates view already uses `subprocess.run` isolation (gates.py) — precedent for subprocess orchestration.
- Secret refs only; `resolve_secret_ref` at process edge; health allowlist excludes secret fields.

## New Components

### 1. Service Entry Points (`__main__.py`)
- **Purpose:** Make admin-web-ui, admin-console-api, qqbot-service, and wecom-service runnable as `python -m <pkg>` with port binding, signal handling, graceful shutdown.
- **Location:**
  - `services/admin-web-ui/src/admin_web_ui/__main__.py` (NEW)
  - `services/admin-console-api/src/admin_console_api/__main__.py` (NEW)
  - `services/qqbot-service/src/qqbot_service/__main__.py` (NEW)
  - `services/wecom-service/src/wecom_service/__main__.py` (NEW — also needs a thin `http_server.py` since none exists)
- **Integrates with:** Existing pure `handle_*` cores; `RuntimeFeatureFlags`; `OperatorConfigStore`; `rbac` secret; env vars already reserved in `.env.example` (`ADMIN_WEB_UI_HOST/PORT`, `ADMIN_CONSOLE_API_URL`).
- **Data flow:** `python -m admin_web_ui` → resolve env (host/port/secret/flags) → build `ThreadingHTTPServer` with a `BaseHTTPRequestHandler` subclass that delegates to `handle_admin_web_ui_request` → `serve_forever` → `signal.SIGTERM`/`SIGINT` → `shutdown()` + `server_close()`.
- **Design:** Each `__main__.py` is a thin adapter — no business logic. It reads env, constructs the same deps the tests inject (read_model from contract log path, feedback_queue, config_store, feature_flags), and binds the handler. A shared `services/_service_runtime.py` helper (or per-service `runtime.py`) can factor out signal handling + `ThreadingHTTPServer` wiring to avoid duplication. wecom-service needs a new `http_server.py` mirroring qqbot-service's pattern (POST callback + GET health).

### 2. Process Orchestrator (`ProcessSupervisor`)
- **Purpose:** Let the console act as a control plane that starts/stops/inspects WeCom and QQBot host processes, and restarts them after config save (apply_semantics=restart_required).
- **Location:** `services/admin-console-api/src/admin_console_api/orchestrator.py` (NEW) + `services/admin-web-ui/src/admin_web_ui/processes.py` (NEW SSR page).
- **Integrates with:** `subprocess.Popen` (stdlib); `OperatorConfigStore` (for channel enablement + restart signals); admin-console-api new `/processes` routes; admin-web-ui new `/processes` page.
- **Data flow:**
  ```
  Operator (web-ui /processes) → POST /processes/{channel}/start
    → admin-console-api orchestrator.start(channel)
    → subprocess.Popen([python, -m, qqbot_service, ...], env=..., stdout=log_file, stderr=log_file)
    → record ProcessRecord(pid, channel, status, started_at, log_path) in an in-memory + JSONL state file
  Health check: GET http://127.0.0.1:{port}/health on the child → map to running/degraded/stopped
  Stop: proc.terminate() (SIGTERM) → wait(timeout) → proc.kill() if needed
  Config save → PUT /config/channels → orchestrator.restart(channel) (stop then start)
  ```
- **Design:** `ProcessSupervisor` is a stdlib-only class holding `dict[channel, Popen]`. State persists to a small JSONL (`INKSTATUTE_PROCESS_STATE_PATH`, default under runtime dir) so a restarted console can re-attach (probe pid liveness via `poll()`). Health checks reuse each child's `/health` endpoint (the new `__main__.py` entries expose it). Graceful shutdown of the console itself terminates all children. **No new queue/DB** — Popen + JSONL state is sufficient for single-machine ops.

### 3. Log Viewer (`LogReader`)
- **Purpose:** Online viewing of WeCom/QQBot/adapter runtime logs with level filter and search; tail-follow pattern.
- **Location:** `services/admin-console-api/src/admin_console_api/logs.py` (NEW) + `services/admin-web-ui/src/admin_web_ui/logs.py` (NEW SSR page).
- **Integrates with:** Runtime JSONL files written by `ContractEventWriter` (`INKSTATUTE_CONTRACT_LOG_PATH` → events.jsonl), `append_runtime_audit` (runtime-audit.jsonl), feedback.jsonl, and the new `__main__.py` stdout/stderr log files (one per child process, path from `ProcessSupervisor`).
- **Data flow:**
  ```
  GET /logs/{source}?level=ERROR&seek=12345&q=keyword
    → LogReader.read(source, offset, level_filter, search)
    → open(log_path, "r"), seek(offset), read lines forward, parse JSONL, filter by level/search
    → return {lines: [...], next_offset: <byte_pos>, eof: bool}
  Tail-follow: client polls with last next_offset; server reads from byte offset onward
  ```
- **Design:** `LogReader` is a pure stdlib class (`open`/`seek`/`readline`). Sources are mapped by name → file path via a `LOG_SOURCES` registry (contract_events, runtime_audit, feedback, wecom_stdout, qqbot_stdout, etc.). Paths resolve from env (`INKSTATUTE_CONTRACT_LOG_PATH`, `INKSTATUTE_RUNTIME_DIR`, `ProcessSupervisor` log paths). **Privacy:** every line passes through `scrub_contract_payload` (already in conversation-read-view) before rendering — never raw legal payload or secrets. Level filter parses `level` field in JSONL or falls back to stderr text grep for non-JSON stdout logs.

### 4. Reports Aggregator (`ReportsAggregator`)
- **Purpose:** Session/task volume, completion rate, long-task success rate, feedback distribution aggregate stats.
- **Location:** `services/admin-console-api/src/admin_console_api/reports.py` (NEW) + `services/admin-web-ui/src/admin_web_ui/reports.py` (NEW SSR page).
- **Integrates with:** `ContractLogReadModel` (conversation-read-view) — already builds conversation/task/trace indexes from contract events; `feedback_queue` (feedback-service); `run_gate_summary` (gates.py subprocess); `RuntimeFeatureFlags` + health.
- **Data flow:**
  ```
  GET /reports?from=...&to=...
    → ReportsAggregator.build(read_model, feedback_queue, gate_summary, time_range)
    → read_model = ContractLogReadModel.from_records(load_records_from_jsonl(contract_log_path))
    → count conversations, tasks by status, completion_rate = completed/total
    → long_task_success = tasks with duration > threshold and status=completed
    → feedback distribution = classify feedback_queue items by classification.category
    → return {sessions: {total, ...}, tasks: {total, completed, completion_rate, long_task_success_rate}, feedback: {by_category, total}, gates: {passed, failed, rate}}
  ```
- **Design:** Pure function over the existing `ContractLogReadModel` + `feedback_queue` — **no new data source**. The read model already derives task status/duration; the aggregator just counts. Time-range filter reuses the existing `_ALLOWED_SESSION_FILTERS` pattern. This is read-only and routes through the same auth/allowlist pipeline.

### 5. Contract Event Audit View (`AuditView`)
- **Purpose:** AgentTurn/FeedbackEvent stream view with trace_id tracking (enhances existing sessions/tasks views).
- **Location:** `services/admin-console-api/src/admin_console_api/audit.py` (NEW) + `services/admin-web-ui/src/admin_web_ui/audit.py` (NEW SSR page).
- **Integrates with:** `ContractLogReadModel._trace_events` (already stored but not exposed as a stream); `load_records_from_jsonl`; privacy scrub.
- **Data flow:** `GET /audit?trace_id=...` → filter records by trace_id → render chronological AgentTurn + FeedbackEvent stream with trace_id linking. Reuses `scrub_contract_payload` per line.
- **Design:** Thin read-only view over existing read-model internals; no new writer.

### 6. Session Auth (`SessionStore` + login route)
- **Purpose:** Reserved username/password login + session cookie interface; MVP token-only but extensible.
- **Location:** `services/admin-web-ui/src/admin_web_ui/sessions.py` (NEW — login page + cookie issue/verify); `packages/rbac/src/rbac/session.py` (NEW — signed session cookie helper, mirrors csrf.py HMAC pattern).
- **Integrates with:** Existing `_authenticate_admin` pipeline in both admin-web-ui server.py and admin-console-api api.py; `rbac.issue_token` (a session can wrap an RBAC token); `RbacGuard`.
- **Data flow:**
  ```
  GET /login → render login form (username/password)
  POST /login → verify credentials (MVP: single operator from env ADMIN_LOGIN_USER/ADMIN_LOGIN_PASS_HASH)
    → issue signed session cookie: Set-Cookie: inkstatute_session=<nonce>.<hmac>
    → cookie payload references an RBAC token (role=ADMIN/OPERATOR) issued server-side
  Subsequent requests: handler reads Cookie header → SessionStore.verify(cookie) → resolve_identity(token)
    → same RbacGuard pipeline as Bearer token
  Logout: clear cookie
  ```
- **Coexistence with token auth:** The auth pipeline gains an **ordered fallback**: (1) `Authorization: Bearer` header → `resolve_identity` (existing API/programmatic path, unchanged); (2) if no bearer header, check `Cookie: inkstatute_session=` → `SessionStore.verify` → unwrap RBAC token → `resolve_identity`. Both paths produce the same `Identity` and feed the same `RbacGuard`. The admin-console-api (JSON API) stays bearer-only; the admin-web-ui (browser) accepts cookie OR bearer. This keeps API clients unchanged while enabling browser sessions.
- **Design:** Session cookie is HMAC-signed (same stdlib pattern as csrf.py and rbac/token.py — no new crypto). MVP credential store is env vars (`ADMIN_LOGIN_USER`, `ADMIN_LOGIN_PASS_HASH` via `hashlib.pbkdf2_hmac`). The username/password DB is explicitly deferred — the interface (`SessionStore.issue`/`verify`, login route, cookie parsing) lands now so a real cred store can slot in later without handler changes. `HttpOnly`, `SameSite=Strict`, `Secure` (when not localhost) cookie attributes.

### 7. Token Management UI
- **Purpose:** RBAC token issue/revoke/expire management page.
- **Location:** `services/admin-console-api/src/admin_console_api/tokens.py` (NEW) + `services/admin-web-ui/src/admin_web_ui/tokens.py` (NEW SSR page).
- **Integrates with:** `rbac.issue_token`/`verify_token`; `RBAC_TOKEN_SECRET`; new `/tokens` routes; `PERMISSIONS_MATRIX` (admin-only).
- **Data flow:** `POST /tokens/issue {role, tenant_id, ttl}` → `issue_token(secret, ...)` → return token once (not stored). `GET /tokens` → list active tokens (MVP: stateless — tokens aren't persisted; list shows issue metadata if a token registry JSONL is added, or just the issue form + verify helper). Revoke = short TTL + rotation of `RBAC_TOKEN_SECRET` (documented).
- **Design:** Issue is a pure call to existing `rbac.issue_token`. A lightweight token registry JSONL (`INKSTATUTE_TOKEN_REGISTRY_PATH`) can record issued-token metadata (role, tenant, iat, exp — never the token itself) for the list view; revocation MVP is TTL + secret rotation.

## Modified Components

### `services/admin-web-ui/src/admin_web_ui/server.py`
- **Change:** Extend `_SECTION_MAP` with new routes (`/processes`, `/logs`, `/reports`, `/audit`, `/tokens`, `/login`, `/logout`); extend `_POST_ROUTES` for `/login`, `/processes/*/start|stop`, `/tokens/issue`; add Cookie parsing to `_extract_auth_header` path (ordered bearer-then-cookie); thread `ProcessSupervisor` + `LogReader` + `ReportsAggregator` deps through `handle_admin_web_ui_request` kwargs.
- **Why:** New pages need routing + auth; cookie auth must coexist with bearer without breaking API proxying.

### `services/admin-console-api/src/admin_console_api/api.py`
- **Change:** Add route dispatch in `handle_admin_get` for `/processes`, `/logs`, `/reports`, `/audit`, `/tokens`; extend `_authenticate_admin` to accept an optional session-cookie resolver (for the case where admin-console-api is hit directly by a browser via cookie); thread new deps (`ProcessSupervisor`, `LogReader`, `ReportsAggregator`) through handler kwargs.
- **Why:** Control-plane + observability data must flow through the same auth/allowlist/RBAC pipeline; no second auth stack.

### `packages/rbac/src/rbac/matrix.py`
- **Change:** Add `/processes` (ADMIN/OPERATOR), `/logs` (ADMIN/OPERATOR), `/reports` (ADMIN/OPERATOR/LAWYER/VIEWER read), `/audit` (ADMIN/OPERATOR/LAWYER), `/tokens` (ADMIN) to `PERMISSIONS_MATRIX`. Update `scripts/scan_rbac_annotations.py` expectations.
- **Why:** New routes need explicit role permissions; CI scan enforces every dispatched prefix has a matrix entry.

### `packages/platform-runtime/src/platform_runtime/feature_flags.py`
- **Change:** Add `process_orchestration_enabled: bool = False`, `log_viewing_enabled: bool = False`, `session_auth_enabled: bool = False` (all default OFF).
- **Why:** New lanes follow the existing default-OFF + `require_enabled` gate pattern; console features must be explicitly opt-in.

### `services/wecom-service/src/wecom_service/`
- **Change:** Add `http_server.py` (NEW, mirrors qqbot-service: `WeComWebhookServer(BaseHTTPRequestHandler)` + `read_request_body_once` + GET `/health`); add `__main__.py` (NEW).
- **Why:** wecom-service has no HTTP server today (only the operator script bridge); to be orchestratable it needs a runnable webhook host entry like qqbot-service.

### `services/qqbot-service/src/qqbot_service/`
- **Change:** Add `__main__.py` (NEW) binding `QQBotWebhookServer` to `ThreadingHTTPServer` with env host/port + signal handling + GET `/health` on the same handler.
- **Why:** Handler class exists but is not runnable; orchestrator needs a `python -m qqbot_service` target with a health endpoint.

### `.env.example`
- **Change:** Uncomment/complete `ADMIN_WEB_UI_HOST/PORT`, add `ADMIN_CONSOLE_API_HOST/PORT`, `INKSTATUTE_CONTRACT_LOG_PATH`, `INKSTATUTE_RUNTIME_DIR`, `INKSTATUTE_PROCESS_STATE_PATH`, `ADMIN_LOGIN_USER`, `ADMIN_LOGIN_PASS_HASH`, `LOG_VIEWING_ENABLED`, `PROCESS_ORCHESTRATION_ENABLED`, `SESSION_AUTH_ENABLED`.
- **Why:** One-click startup requires all env vars documented; PROJECT.md lists `.env.example` completion as product polish.

### `scripts/`
- **Change:** Add `start-console.sh` (NEW one-click startup: launches admin-console-api + admin-web-ui as background processes, prints URLs). Optionally `stop-console.sh`.
- **Why:** PROJECT.md target: "one-click startup script".

## Data Flow

### Runnable Console Startup
```
./scripts/start-console.sh
  → source .env
  → python -m admin_console_api (port 8081) &
  → python -m admin_web_ui    (port 8080) &
  → prints http://127.0.0.1:8080
Each __main__.py:
  → resolve env (host/port/secret/flags/config_path/contract_log_path)
  → build deps: OperatorConfigStore, ContractLogReadModel.from_records(...), feedback_queue, RuntimeFeatureFlags, ProcessSupervisor
  → ThreadingHTTPServer((host, port), Handler) with server.deps = deps
  → signal.signal(SIGTERM, lambda: server.shutdown())
  → server.serve_forever()
```

### Process Orchestration Flow
```
Operator browser → POST /processes/qqbot/start (CSRF + RBAC ADMIN/OPERATOR)
  → admin-web-ui proxies to admin-console-api
  → orchestrator.start("qqbot")
    → resolve channel config (OperatorConfigStore + flags dual-knob)
    → subprocess.Popen([sys.executable, "-m", "qqbot_service"],
                       env=filtered_env_with_secrets, stdout=log_file, stderr=log_file)
    → ProcessRecord(pid, channel, "running", started_at, log_path) → append to state JSONL
  → return 200 {pid, status, log_path}
Health poll (client-side JS or server-side on GET /processes):
  → orchestrator.health("qqbot") → requests.get("http://127.0.0.1:{port}/health") via urllib
  → map to running/degraded/stopped
Config save → restart:
  → PUT /config/channels succeeds → orchestrator.restart(channel) → stop() then start()
```

### Log Viewing Flow
```
GET /logs/contract_events?seek=0&level=ERROR&q=turn_123
  → admin-console-api logs.handle_logs(source, seek, level, q)
  → LogReader.read(LOG_SOURCES["contract_events"], seek, level, q)
    → path = env INKSTATUTE_CONTRACT_LOG_PATH
    → open(path), seek(seek), readline loop
    → json.loads each line, scrub_contract_payload(line)
    → filter: level match, q substring (on scrubbed text)
  → return {lines, next_offset, eof}
Browser polls with next_offset for tail-follow.
Privacy: scrub_contract_payload on every line; health allowlist excludes secret fields.
```

### Reports Aggregation Flow
```
GET /reports?from=2026-07-01&to=2026-07-13
  → ReportsAggregator.build(read_model, feedback_queue, gate_summary, time_range)
    → read_model.conversations (filtered by time) → session count
    → read_model.tasks → total, completed, completion_rate
    → long_task_success_rate = tasks[duration > LONG_TASK_THRESHOLD & status=completed] / tasks[duration > LONG_TASK_THRESHOLD]
    → feedback_queue items → group by classification.category → distribution
    → gate_summary (subprocess run_v2_gates.py --json-summary) → passed/failed/rate
  → return aggregated dict → SSR reports page
No new persistence — pure read over existing JSONL + in-memory queue.
```

### Session Auth Coexistence Flow
```
Browser request → admin-web-ui handler
  → _extract_auth_header(headers) → Bearer? 
    YES → resolve_identity(bearer) [existing API path, unchanged]
    NO  → parse Cookie: inkstatute_session=<nonce>.<sig>
      → SessionStore.verify(cookie, rbac_secret) → unwrap inner RBAC token
      → resolve_identity(inner_token) [same Identity/RbacGuard pipeline]
  → RbacGuard.check(identity.role, route)
API client request → admin-console-api
  → Bearer only (cookies not required for JSON API; optionally accepted)
```

## Suggested Build Order

1. **Service entry points (`__main__.py` + wecom `http_server.py`) — no orchestration yet**
   - Why first: every later feature (orchestration, log viewing, health dashboard) depends on runnable services with `/health` endpoints. Also the lowest-risk change (thin wrappers over existing pure cores).
   - Deliver: `python -m admin_web_ui`, `python -m admin_console_api`, `python -m qqbot_service`, `python -m wecom_service` all bind ports + handle SIGTERM. Add `start-console.sh`.
   - Depends on: nothing new (uses existing pure handlers + env).

2. **Feature flags + RBAC matrix + `.env.example` completion**
   - Why: new routes need default-OFF gates and matrix entries before handlers dispatch; CI scan enforces matrix coverage.
   - Depends on: #1 (routes exist to protect).

3. **Health/gate dashboard enhancement + Reports aggregator**
   - Why: pure read-only over existing `ContractLogReadModel` + `feedback_queue` + `run_gate_summary`; no subprocess management risk; proves the observability data path.
   - Depends on: #2 (flags/matrix).

4. **Contract event audit view (trace_id stream)**
   - Why: thin read-only over existing `_trace_events`; complements reports; no new infra.
   - Depends on: #2.

5. **Log viewer (`LogReader` + `/logs` routes + SSR page)**
   - Why: introduces file-read + scrub pattern; needed before orchestration (operators watch logs of processes they start). Privacy scrub is the main risk.
   - Depends on: #2.

6. **Process orchestrator (`ProcessSupervisor` + `/processes` routes + SSR page)**
   - Why: highest-complexity new component (subprocess lifecycle, health probes, restart-on-config-save). Needs runnable services (#1) + log viewing (#5) to be useful and debuggable.
   - Depends on: #1, #5.

7. **Token management UI (`/tokens` issue/verify)**
   - Why: wraps existing `rbac.issue_token`; lower risk; admin-only.
   - Depends on: #2.

8. **Session auth (`SessionStore` + `/login` + cookie coexistence)**
   - Why last among auth: it's the interface-reserving layer; MVP is token-only so session login is polish, not a blocker. Putting it last avoids destabilizing the auth pipeline early. The cookie/bearer coexistence change to `_authenticate_admin` touches both admin services and needs careful test evolution.
   - Depends on: #2, #7 (token issue reused for session inner token).

9. **Product polish: error pages, navigation, responsive layout, one-click script finalization**
   - Why: depends on all pages existing; pure SSR/CSS work.
   - Depends on: #1–#8.

**Parallelism:** After #2, items #3, #4, #5, #7 can proceed in parallel waves (all read-only, independent routes). #6 (orchestrator) waits for #1 + #5. #8 waits for #7.

**Explicit non-goals:** live WeCom UAT / lawyer trial / QQ `--live` acceptance (carried human gates); TLS/reverse-proxy; external DB/queue; React SPA; unfreezing ChannelAdapter/BackendAdapter Protocols; Hermes profile editing from console; hot-reload (restart-to-apply remains MVP per v1.10 decision).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| `__main__.py` entry pattern | HIGH | qqbot-service `http_server.py` already shows BaseHTTPRequestHandler + ThreadingHTTPServer pattern; pure cores are handler-agnostic |
| Process orchestration via subprocess.Popen | HIGH | gates.py already uses subprocess.run; stdlib Popen + poll + terminate is well-trodden; single-machine scope |
| Log viewing via file seek + scrub | HIGH | JSONL writers + `INKSTATUTE_CONTRACT_LOG_PATH` exist; `scrub_contract_payload` exists; tail-follow is seek+readline |
| Reports from existing read model | HIGH | `ContractLogReadModel` already derives conversations/tasks/trace; feedback_queue already classified |
| Session cookie coexistence | HIGH | csrf.py + rbac/token.py establish the HMAC-signed-token stdlib pattern; ordered bearer-then-cookie fallback is additive |
| wecom-service HTTP server | HIGH | qqbot-service http_server.py is the template; wecom wiring already composes adapter |
| Exact route names / flag names | MEDIUM | `/processes`, `/logs`, `/reports`, `/audit`, `/tokens` are recommendations; phase plans may adjust |
| Token registry persistence | MEDIUM | MVP may be stateless (issue + verify) with secret-rotation revocation; JSONL registry is optional |

## Sources

- `.planning/PROJECT.md` — v1.11 target features, deployment target, architecture constraint
- `services/admin-web-ui/src/admin_web_ui/server.py` — `handle_admin_web_ui_request` pure core, `_SECTION_MAP`, `_POST_ROUTES`, auth pipeline, CSRF pattern
- `services/admin-web-ui/src/admin_web_ui/api_client.py` — in-process proxy to admin-console-api
- `services/admin-web-ui/src/admin_web_ui/csrf.py` — signed nonce+HMAC token pattern (reusable for sessions)
- `services/admin-console-api/src/admin_console_api/api.py` — `handle_admin_get`/`handle_admin_put`, `_authenticate_admin` pipeline
- `services/admin-console-api/src/admin_console_api/auth.py` — static token + bearer extraction
- `services/admin-console-api/src/admin_console_api/health.py` — positive allowlist pattern
- `services/admin-console-api/src/admin_console_api/gates.py` — subprocess.run isolation precedent
- `services/admin-console-api/src/admin_console_api/views.py` — `ContractLogReadModel` + `scrub_contract_payload` usage
- `services/qqbot-service/src/qqbot_service/http_server.py` — `QQBotWebhookServer(BaseHTTPRequestHandler)` template
- `services/qqbot-service/src/qqbot_service/wiring.py` — dual-knob wired runtime composition
- `services/wecom-service/src/wecom_service/wiring.py` — WeCom wired runtime (no HTTP server today)
- `services/wecom-service/src/wecom_service/runtime_audit.py` — JSONL audit writer pattern
- `services/hermes-contract-layer/src/hermes_contract_layer/hook.py` — `INKSTATUTE_CONTRACT_LOG_PATH` env
- `services/hermes-contract-layer/src/hermes_contract_layer/writer.py` — append-only JSONL `ContractEventWriter`
- `services/conversation-read-view/src/conversation_read_view/read_model.py` — `ContractLogReadModel.from_records` derived indexes
- `services/feedback-service/src/feedback_service/queue.py` — `FeedbackQueueItem` + classification
- `packages/rbac/src/rbac/token.py` — HMAC-SHA256 `issue_token`/`verify_token`
- `packages/rbac/src/rbac/matrix.py` — `PERMISSIONS_MATRIX` (single source of truth)
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` — default-OFF flag pattern
- `.env.example` — reserved `ADMIN_WEB_UI_HOST/PORT`, `ADMIN_CONSOLE_API_URL`, `RBAC_TOKEN_SECRET`
- `scripts/inkstatute_wecom_live_bridge.py` — operator script with signal handling + subprocess to Hermes (precedent)
- `AGENTS.md` — stdlib-only, no new service/DB/queue unless plan requires, no secrets in git

---
*Architecture research for: v1.11 Product Console — runnable entry points, process orchestration, observability, auth, polish*
*Researched: 2026-07-13*
