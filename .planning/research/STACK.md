# Stack Research: v1.11 Product Console

**Domain:** Runnable service entry points, process orchestration, observability (reports / logs / audit / health), auth (token management + login session interface), product polish.
**Researched:** 2026-07-13
**Confidence:** HIGH
**Runtime:** Python 3.14.6 (CI floor `requires-python = ">=3.11"`)

## Scope Boundary

This research covers **only** stack additions/changes for the v1.11 Product Console milestone. The following are **already validated** and must not be re-researched:

| Already shipped (reuse) | Do not re-research |
|-------------------------|--------------------|
| `admin-web-ui` SSR (`BaseHTTPRequestHandler` + `html.escape` + CSP + CSRF) | New SPA / new frontend toolchain |
| `admin-console-api` read views + `/config/*` mutate (`handle_admin_get` / `handle_admin_put`) | New mega-API service |
| `rbac` HMAC-SHA256 token auth + `RbacGuard` matrix (admin/operator/lawyer/viewer) | New auth framework / JWT library |
| `qqbot-service` `QQBotWebhookServer` (`BaseHTTPRequestHandler`) + `wiring` | QQ OpenAPI client / channel crypto |
| `wecom-service` `wiring` + adapter (library, no HTTP host yet) | WeCom crypto / send path |
| `conversation-read-view` `ContractLogReadModel.from_records` over JSONL | New read-store / new DB |
| `feedback-service` feedback queue + normalization | Feedback classification ML |
| `platform-runtime` `RuntimeFeatureFlags` (default OFF) | Flag framework redesign |
| `operator-config` refs-only JSON store + validators | Config schema redesign |

**Milestone goal:** Make the admin console a runnable, product-grade operations control plane — start/stop channel host subprocesses, view real-time logs, aggregate report stats, audit contract events, manage RBAC tokens, and provide an extensible login-session interface. Local/single-machine ops; no TLS/reverse-proxy/production-stack requirement.

---

## Existing Stack (validated, do not change)

- **Python stdlib `http.server`** — `BaseHTTPRequestHandler` subclasses (`AdminWebUiServer`, `QQBotWebhookServer`) are library handlers; **no port binding / `__main__` exists yet**. Entry points must bind these via `ThreadingHTTPServer`, not replace them.
- **`rbac` package** — `issue_token` / `verify_token` (HMAC-SHA256, `base64url(payload).base64url(sig)`, TTL 900s), `RbacGuard.check(role, endpoint)`, `resolve_identity`. Token carried via `Authorization: Bearer <token>`.
- **`admin-console-api`** — `handle_admin_get` / `handle_admin_put` pure callables (testable without port bind); `auth.py` resolves `RBAC_TOKEN_SECRET` from env.
- **`admin-web-ui`** — `handle_admin_web_ui_request` pure core + `AdminWebUiServer(BaseHTTPRequestHandler)` thin wrapper; config via `self.server.*` attributes; CSP + CSRF (`csrf.py` HMAC-SHA256, route-bound).
- **`qqbot-service`** — `http_server.py` has `QQBotWebhookServer(BaseHTTPRequestHandler)` + `default_post_ack_scheduler` (daemon thread); `wiring.build_qqbot_wired_runtime` composes runtime. **No `__main__` / port bind.**
- **`wecom-service`** — `wiring.build_wecom_wired_runtime` + adapter; **no HTTP host wrapper exists** (library only).
- **`conversation-read-view`** — `ContractLogReadModel.from_records` + `load_records_from_jsonl`; cursor pagination, trace reconstruction, CSV/JSON export, privacy scrubbing.
- **`feedback-service`** — feedback queue (`list[dict]`) + normalization.
- **`operator-config`** — atomic JSON store (`OperatorConfigStore`), refs-only, validators.
- **All packages/services:** `dependencies = []`, `requires-python = ">=3.11"`, stdlib-only, `unittest` test patterns, pure-handler testability.

---

## New Stack Additions

### 1. Runnable HTTP Server Entry Points

