# Research Summary: v1.11 Product Console

**Milestone:** v1.11 Product Console
**Researched:** 2026-07-13
**Confidence:** HIGH
**Deployment:** Local/single-machine, stdlib `http.server` SSR, no TLS/reverse-proxy/production-stack

**Milestone goal:** Make the admin console a runnable, product-grade operations control plane — start/stop channel host subprocesses, view real-time logs, aggregate report stats, audit contract events, manage RBAC tokens, and provide an extensible login-session interface.

**Already shipped (do not re-scope as new):** Read-only admin console API + web UI (sessions/tasks/feedback/health/gates), RBAC roles (admin/operator/lawyer/viewer) with HMAC-SHA256 tokens (900s TTL), feature flags default OFF, WeCom + QQBot channel packages with dual-knob enable + secret refs, operator config store with CSRF-protected SSR forms, conversation read-view with cursor pagination + CSV/JSON export + trace_id reconstruction, contract event recording (AgentTurn/FeedbackEvent), feedback service with dedup + classification, gate honesty banners + human gate status card.

---

## Stack Additions

All additions are **stdlib-only** (`dependencies = []` preserved). No new third-party deps, no new DB, no new queue, no SPA. Full detail: [STACK.md](STACK.md).

### What to use

| Addition | Stdlib module | Purpose |
|----------|---------------|---------|
| Runnable HTTP entry points | `http.server.ThreadingHTTPServer` + `argparse` + `signal` | Bind existing `BaseHTTPRequestHandler` subclasses to host/port with threaded handling + graceful SIGINT/SIGTERM shutdown |
| Process orchestration | `subprocess.Popen` + `threading.Lock` + `os.kill` | Start/stop/inspect WeCom/QQBot host subprocesses; PID registry guarded by lock; no `psutil` |
| Log viewing | `pathlib` + `io` + `os` (byte-offset tail) + `logging.handlers.RotatingFileHandler` | Tail-style seek+readline reader with level/search filter; rotating files cap disk; byte-offset polling every 2–3s |
| Report aggregation | `ContractLogReadModel` (existing) + `collections.Counter` + `datetime` | Pure-Python counts over in-memory read model; no pandas/numpy; SSR tables + inline SVG |
| Session auth | `http.cookies.SimpleCookie` + `secrets.token_urlsafe` + `hmac`/`hashlib`/`base64` (reuse `rbac.token` pattern) | HMAC-signed stateless session cookies; `RBAC_TOKEN_SECRET` reused; `SessionStore` protocol reserved for later `sqlite3` swap |
| Token management | `rbac.token.issue_token`/`verify_token` (existing) + atomic JSON revocation list | Issue/list/revoke RBAC tokens; revocation denylist in `revoked_tokens.json` |
| Product polish | `html` / `string.Template` / f-string SSR (existing) + `subprocess`/bash startup script | Error pages, nav, responsive CSS, one-click startup, `.env.example` completion |

### What NOT to add

| Avoid | Use instead |
|-------|-------------|
| Flask / FastAPI / Starlette / Django / uvicorn / gunicorn | `ThreadingHTTPServer` + existing `BaseHTTPRequestHandler` subclasses |
| React / Next / Vite / any JS SPA | SSR templates + `html.escape` + inline SVG |
| WebSocket / SSE libraries (`websockets`, `sse-starlette`) | Byte-offset HTTP polling for log viewing (SSE explicitly deferred) |
| `psutil` | `subprocess.Popen` API (`poll()`, `pid`, `terminate()`) |
| `celery` / `dramatiq` / `rq` / any task queue | `subprocess.Popen` + `threading.Lock` |
| PostgreSQL / Redis / MongoDB | `ContractLogReadModel` + signed cookies + atomic JSON |
| `sqlite3` as a hard dep this milestone | `rbac.token`-pattern signed cookies; reserve `SessionStore` protocol for later |
| `pandas` / `numpy` | `collections.Counter` + pure-Python loops |
| Pydantic / jsonschema as hard deps | Dataclasses + explicit validators |
| `httpx` / `aiohttp` | In-process callable proxy (`AdminApiClient`) |
| JWT library (`pyjwt`) | Extend `rbac.token` / mirror pattern for sessions |
| `watchdog` / `inotify` file-watch libs | Byte-offset polling |
| Auto-killing unknown PIDs on console startup | Warn operator about orphaned entries; require explicit re-adopt |

---

## Feature Table Stakes

Must-have features for v1.11. Full detail: [FEATURES.md](FEATURES.md).

### Process Orchestration
- **Process status panel** — per-host card: running/stopped/unknown state, PID, uptime, last exit code, started-at. LOW–MEDIUM.
- **Start / stop / restart actions** — `subprocess.Popen` spawn, SIGTERM graceful + SIGKILL fallback after timeout. CSRF on every mutating action. MEDIUM.
- **Config-save → restart-to-apply wiring** — one-click "Save & Restart" persists config then restarts affected host. MEDIUM.
- **Honest state, not fake health** — actual OS process state, not guessed "enabled" boolean; "unknown / not managed" when PID invisible. LOW.
- **Graceful shutdown ordering** — stop waits for in-flight turns (bounded timeout) before killing; restart = stop-then-start. MEDIUM.
- **Failure visibility** — start failure (port in use, missing env ref, import error) surfaces stderr tail in status card, not silent 500. LOW–MEDIUM.

### Log Viewing
- **Log file discovery + tail view** — last N lines (e.g. 200) on `/logs` page. LOW–MEDIUM.
- **Level filter (DEBUG/INFO/WARN/ERROR)** — dropdown filters displayed lines. LOW.
- **Text search / grep** — substring filter over visible window. LOW.
- **Per-host log source selector** — WeCom / QQBot / adapter / admin-console. LOW.
- **Refresh / manual reload** — re-reads the tail. TRIVIAL.
- **No raw secrets in log display** — display-time scrubbing or fail-closed logging policy. LOW.

### Reports & Dashboards
- **Volume counts** — sessions, tasks, turns, feedback events over selectable time window (today/7d/30d). LOW–MEDIUM.
- **Completion / success rate** — % tasks in terminal success vs failed/cancelled; long-task success rate separately. MEDIUM.
- **Feedback distribution** — counts by classification + dedup-aware unique counts. LOW–MEDIUM.
- **Time-window selector** — today / 7d / 30d / custom range. LOW.
- **Static snapshot, not live-updating** — point-in-time aggregation; Refresh button re-runs query. LOW.
- **CSV/JSON export of report tables** — reuse existing export patterns. LOW.
- **Empty-state honesty** — "No sessions in this window" not blank chart. TRIVIAL.

### Contract Event Audit
- **Event stream view** — `/audit` page listing AgentTurn + FeedbackEvent reverse-chronological with cursor pagination. LOW–MEDIUM.
- **trace_id filter + reconstruction** — full ordered event chain for a trace. MEDIUM.
- **Event type filter** — AgentTurn only / FeedbackEvent only / all. LOW.
- **Field allowlist (no secrets, no raw payloads)** — display refs not resolved values. LOW.
- **Timestamp + actor + role per event**. LOW.
- **CSV/JSON export** — audit slice for compliance review. LOW.

### Auth (Token + Session)
- **Token management page** — `/auth/tokens` listing issued tokens with issue + revoke actions. MEDIUM.
- **Issue token with role + tenant + TTL** — reuse `rbac.token.issue_token`. LOW–MEDIUM.
- **Revoke token** — revocation denylist checked at verify time (main new logic). MEDIUM.
- **Expiry visibility** — show exp; expired tokens auto-fail. LOW.
- **CSRF on all token mutate actions**. TRIVIAL (existing).
- **Never display token secret after first issuance** — show once, then fingerprint/hash only. LOW.
- **Login session interface (reserved, MVP token-only)** — `/login` page validates against env operator credential, issues RBAC token in session cookie. MEDIUM.
- **Session cookie + token coexistence** — auth resolver checks cookie first, then bearer header. MEDIUM.