- **`http.server.ThreadingHTTPServer` + `socketserver`**: Bind existing `BaseHTTPRequestHandler` subclasses to a host/port with threaded request handling. **Why:** Current handlers are library-only; entry points need a real listening socket. `ThreadingHTTPServer` (stdlib, Python 3.7+) handles concurrent browser requests without blocking the single-threaded `HTTPServer`. **Version:** stdlib (ships with Python ≥3.11). **Integration:** New `__main__.py` modules in `admin-web-ui` and `admin-console-api` construct `ThreadingHTTPServer((host, port), AdminWebUiServer)`, set `server.feature_flags` / `server.handle_admin_get` / `server.read_model` / `server.rbac_secret` etc. (the existing `self.server.*` attribute contract), then `serve_forever()`. No change to handler classes.
- **`argparse`**: CLI for `--host`, `--port`, `--config-path`, `--log-dir`, `--log-level`. **Why:** Entry points need operator-tunable bind/config paths without editing code. **Version:** stdlib. **Integration:** Each `__main__.py` parses args → builds `RuntimeFeatureFlags` from env → builds read model / config store / feedback queue → starts server.
- **`signal`**: `signal.signal(signal.SIGINT, ...)` + `signal.signal(signal.SIGTERM, ...)` → `server.shutdown()` graceful stop. **Why:** Ctrl-C / `kill` must close the listening socket cleanly, not leave subprocesses orphaned. **Version:** stdlib. **Integration:** Register handlers before `serve_forever()`; handler calls `httpd.shutdown()` from a separate thread (stdlib requirement — `shutdown()` must be called from another thread to avoid deadlock).
- **`os` / `pathlib` / `json`**: Load config paths, resolve env, build feature flags. **Why:** Already the monorepo pattern for config resolution. **Version:** stdlib. **Integration:** Reuse existing `_resolve_rbac_secret` / `OperatorConfigStore` / `RuntimeFeatureFlags` factories.

### 2. Process Orchestration (start/stop WeCom/QQBot host subprocesses)

- **`subprocess.Popen`**: Launch channel host processes (`python -m qqbot_service` / `python -m wecom_service`) as managed subprocesses with captured stdout/stderr → log files. **Why:** Console is the control plane; channel hosts run as separate OS processes so a channel crash never takes down the console. `Popen` gives PID, exit code, signal control. **Version:** stdlib. **Integration:** New `packages/process-orchestration` (or `services/admin-console-api` orchestration module) keeps a `dict[channel_name, Popen]` registry; `start` spawns with `stdout=open(log_path, "ab")`; `stop` sends `SIGTERM` then `Popen.wait(timeout=...)` with `SIGKILL` escalation; `inspect` returns `poll()` status + PID. Config save → `stop` + `start` to apply (matches existing "restart runtime to apply" semantics).
- **`subprocess.Popen` env injection**: Pass `env=os.environ | {channel-specific refs/values}` to each child. **Why:** Channel hosts resolve `*_REF` / values at process edge (`qqbot_service.secrets.resolve_secret_ref`); the orchestrator constructs the child env from operator config + secret values without writing them to disk. **Version:** stdlib. **Integration:** Reuse `OperatorConfigStore` config + `resolve_secret_ref` to build child env; never log child env.
- **`signal` / `psutil`-free PID management**: Use `Popen.pid` + `Popen.poll()` for liveness; `os.kill(pid, signal.SIGTERM)` only as fallback. **Why:** Avoids a `psutil` hard dependency; `Popen` API is sufficient for single-machine start/stop/inspect. **Version:** stdlib. **Integration:** Registry persists PIDs to a small JSON state file (`runbook`-style) so a console restart can re-adopt or warn about orphaned hosts; do not auto-kill unknown PIDs on startup (safety).
- **`threading.Lock`**: Guard the process registry against concurrent start/stop calls. **Why:** `ThreadingHTTPServer` dispatches requests on threads; orchestration mutations must be atomic. **Version:** stdlib. **Integration:** `Lock` around registry `dict` mutations in the orchestration module.

### 3. Real-Time Log File Viewing via HTTP