### Product Polish
- **404 / 500 error pages** — server-rendered, CSP-compliant, no stack trace leakage. LOW.
- **Consistent navigation** — sidebar/top nav on every page with active-state highlighting. LOW.
- **Responsive layout** — usable on laptop (mobile bonus, not required). LOW.
- **`.env.example` completion** — every env var documented with safe placeholders. LOW.
- **One-click startup script** — `scripts/start_inkstatute.sh` sources `.env`, starts all services. LOW.
- **Loading / empty / error states on every data view**. LOW.
- **Gate-honesty notices on new pages**. TRIVIAL.
- **README + runbook updates**. LOW.

---

## Feature Differentiators

High-value optional features. Full detail: [FEATURES.md](FEATURES.md).

### Process Orchestration
- **Effective-config + process-state combined view** — dual-knob enable AND actual running state side by side ("enabled=true but process stopped"). MEDIUM.
- **Per-host independent control** — WeCom runs while QQBot stopped, independent of provider selection. LOW.
- **Restart-only-affected-host** — saving WeCom config restarts only WeCom. LOW–MEDIUM.
- **Startup script / one-click launch** — `scripts/start_inkstatute.sh` (+ `.ps1`). LOW.
- **Process ownership honesty** — "externally managed — restart not available" for non-console-spawned processes. LOW.

### Log Viewing
- **Server-Sent Events (SSE) live tail** — `text/event-stream` push; recommended real-time mechanism for stdlib `http.server` if threading cost acceptable. MEDIUM. *(Deferred from v1.11 per STACK.md — byte-offset polling is MVP.)*
- **Follow / pause / clear-view controls** — `tail -f` pause. LOW–MEDIUM.
- **trace_id correlation jump** — click trace_id in log line → audit view filtered to that trace. LOW–MEDIUM.
- **Level color coding via CSS only** — `<span class="log-warn">`. TRIVIAL.
- **Bounded buffer + backpressure** — SSE stream holds at most N lines; drop oldest if browser slow. LOW–MEDIUM.

### Reports & Dashboards
- **Gate pass-rate dashboard** — extend `/gates` with pass-rate-over-time + feature-flag status visualization. MEDIUM.
- **Human-gate status visualization** — Phase 5/8/QQ-live as explicit "not yet accepted" cards with evidence links. LOW.
- **trace_id-linked drill-down** — click a metric → filtered audit view for those traces. MEDIUM.
- **Feedback → turn linkage** — show which AgentTurns received negative feedback, jump to audit. MEDIUM.
- **Cost/latency hints from model-gateway** — per-provider token spend + p50/p95 latency. MEDIUM–HIGH. Optional; defer if gateway not deployed.

### Contract Event Audit
- **Turn ↔ feedback linkage view** — for a given AgentTurn, show attached FeedbackEvent(s) with classification + dedup state. MEDIUM.
- **trace_id jump from logs and reports** — bidirectional cross-link tying the three observability surfaces together. LOW–MEDIUM.
- **Event ordering guarantee visualization** — sequence numbers / occurred_at for causal order verification. LOW.
- **Privacy-scrubbed preview** — admin-gated `raw_payload_ref` preview, fail-closed otherwise. MEDIUM.
- **Audit of config changes** — who changed which config field when (field-level diff, refs redacted). MEDIUM.

### Auth (Token + Session)
- **Role-aware token issuance guardrails** — admin can issue operator/lawyer/viewer tokens but not escalate beyond own role. LOW–MEDIUM.
- **Token last-used-at tracking** — timestamp on each successful verify. MEDIUM.
- **Session timeout + re-login** — cookie expires; UI redirects to `/login`. LOW.
- **Audit log of token issue/revoke** — feeds contract event audit surface. LOW–MEDIUM.
- **Reserved username/password from `.env`** — `INKSTATUTE_OPERATOR_USER` / `INKSTATUTE_OPERATOR_PASSWORD_HASH`. LOW.
- **Logout (revoke session)** — clear cookie + mark session token revoked. LOW.