- **`pathlib` + `io` + `os` (byte-offset tail)**: Read log files from a configurable `--log-dir` using a `since` byte offset cursor; return new bytes since last cursor. **Why:** Channel hosts write stdout/stderr to log files (set by orchestrator's `Popen` redirection); the console reads the same files. Byte-offset polling is the simplest stdlib approach — no WebSocket/SSE framing, no extra thread, no file-watch dependency. **Version:** stdlib. **Integration:** New `admin-web-ui` route `/logs/<channel>` + `admin-console-api` view: open file, `seek(offset)`, read to end, return `{"lines": [...], "next_offset": N}`. Client polls with `?offset=N&level=...`. Level filter via `line.startswith("LEVEL")` parse on stdlib `logging` format.
- **`logging` + `logging.handlers.RotatingFileHandler` / `TimedRotatingFileHandler`**: Channel hosts and the console itself write structured logs to rotating files under `--log-dir`. **Why:** Rotating files cap disk usage on a long-running single-machine deploy; the log-viewer reads the current active file. **Version:** stdlib. **Integration:** Each host `__main__.py` configures `RotatingFileHandler(log_dir / f"{service}.log", maxBytes=5MB, backupCount=5)` + `StreamHandler` for console. Use a consistent `%asctime\t%(levelname)s\t%(name)s\t%(message)s` format so the viewer's level filter works across all hosts.
- **`re` (optional)**: Light search filter on log lines. **Why:** Operator search box over a tail window. **Version:** stdlib. **Integration:** `re.search(pattern, line)` over the returned window only (not full file scan — cap to last N MB to avoid OOM on large logs).

> **Note on SSE/WebSocket:** Full streaming (Server-Sent Events / WebSocket) is *possible* with stdlib `http.server` (chunked response + `wfile.flush()` loop on a dedicated thread), but it adds threading/lifetime complexity and risks blocking a `ThreadingHTTPServer` worker indefinitely. For v1.11 local ops, **byte-offset polling every 2–3s is sufficient and far simpler**. SSE is explicitly deferred (see What NOT to Add).

### 4. Report / Statistics Aggregation

- **`conversation-read-view.ContractLogReadModel` (existing) + pure-Python aggregation**: Compute session/task volume, completion rate, long-task success rate, feedback distribution by iterating already-loaded records. **Why:** The read model already loads + scrubs + indexes JSONL contract events; reports are derived counts over the same in-memory records. No new store. **Version:** in-repo 0.1.0. **Integration:** New `admin-console-api` view `/reports` (or extend `views.py`) calls `read_model._tasks` / `_conversations` / `feedback_queue` and returns aggregate dicts: `{"session_count", "task_count", "completion_rate", "long_task_success_rate", "feedback_distribution"}`. Render via `admin-web-ui` SSR table/cards with `html.escape`.
- **`collections.Counter` / `collections.defaultdict`**: Tally feedback classes, status distributions. **Why:** stdlib histogram primitive; avoids pandas/numpy. **Version:** stdlib. **Integration:** Inside the report handler.
- **`datetime` / `time`**: Time-window bucketing (e.g. per-day counts) for trend charts. **Why:** stdlib date math. **Version:** stdlib. **Integration:** Bucket records by `iat` / `event_time` into day keys; render as SSR `<table>` or inline SVG (no JS chart library — keep CSP `script-src 'self'`).

> **No new DB / no pandas / no numpy.** Aggregation is over the in-memory read model rebuilt on each report request (acceptable for local single-machine volumes). If volumes grow, swap behind a `ReportSource` protocol later — do not pre-optimize.

### 5. Session-Based Auth (alongside existing token auth)

- **`http.cookies.SimpleCookie`**: Parse `Cookie` request header and emit `Set-Cookie` response header for a session cookie. **Why:** stdlib cookie parsing/serialization; no third-party session lib. **Version:** stdlib. **Integration:** New `admin-web-ui` `/login` GET (form) + POST (username/password → issue session). On success, set `Set-Cookie: inkstatute_session=<signed-session>; HttpOnly; SameSite=Strict; Path=/`. Existing `Authorization: Bearer` token path stays unchanged.
- **`secrets.token_urlsafe`**: Generate session IDs (32-byte entropy). **Why:** stdlib CSPRNG; matches `csrf.py` token pattern. **Version:** stdlib. **Integration:** Session ID → server-side store mapping `{sid: {role, tenant_id, exp}}`.
- **`hmac` + `hashlib` + `json` + `base64` (reuse `rbac.token` pattern)**: Sign session cookies with the same `RBAC_TOKEN_SECRET` so sessions are tamper-proof without a DB. **Why:** The `rbac` token is already `base64url(payload).base64url(hmac_sha256(secret, payload))`; a session cookie can be the same shape with a longer TTL and a `session: true` claim, OR a stateless signed cookie. **Version:** in-repo `rbac` 0.1.0 + stdlib. **Integration:** New `admin_web_ui/sessions.py` `issue_session` / `verify_session` mirroring `rbac.token.issue_token` / `verify_token` but with `session` claim + configurable TTL (e.g. 8h). `resolve_identity` extended to accept a session cookie as an alternative to the Bearer header (MVP: token-only, session path gated by a new `session_auth_enabled` flag default OFF).
- **`sqlite3` (optional, deferred)**: Server-side session store if stateful sessions become required (revocation lists, active session enumeration). **Why:** stdlib embedded DB; no external service. **Version:** stdlib. **Integration:** **MVP does NOT need this** — stateless signed cookies suffice for v1.11. Reserve as a protocol-swappable `SessionStore` behind `issue_session`/`verify_session` so a later phase can add `sqlite3` revocation without changing the auth surface. Do not introduce `sqlite3` as a hard dependency this milestone.

### 6. Token Management UI

- **`rbac.token.issue_token` / `verify_token` (existing) + new admin views**: List active tokens, issue new tokens (role + tenant + TTL), revoke (add to a revocation list). **Why:** Operators need a UI to mint/revoke tokens without hand-crafting HMAC. **Version:** in-repo `rbac` 0.1.0. **Integration:** New `admin-console-api` `/tokens` GET (list) / POST (issue) / DELETE (revoke by jti/id). Revocation requires a small store — use the same atomic JSON pattern as `operator-config` (a `revoked_tokens.json` of token IDs/expirations, checked in `verify_token` or a wrapper). Keep `dependencies = []`.

### 7. Product Polish

- **`html` / `string.Template` / f-string SSR (existing pattern)**: Error pages (404/403/500), responsive layout via CSS (stdlib-served static CSS under `default-src 'self'`), navigation. **Why:** Existing SSR approach; no JS framework. **Version:** stdlib. **Integration:** Extend `dashboard.py` render helpers; add a `/static/style.css` route served by `admin-web-ui` (read file, set `Content-Type: text/css`, respect CSP).
- **One-click startup script (`scripts/start_console.sh` or `python -m admin_web_ui`)**: Shell/Python wrapper that exports env from `.env`, starts admin-web-ui + admin-console-api (+ optionally channel hosts). **Why:** Operator usability milestone goal. **Version:** stdlib `subprocess` / bash. **Integration:** Reuse `start-hindsight.sh` pattern already in `scripts/`.

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Flask / FastAPI / Starlette / Django** | Introduces hard deps; breaks `dependencies = []` monorepo convention; diverges from existing stdlib `http.server` hosts | `ThreadingHTTPServer` + existing `BaseHTTPRequestHandler` subclasses |
| **React / Next / Vite / any JS SPA** | Overkill for operator console; CSP/`innerHTML` risk; new frontend toolchain; milestone is SSR | SSR templates + `html.escape` + inline SVG |
| **uvicorn / gunicorn / waitress** | ASGI/WSGI servers incompatible with existing sync `BaseHTTPRequestHandler` design; unneeded for local single-machine | `ThreadingHTTPServer.serve_forever()` |
| **WebSocket / Server-Sent Events libraries (`websockets`, `sse-starlette`)** | Adds hard deps + threading complexity; `ThreadingHTTPServer` worker would block on long stream | Byte-offset HTTP polling for log viewing |
| **`psutil`** | Hard dep for process inspection when `Popen.poll()` + `Popen.pid` suffice for single-machine start/stop/inspect | `subprocess.Popen` API |
| **`celery` / `dramatiq` / `rq` / any task queue** | AGENTS.md forbids new queue unless plan requires; orchestration is synchronous start/stop | `subprocess.Popen` + `threading.Lock` |
| **PostgreSQL / Redis / MongoDB** | AGENTS.md forbids new DB unless justified; reports derive from in-memory read model; sessions are stateless signed cookies | `ContractLogReadModel` + signed cookies + atomic JSON |
| **`sqlite3` as a hard dep this milestone** | Stateless signed session cookies suffice for MVP; only justify if revocation/active-session enumeration becomes a hard requirement | `rbac.token`-pattern signed cookies; reserve `SessionStore` protocol for later |
| **`pandas` / `numpy`** | Report aggregation is simple counts over small local volumes; heavy deps break `dependencies = []` | `collections.Counter` + pure-Python loops |
| **Pydantic / jsonschema as hard deps** | Monorepo is `dependencies = []`; hand validators already proven | Dataclasses + explicit validators |
| **`httpx` / `aiohttp`** | Rejected repeatedly; console proxies via in-process callables (`handle_admin_get`), not HTTP client calls | In-process callable proxy (`AdminApiClient`) |
| **JWT library (`pyjwt`)** | `rbac` already implements HMAC-SHA256 signed tokens with stdlib | Extend `rbac.token` / mirror pattern for sessions |
| **`watchdog` / `inotify` file-watch libs** | Log viewer polling is simpler and dependency-free | Byte-offset polling |
| **Auto-killing unknown PIDs on console startup** | Safety: could kill unrelated processes matching a stale registry | Warn operator about orphaned registry entries; require explicit re-adopt |

---

## Integration Points

| Surface | Change | Keep unchanged |
|---------|--------|----------------|
| `admin-web-ui` `__main__.py` (new) | `ThreadingHTTPServer` bind + `argparse` + `signal` graceful shutdown; set `server.*` attributes | `AdminWebUiServer` handler class; `handle_admin_web_ui_request` pure core; CSP/CSRF |
| `admin-console-api` `__main__.py` (new) | `ThreadingHTTPServer` bind for the API port; same signal/argparse pattern | `handle_admin_get` / `handle_admin_put` pure callables; auth.py |
| `qqbot-service` `__main__.py` (new) | Bind `QQBotWebhookServer` to QQBot port; build wired runtime from env/config; redirect logs to `--log-dir` | `QQBotWebhookServer`; `wiring.build_qqbot_wired_runtime`; `default_post_ack_scheduler` |
| `wecom-service` `__main__.py` (new) | **Add a thin `http_server.py` mirroring `qqbot_service.http_server`** (WeCom has no HTTP host yet) + bind in `__main__` | `wiring.build_wecom_wired_runtime`; adapter; crypto; send path |
| `admin-console-api` orchestration module (new) | `subprocess.Popen` registry; `/orchestrate/<channel>` start/stop/inspect routes; `threading.Lock` guard | Existing read/config routes |
| `admin-console-api` `/logs` view (new) | Byte-offset tail read from `--log-dir`; level/search filter | Existing views pattern |
| `admin-console-api` `/reports` view (new) | Aggregate over `ContractLogReadModel` + `feedback_queue` | Read model loading; privacy scrubbing |
| `admin-console-api` `/tokens` views (new) | Issue/list/revoke via `rbac.token` + revoked-tokens JSON | `rbac` token shape; `RBAC_TOKEN_SECRET` |
| `admin-web-ui` `/login` + `sessions.py` (new) | `SimpleCookie` + signed session cookie (HMAC, reuse `RBAC_TOKEN_SECRET`); `session_auth_enabled` flag default OFF | `Authorization: Bearer` token path; `RbacGuard`; CSRF |
| `RuntimeFeatureFlags` | Add `session_auth_enabled: bool = False`, `process_orchestration_enabled: bool = False`, `log_viewing_enabled: bool = False`, `reports_enabled: bool = False`, `token_management_enabled: bool = False` (all default OFF) | Existing flags + `require_enabled` gate |
| `logging` config | Each host `__main__.py` configures `RotatingFileHandler` under `--log-dir` with shared format | No change to library-level log calls |
| `.env.example` | Add `ADMIN_WEB_UI_HOST/PORT`, `ADMIN_CONSOLE_API_HOST/PORT`, `INKSTATUTE_LOG_DIR`, `INKSTATUTE_LOG_LEVEL`, session TTL, orchestration flags | Existing refs-only secret pattern |

**Data flow (orchestration):**
```text
Operator browser
  → admin-web-ui /orchestrate/<channel> (SSR button, CSRF, RBAC admin/operator)
  → admin-console-api orchestration module
  → subprocess.Popen(python -m <channel>_service, env=resolved_refs, stdout=log_file)
  → channel host process (binds its own port, writes logs to --log-dir)
  → console /logs/<channel> reads the same log file via byte-offset polling
```

**Data flow (reports):**
```text
Operator browser
  → admin-web-ui /reports (SSR, RBAC admin/operator)
  → admin-console-api /reports
  → ContractLogReadModel.from_records(load_records_from_jsonl(contract_log.jsonl))
  → collections.Counter aggregation over tasks/conversations/feedback
  → SSR table/cards (html.escape, no JS)
```

**Data flow (session auth, MVP extensible):**
```text
Operator browser /login (POST username/password)
  → admin-web-ui sessions.issue_session (secrets.token_urlsafe + HMAC sign with RBAC_TOKEN_SECRET)
  → Set-Cookie: inkstatute_session=<signed>; HttpOnly; SameSite=Strict
  → subsequent requests: resolve_identity accepts Cookie OR Authorization: Bearer
  → RbacGuard.check (unchanged)
```

---

## Version Compatibility

| Component | Version | Notes |
|-----------|---------|-------|
| Python | ≥3.11 (CI floor), 3.14.6 runtime | `ThreadingHTTPServer`, `signal.SIGTERM`, `logging.handlers.RotatingFileHandler`, `http.cookies.SimpleCookie`, `secrets.token_urlsafe` all stable since 3.7–3.11 |
| `subprocess.Popen` | stdlib | `Popen.poll()`, `Popen.wait(timeout=)`, `Popen.send_signal()` stable across 3.11+ |
| `rbac` | 0.1.0 (in-repo) | Reuse `issue_token`/`verify_token` HMAC pattern for sessions; do not change token shape |
| `conversation-read-view` | 0.1.0 (in-repo) | `ContractLogReadModel.from_records` is the report data source |
| `operator-config` | 0.1.0 (in-repo) | Atomic JSON store pattern reused for revoked-tokens list |
| `openai` (optional) | `>=2.45.0,<3` | Unchanged from v1.10; only on hosts running live provider_model probe; not a console dep |

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `ThreadingHTTPServer` (stdlib) | `asyncio` + `aiohttp` / `uvicorn` | Only if async streaming/SSE becomes a hard product requirement — would force a rewrite of all existing sync `BaseHTTPRequestHandler` hosts; not justified for local ops |
| Byte-offset polling for logs | SSE via chunked `wfile` loop | If real-time push (sub-second) becomes a product must-have and the threading cost is acceptable; deferred from v1.11 |
| `subprocess.Popen` registry | `multiprocessing.Process` | `Popen` gives clean OS-process isolation + separate Python interpreter per channel host (matches "channel host as separate process"); `multiprocessing` couples to parent interpreter and complicates restart |
| Stateless signed session cookies | `sqlite3` server-side sessions | Only if token revocation / active-session enumeration becomes a hard requirement; reserve `SessionStore` protocol now, swap later |
| Pure-Python aggregation over read model | `sqlite3` + SQL aggregation | If contract-log volume grows beyond in-memory rebuild cost; keep `ReportSource` protocol swappable |
| New `wecom-service` thin `http_server.py` | Merge wecom host into qqbot host | WeCom and QQBot have distinct webhook shapes/crypto; mirroring the qqbot thin-host pattern keeps channel isolation (matches v1.9 host-composition design) |

---

## Sources

- In-repo: `services/admin-web-ui/src/admin_web_ui/server.py` (`AdminWebUiServer`, `handle_admin_web_ui_request`, `self.server.*` contract), `services/admin-web-ui/src/admin_web_ui/api_client.py`, `services/admin-web-ui/src/admin_web_ui/csrf.py`, `services/qqbot-service/src/qqbot_service/http_server.py` (`QQBotWebhookServer`, `default_post_ack_scheduler`), `services/qqbot-service/src/qqbot_service/wiring.py`, `services/wecom-service/src/wecom_service/wiring.py` (no HTTP host), `packages/rbac/src/rbac/token.py` (`issue_token`/`verify_token` HMAC pattern), `services/admin-console-api/src/admin_console_api/api.py` (`handle_admin_get`/`handle_admin_put`), `services/conversation-read-view/src/conversation_read_view/read_model.py` (`ContractLogReadModel.from_records`), `packages/platform-runtime/src/platform_runtime/feature_flags.py`, `.env.example`, `.planning/PROJECT.md` (v1.11 milestone), AGENTS.md — **HIGH**
- Prior research: `.planning/research/STACK.md` (v1.10) — empty-deps + stdlib HTTP host pattern + refs-only config — **HIGH**
- Python stdlib docs: `http.server`, `subprocess`, `signal`, `logging.handlers`, `http.cookies`, `secrets`, `argparse` — stable across 3.11–3.14 — **HIGH**

---
*Stack research for: v1.11 Product Console*
*Researched: 2026-07-13*