### Product Polish
- **Request-id correlation across pages** — error shows short request id mapping to log line. LOW–MEDIUM.
- **Keyboard-accessible nav** — tabbable, focus-visible. LOW.
- **Dark mode via CSS `prefers-color-scheme`**. LOW.
- **Per-page "Last refreshed" timestamp**. TRIVIAL.
- **Status badges consistent across pages** — shared badge component for running/stopped, enabled/disabled, pass/fail, accepted/not-accepted. LOW.

---

## Architecture Integration

Key integration points and build order. Full detail: [ARCHITECTURE.md](ARCHITECTURE.md).

### New Components

1. **Service Entry Points (`__main__.py`)** — `admin-web-ui`, `admin-console-api`, `qqbot-service`, `wecom-service` become runnable as `python -m <pkg>`. Each is a thin adapter: resolve env → build deps → `ThreadingHTTPServer` bind → `serve_forever` → signal graceful shutdown. wecom-service also needs a new thin `http_server.py` (mirrors qqbot-service pattern: POST callback + GET `/health`).

2. **Process Orchestrator (`ProcessSupervisor`)** — `services/admin-console-api/src/admin_console_api/orchestrator.py` (NEW) + `services/admin-web-ui/src/admin_web_ui/processes.py` (NEW SSR page). Stdlib-only class holding `dict[channel, Popen]`. State persists to JSONL (`INKSTATUTE_PROCESS_STATE_PATH`) for console-restart re-adoption. Health checks reuse each child's `/health` endpoint. Config save → `restart(channel)` (stop then start).

3. **Log Viewer (`LogReader`)** — `services/admin-console-api/src/admin_console_api/logs.py` (NEW) + `services/admin-web-ui/src/admin_web_ui/logs.py` (NEW SSR page). Pure stdlib `open`/`seek`/`readline`. `LOG_SOURCES` registry maps names → file paths. Every line passes through `scrub_contract_payload` before rendering.

4. **Reports Aggregator (`ReportsAggregator`)** — `services/admin-console-api/src/admin_console_api/reports.py` (NEW) + `services/admin-web-ui/src/admin_web_ui/reports.py` (NEW SSR page). Pure function over existing `ContractLogReadModel` + `feedback_queue` + `run_gate_summary`. No new data source.

5. **Contract Event Audit View (`AuditView`)** — `services/admin-console-api/src/admin_console_api/audit.py` (NEW) + `services/admin-web-ui/src/admin_web_ui/audit.py` (NEW SSR page). Thin read-only view over existing `ContractLogReadModel._trace_events`. Reuses `scrub_contract_payload` per line.

6. **Session Auth (`SessionStore` + login route)** — `services/admin-web-ui/src/admin_web_ui/sessions.py` (NEW) + `packages/rbac/src/rbac/session.py` (NEW). HMAC-signed session cookie (same stdlib pattern as csrf.py and rbac/token.py). Ordered auth fallback: Bearer header first (existing API path), then session cookie (browser path). Both produce same `Identity` → same `RbacGuard`. MVP credential store is env vars (`ADMIN_LOGIN_USER`, `ADMIN_LOGIN_PASS_HASH` via `hashlib.pbkdf2_hmac`).

7. **Token Management UI** — `services/admin-console-api/src/admin_console_api/tokens.py` (NEW) + `services/admin-web-ui/src/admin_web_ui/tokens.py` (NEW SSR page). Issue is a pure call to existing `rbac.issue_token`. Lightweight token registry JSONL (`INKSTATUTE_TOKEN_REGISTRY_PATH`) records metadata (never the token itself). Revocation MVP = TTL + secret rotation + denylist.

### Modified Components

| Component | Change | Keep unchanged |
|-----------|--------|----------------|
| `admin-web-ui/server.py` | Extend `_SECTION_MAP` + `_POST_ROUTES` with new routes; add Cookie parsing (bearer-then-cookie); thread new deps through kwargs | `handle_admin_web_ui_request` pure core; CSP/CSRF |
| `admin-console-api/api.py` | Add route dispatch for `/processes`, `/logs`, `/reports`, `/audit`, `/tokens`; extend `_authenticate_admin` for optional cookie resolver | `handle_admin_get`/`handle_admin_put` pure callables; auth.py |
| `rbac/matrix.py` | Add `/processes` (ADMIN/OPERATOR), `/logs` (ADMIN/OPERATOR), `/reports` (all roles read), `/audit` (ADMIN/OPERATOR/LAWYER), `/tokens` (ADMIN) to `PERMISSIONS_MATRIX` | Existing matrix entries |
| `platform-runtime/feature_flags.py` | Add `process_orchestration_enabled`, `log_viewing_enabled`, `session_auth_enabled` (all default OFF) | Existing flags + `require_enabled` gate |
| `wecom-service/` | Add `http_server.py` (NEW) + `__main__.py` (NEW) | `wiring.build_wecom_wired_runtime`; adapter; crypto; send path |
| `qqbot-service/` | Add `__main__.py` (NEW) binding `QQBotWebhookServer` to `ThreadingHTTPServer` + signal + GET `/health` | `QQBotWebhookServer`; `wiring`; `default_post_ack_scheduler` |
| `.env.example` | Complete `ADMIN_WEB_UI_HOST/PORT`, `ADMIN_CONSOLE_API_HOST/PORT`, `INKSTATUTE_CONTRACT_LOG_PATH`, `INKSTATUTE_RUNTIME_DIR`, `INKSTATUTE_PROCESS_STATE_PATH`, `ADMIN_LOGIN_USER`, `ADMIN_LOGIN_PASS_HASH`, orchestration/session flags | Existing refs-only secret pattern |
| `scripts/` | Add `start-console.sh` (one-click startup) | Existing scripts |

### Suggested Build Order

1. **Service entry points** (`__main__.py` + wecom `http_server.py`) — no orchestration yet. Lowest-risk thin wrappers over existing pure cores. Every later feature depends on runnable services with `/health` endpoints.
2. **Feature flags + RBAC matrix + `.env.example` completion** — new routes need default-OFF gates and matrix entries before handlers dispatch; CI scan enforces matrix coverage.
3. **Health/gate dashboard enhancement + Reports aggregator** — pure read-only over existing `ContractLogReadModel` + `feedback_queue` + `run_gate_summary`; proves the observability data path with no subprocess risk.
4. **Contract event audit view (trace_id stream)** — thin read-only over existing `_trace_events`; complements reports; no new infra.
5. **Log viewer (`LogReader` + `/logs` routes + SSR page)** — introduces file-read + scrub pattern; needed before orchestration (operators watch logs of processes they start). Privacy scrub is the main risk.
6. **Process orchestrator (`ProcessSupervisor` + `/processes` routes + SSR page)** — highest-complexity new component (subprocess lifecycle, health probes, restart-on-config-save). Needs runnable services (#1) + log viewing (#5) to be useful and debuggable.
7. **Token management UI (`/tokens` issue/verify)** — wraps existing `rbac.issue_token`; lower risk; admin-only.
8. **Session auth (`SessionStore` + `/login` + cookie coexistence)** — interface-reserving layer; MVP is token-only so session login is polish, not a blocker. Putting it last avoids destabilizing the auth pipeline early.
9. **Product polish** — error pages, navigation, responsive layout, one-click script finalization. Depends on all pages existing.

**Parallelism:** After #2, items #3, #4, #5, #7 can proceed in parallel waves (all read-only, independent routes). #6 waits for #1 + #5. #8 waits for #7.

---

## Watch Out For

Top pitfalls that must be addressed early. Full detail: [PITFALLS.md](PITFALLS.md) (30 pitfalls total).

### Must-address in Phase 79 (ENTRY-RUN) — before any feature work

1. **Threading decision is the first artifact (Pitfalls 1, 7, 20)** — `BaseHTTPRequestHandler` is single-threaded by default; blocking subprocess waits or log reads freeze the entire UI. If adopting `ThreadingHTTPServer`, **audit every `server.*` attribute for thread safety** (`OperatorConfigStore`, `feedback_queue`, process table, `ContractLogReadModel` are all shared mutable state with no locks). Either stay single-threaded with bounded non-blocking handlers, or go threaded with per-store `threading.Lock` + copy-on-rebuild read model. Do not mix. This decision gates Phases 80–82.

2. **Entry points have zero test coverage today (Pitfall 19)** — every existing test dispatches directly to `handle_*` cores, bypassing the socket. Add a socket-level integration test per service: boot `HTTPServer(("127.0.0.1", 0), Handler)` on ephemeral port, send real HTTP request via `urllib.request`, assert 200. Test signal handling by sending SIGINT.

3. **Per-route POST body cap (Pitfall 22)** — current `MAX_CHANNELS_POST_BYTES = 64KB` is global. New endpoints (log search, report config) may need different limits. Make the cap per-route with a `{route: max_bytes}` map before new POST routes ship.

4. **No new DB/queue, flags default OFF (Pitfall 23)** — enforce at Phase 79 via checklist: no `sqlite3`, no `redis`, no `multiprocessing.Manager`, no `queue.Queue`-as-broker. Every new feature flag defaults to `False`. Run existing `test_read_only.py` + flag-default-OFF gate test in every phase.

### Must-address in Phase 80 (ORCHESTRATION)

5. **Zombie processes + leaked handles (Pitfall 2)** — write PID file per managed process; on console startup reconcile PID file against live PIDs (`os.kill(pid, 0)`); after `terminate()` always `wait()` with `SIGKILL` escalation to reap. Persist process metadata in atomic JSON for re-adoption. Regression test: start→crash→restart→verify adoption.

6. **Signal handling orphans channel hosts (Pitfall 3)** — shutdown sequence: (1) `httpd.shutdown()`, (2) SIGTERM each child, (3) wait N seconds, (4) SIGKILL survivors, (5) reap all. Use `start_new_session=True` at `Popen` for process-group signaling. Test: SIGINT console → no managed PID survives.

7. **Port conflicts + rapid start/stop races (Pitfall 4)** — status from liveness (`os.kill(pid, 0)`) + readiness (port check), not from Popen return. Per-process lock + idempotency guard (reuse CSRF token binding). `SO_REUSEADDR` on channel host sockets. Test: double-submit start → one process; stop→immediate-start → waits for port release.

8. **Config-save → restart race applies half-written config (Pitfall 5)** — strict ordering: `store.save()` returns success (atomic write committed) **then** enqueue restart. Never read `.tmp` sibling. Child calls `store.load()` at startup. Test: save+restart under concurrency → child always sees post-save document.

9. **Secrets passed via argv visible in `ps` (Pitfall 25)** — pass all secrets to children via **environment variables**, never argv. Children resolve `*_REF` at their own edge. Test: inspect spawned child's cmdline (or mock Popen, assert env not argv).

10. **Over-engineering orchestration (Pitfall 24)** — scope to: start one named process, stop one named process, show status (alive + port), apply config → restart. No retries, no rolling, no clustering. Process table is a flat dict. If a feature needs >1 screen of design, it's over-engineered for this milestone.

### Must-address in Phase 82 (LOG-VIEW)

11. **Loading entire log files into memory (Pitfall 6)** — do **not** reuse `load_event_stream`/`load_records_from_jsonl` for runtime log viewing (those read the whole file). Use tail-style `seek` + buffered readline, cap returned lines (500–2000). Test with synthetic 100MB log asserting bounded memory + sub-second response.

12. **Log rotation breaks offset cursor (Pitfall 8)** — detect rotation by comparing file size + mtime (or inode) against last-seen; when file shrinks or inode changes, reset cursor to 0 and signal "log rotated." Test viewer against actively-rotating log.

13. **Secrets + raw legal payloads leak into log viewer (Pitfall 9)** — redaction filter **before** `html.escape`: mask `Bearer ...`, `sk-...`, `BotSecret`, AES keys, `secret://...` refs, `*_REF` resolutions. Test: inject synthetic secret → viewer shows `[REDACTED]`.

14. **Path traversal in log/report file selection (Pitfall 26)** — validate service/file name against fixed allowlist (`{"wecom", "qqbot", "adapter", "admin"}`). Resolve full path + assert starts with canonical base dir. Reject `..`, absolute paths, symlinks. Test: `/logs/../../etc/passwd` → 404/400.

### Must-address in Phase 81 (REPORTS)

15. **Rebuilding full read model per request (Pitfall 10)** — build read model once at startup (or refresh cadence) and reuse. For large logs, single streaming pass with counters. Cache aggregate with mtime-based invalidation. Perf test: 50k-event fixture → <1s response + bounded memory.

16. **Stale report data after restarts (Pitfall 11)** — "last built at" timestamp on reports page. Explicit refresh action (POST with CSRF) and/or mtime auto-invalidation. Never auto-close human gate based on stale aggregate. Document staleness in UI.

17. **Timezone inconsistency (Pitfall 12)** — normalize all `occurred_at` to aware UTC at parse time; convert to display tz only at render. Bucket by display tz. Test: crosses midnight in non-UTC tz → correct day buckets.

18. **Unbounded JSONL scan (Pitfall 13)** — default reports to bounded window (last 7 days); wider ranges opt-in. Reverse-iterate from EOF for recent windows + early-exit. Document "all time" as intentionally slow.

### Must-address in auth phases (85–86)

19. **Token leakage in new logs (Pitfall 14)** — extend "no tokens logged" invariant to all new code. Never log `Authorization`, `ADMIN_API_TOKEN`, RBAC secrets, issued token values. Error responses return generic "invalid token." Grep-based gate test: no token/secret/bearer literals in log files under tests.

20. **Session fixation + weak session IDs (Pitfall 15)** — `secrets.token_urlsafe(32)` for session IDs. Rotate session ID on successful login. `HttpOnly; SameSite=Strict; Path=/` cookie attributes. Sweep expired sessions on each load. Fixation test: pre-login cookie invalid after login.

21. **CSRF gap on new endpoints (Pitfall 16)** — add every new state-changing route to `_POST_ROUTES` with CSRF validation. For login: issue CSRF token on GET `/login` (anonymous role), validate on POST, rotate both session cookie + CSRF token after login. Test: POST without/wrong CSRF → 403.

22. **Privilege escalation via dual auth paths (Pitfall 17)** — unify auth resolution into single function returning `Identity` from either Bearer or cookie, then run **every** route through `RbacGuard.check`. No route bypasses the guard. Guard test per role per new route.

23. **Session/token store race under ThreadingHTTPServer (Pitfall 18)** — wrap all read-modify-write cycles on shared JSON stores in `threading.Lock` (one per store). Concurrency test: N threads revoke/issue tokens → no lost updates.

24. **Self-revocation / last-admin lockout (Pitfall 30)** — prevent revoking own active token. Always honor `ADMIN_API_TOKEN` env var as bootstrap override (cannot be revoked via UI). Require CSRF'd confirmation for revoke. Test: revoke-own → 400; env token works after all UI tokens revoked.

### Must-address across all rendering phases

25. **XSS via unescaped content (Pitfall 29)** — every value interpolated into HTML passes through `html.escape` or `AdminUiBoundary.escape_value` — no exceptions. Grep/AST gate test: no f-string or `.format` producing HTML with unescaped variable. Reflected-XSS test per new route: inject `<script>` into every user-controlled field → escaped.

26. **CSP / no-JS constraint (Pitfall 21)** — stay SSR: bounded snapshot + manual Refresh button (POST with CSRF) or long-ish `meta refresh` (≥5s) only if threaded. No inline JS, no `EventSource`, no WebSocket. CSP stays exactly as-is.

27. **Human gates auto-closed by "green" display (Pitfall 28)** — render human gates with distinct visual state ("HUMAN GATE — carried, not auto-closed") that cannot turn green from fixture evidence. Preserve Phase 78 `not_live_acceptance` label. Test: human-gate rows never render as "passed." Never add "mark human gate passed" button.

---

## Suggested Phase Themes

Suggested phase grouping based on all 4 research docs. Phases continue from **79**. Roadmap may renumber.

| Phase | Theme | Key deliverables | Depends on |
|-------|-------|------------------|------------|
| **79 ENTRY-RUN** | Runnable entry points + threading decision | `__main__.py` for admin-web-ui, admin-console-api, qqbot-service, wecom-service (+ wecom `http_server.py`); `ThreadingHTTPServer` bind + `argparse` + `signal` graceful shutdown; `start-console.sh`; threading model decision artifact + thread-safety audit; per-route POST body cap framework; socket-level integration tests | Nothing new (existing pure handlers + env) |
| **80 ORCHESTRATION** | Process control plane | `ProcessSupervisor` + `/processes` routes + SSR page; start/stop/restart/inspect; PID file + re-adoption; config-save → restart wiring; non-blocking handlers; env-injected secrets (never argv); graceful child drain on console shutdown | 79 |
| **81 REPORTS** | Report dashboards | `ReportsAggregator` + `/reports` route + SSR page; volume counts, completion/success rate, feedback distribution; time-window selector; CSV/JSON export; cached read model with mtime invalidation; tz-normalized bucketing; bounded scan windows; empty-state honesty | 79 (flags/matrix) |
| **82 LOG-VIEW** | Real-time log viewing | `LogReader` + `/logs` routes + SSR page; byte-offset tail + level filter + search; per-host source selector; `RotatingFileHandler` on channel hosts; rotation-aware cursor; secret/payload redaction filter; path traversal guard; bounded memory (no full-file reads) | 79, 80 (host logging config) |
| **83 AUDIT-EVENTS** | Contract event audit | `AuditView` + `/audit` route + SSR page; AgentTurn/FeedbackEvent stream; trace_id filter + reconstruction; event type filter; field allowlist; CSV/JSON export; trace_id cross-link from logs + reports | 79 (flags/matrix), 81/82 (cross-link) |
| **84 HEALTH-GATE-DASH** | Health + gate dashboard | Enhanced `/gates` with pass-rate-over-time; feature-flag status visualization; human-gate status cards (distinct non-green visual); service health from child `/health` endpoints; carried-gate honesty preserved | 79, 80 (health probes) |
| **85 AUTH-TOKEN** | RBAC token management | `/tokens` issue/list/revoke; revocation denylist (`revoked_tokens.json`); token registry JSONL (metadata only); admin-only; role-aware issuance guardrails; self-revocation prevention; env bootstrap override; audit log of issue/revoke | 79 (flags/matrix) |
| **86 AUTH-SESSION** | Login session interface | `SessionStore` + `/login` + `/logout`; HMAC-signed session cookie (reuse `RBAC_TOKEN_SECRET`); env operator credential (`ADMIN_LOGIN_USER`/`ADMIN_LOGIN_PASS_HASH`); cookie-then-bearer auth fallback; session fixation prevention (rotate ID); login CSRF token; `session_auth_enabled` flag default OFF | 79, 85 (token issue reused for session inner token) |
| **87 POLISH** | Product polish | 404/500 error pages; consistent navigation; responsive CSS; one-click startup script finalization; `.env.example` completion; loading/empty/error states; gate-honesty notices on new pages; request-id correlation; dark mode; status badge component; README + runbook updates | 79–86 |

**Parallelism:** After Phase 79, Phases 81, 82, 83, 85 can proceed in parallel waves (all read-only or admin-only, independent routes). Phase 80 waits for 79. Phase 84 waits for 79 + 80. Phase 86 waits for 85. Phase 87 waits for all.

**Explicit non-goals:** live WeCom UAT / lawyer trial / QQ `--live` acceptance (carried human gates); TLS/reverse-proxy; external DB/queue; React SPA; unfreezing ChannelAdapter/BackendAdapter Protocols; Hermes profile editing from console; hot-reload (restart-to-apply remains MVP); full process supervisor/systemd rebuild; auto-restart watchdog; distributed/remote orchestration; WebSocket log streaming; time-series DB; OAuth/OIDC/SAML SSO; MFA/TOTP; full user management database.

---

*Research summary for: v1.11 Product Console*
*Synthesized from: STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md*
*Researched: 2026-07-13*
