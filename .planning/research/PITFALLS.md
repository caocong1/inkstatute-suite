# Pitfalls Research: v1.11 Product Console

**Domain:** Adding runnable service entry points, process orchestration, observability (reports/logs/audit/health), auth (token management + login session interface), and product polish to the existing InkStatute admin console — a stdlib `http.server` SSR system with atomic JSON file storage, no DB, no JS frameworks, default-OFF feature flags, and a static-token + HMAC-CSRF auth model.
**Researched:** 2026-07-13
**Confidence:** HIGH

This research covers common mistakes when **adding these features on top of the already-shipped v1.10 admin console** — not greenfield. The existing system has: `AdminWebUiServer` (a bare `BaseHTTPRequestHandler` with **no** `__main__.py`, no `HTTPServer` instantiation, no signal handling, no port binding — tests dispatch directly to `handle_admin_web_ui_request`/`_dispatch`), `admin-console-api` (static `ADMIN_API_TOKEN` Bearer auth via `hmac.compare_digest`), `OperatorConfigStore` (atomic `.tmp` + `os.replace` JSON writes), `ContractLogReadModel` (loads the **entire** JSONL into memory via `read_text().splitlines()` then sorts and indexes in-process), `csrf.py` (HMAC-signed tokens bound to identity+route, **no cookies, no nonce state, no sessions**), and a CSP of `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'`. Phases continue from **79**.

Suggested phase themes (roadmap may renumber): **79 ENTRY-RUN** (runnable entry points, port binding, signal handling, startup scripts), **80 ORCHESTRATION** (start/stop/inspect channel host processes, config-save→restart), **81 REPORTS** (session/task volume, completion/long-task rates, feedback distribution from JSONL), **82 LOG-VIEW** (real-time runtime log viewing with level filter/search), **83 AUDIT-EVENTS** (AgentTurn/FeedbackEvent stream view with trace_id tracking), **84 HEALTH-GATE-DASH** (service health, gate pass rate, flag/human-gate status), **85 AUTH-TOKEN** (RBAC token issue/revoke/expire management), **86 AUTH-SESSION** (reserved login + session cookie interface, MVP token-only), **87 POLISH** (error pages, nav, responsive, one-click startup, .env.example).

---

## Process Orchestration Pitfalls

### Pitfall 1: Blocking the single-threaded request handler with subprocess waits

- **What goes wrong:** `AdminWebUiServer` extends `BaseHTTPRequestHandler`, which is **single-threaded** by default — one request at a time. A "stop process" handler that calls `proc.wait(timeout=...)` or `proc.poll()` in a loop, or a "start" handler that waits for port-readiness, freezes the **entire** admin UI for every concurrent user. Operators hit the console during a stuck stop and conclude the console is dead, then kill the console itself — orphaning the channel host.
- **Warning sign:** `do_POST` handler calls `subprocess.Popen.wait(...)` or `time.sleep` inside the request dispatch path; `handle_admin_web_ui_request` takes >1s on orchestration routes; no `ThreadingHTTPServer` in the entry point.
- **Prevention:** Make orchestration handlers **non-blocking**: issue `Popen` with `start_new_session=True`, record the handle in a process table, and return immediately with a "starting/stopping" status. Poll status on a **separate** GET (`/processes/<name>/status`) with short timeouts. If blocking is unavoidable for a specific step (e.g. confirm port freed), cap the wait at ≤2s and return partial status rather than holding the connection. Decide threading model in **Phase 79** before any orchestration handler is written in **Phase 80**.
- **Phase:** 79 ENTRY-RUN (threading decision) → 80 ORCHESTRATION (non-blocking handlers).

### Pitfall 2: Zombie processes and leaked process handles

- **What goes wrong:** The console starts WeCom/QQBot host processes via `Popen` but never reaps them. On stop, the handler calls `proc.terminate()` and forgets the handle; the child becomes a zombie until the console exits. On console crash/restart, the process table (in-memory) is lost and the channel hosts keep running **orphaned** — a second "start" then fails with a port conflict, and the operator cannot tell which console owns which process.
- **Warning sign:** Process table is a plain `dict` on the server object with no PID-file or on-disk record; no `proc.wait()` after `terminate()`; no reaper on console startup; "start" returns "port in use" after a crash.
- **Prevention:** Write a PID file per managed process (e.g. `run/<service>.pid`) at start; on console startup, reconcile the PID file against live PIDs (`os.kill(pid, 0)`) and either adopt or clean up stale entries. After `terminate()`, always `wait()` (with a `kill` escalation timeout) to reap. Persist process metadata (name, pid, started_at, status) in an atomic JSON file so a restarted console can re-adopt. Add a regression test: start→crash-console→restart-console→verify adoption, and start→stop→verify no zombie via `psutil`-free `os.waitpid`.
- **Phase:** 80 ORCHESTRATION.

### Pitfall 3: Signal handling that orphans channel hosts on console shutdown

- **What goes wrong:** The new `__main__.py` installs a SIGINT/SIGTERM handler that calls `httpd.shutdown()` but never terminates managed child processes. Ctrl-C on the console leaves WeCom/QQBot hosts running with no parent. Conversely, a handler that `SIGKILL`s children immediately drops in-flight WeCom ACKs and corrupts half-written JSONL event logs.
- **Warning sign:** `signal.signal(signal.SIGINT, ...)` handler only calls `server.shutdown()`; no `proc.terminate()` loop; no graceful drain; children survive `kill -INT` on the console PID.
- **Prevention:** Install a shutdown sequence in `__main__.py`: (1) stop accepting new HTTP connections (`httpd.shutdown()`), (2) for each managed process send `SIGTERM`, (3) wait up to N seconds for graceful exit, (4) `SIGKILL` survivors, (5) reap all. Use `start_new_session=True` at `Popen` so children get their own process group and can be signaled as a group. Test by sending SIGINT to the console and asserting no managed PID survives.
- **Phase:** 79 ENTRY-RUN (signal skeleton) → 80 ORCHESTRATION (child drain).

### Pitfall 4: Port conflicts and race conditions on rapid start/stop

- **What goes wrong:** Operator clicks "stop" then immediately "start" before the OS has released the port (TIME_WAIT). The new `Popen` fails with `EADDRINUSE`; the console reports "started" (because `Popen` returned a handle) but the child exits instantly — the process table shows "running" for a dead process. Or two concurrent "start" clicks (browser double-submit) spawn two hosts on the same port.
- **Warning sign:** Process table status derived only from "did Popen return" rather than "is the port listening / is the PID alive"; no idempotency guard on start; no `SO_REUSEADDR` on channel host sockets.
- **Prevention:** Status must be derived from **liveness** (`os.kill(pid, 0)`) + **readiness** (port check), not from the Popen return. Gate start/stop behind a per-process lock and an idempotency token (reuse the existing CSRF token binding to the route). After "stop", poll for port-free before allowing "start". Set `SO_REUSEADDR` on channel host listeners. Add a test: double-submit start → only one process; stop→immediate-start → waits for port release or returns "cooling down".
- **Phase:** 80 ORCHESTRATION.

### Pitfall 5: Config-save → orchestrate-restart race that applies half-written config

- **What goes wrong:** Operator saves channel config; the console triggers a restart of the WeCom host; the host re-reads config **before** the atomic `os.replace` has completed, or reads the `.tmp` file. Or the restart fires while `OperatorConfigStore.save` is mid-validation, so the host starts with the **old** config and the operator sees no change.
- **Warning sign:** Restart handler invoked synchronously inside the config-save POST before `save()` returns; restart reads config path directly instead of via `store.load()`; no ordering guarantee between persist-confirm and restart-trigger.
- **Prevention:** Strict ordering: (1) `store.save()` must return success (atomic write committed), (2) **then** enqueue restart. Never read the `.tmp` sibling. The restart handler should call `store.load()` (the committed document) and pass it to the child, or have the child call `load()` itself at startup. Add a test: save+restart under concurrency → child always sees the post-save document.
- **Phase:** 80 ORCHESTRATION (must coordinate with the existing Phase 75 channel-config apply path).

---

## Log Viewing Pitfalls

### Pitfall 6: Loading entire log files into memory on each HTTP request

- **What goes wrong:** The existing `load_records_from_jsonl` / `load_event_stream` pattern reads the **whole** file via `read_text().splitlines()` into a `list`. A log-view handler that reuses this pattern on a multi-hundred-MB runtime log (WeCom/QQBot hosts log heavily) will balloon the console's RSS to gigabytes and OOM on the first "view logs" click. Re-running it on every poll request multiplies the damage.
- **Warning sign:** Log-view handler calls `Path(...).read_text()` or `readlines()`; no byte/line cap; no streaming generator; memory grows monotonically with log size in tests.
- **Prevention:** Stream logs with a **tail-style** reader: `seek` to an offset (or last N bytes), read forward line-by-line via a buffered iterator, cap returned lines (e.g. 500–2000). For search, stream and filter in a single pass — never materialize the full file. Add a test with a synthetic 100MB log asserting bounded memory (cap returned bytes) and sub-second response. Do **not** reuse `load_event_stream` for runtime log viewing — it is schema-validated contract JSONL, not raw runtime logs.
- **Phase:** 82 LOG-VIEW.

### Pitfall 7: Blocking I/O on log reads starving the single-threaded server

- **What goes wrong:** Reading a large log file synchronously in `do_GET` blocks the only request thread. While the operator's browser waits for `/logs`, no other page loads — health dashboard, config, reports all hang. If the log is on a slow disk or NFS mount, the block is seconds.
- **Warning sign:** Log-view route handled in the same synchronous `_dispatch` path with no timeout; `read()` call with no size limit; no `ThreadingHTTPServer`.
- **Prevention:** Either (a) move to `ThreadingHTTPServer` in Phase 79 so log reads don't block other requests, **and** audit all shared mutable state (process table, config store) for thread safety, or (b) keep single-threaded but cap log read to a bounded tail with a hard byte limit and a `select`/non-blocking read timeout. Prefer (a) but treat it as a Phase 79 architectural decision with a thread-safety audit artifact.
- **Phase:** 79 ENTRY-RUN (threading decision) → 82 LOG-VIEW (bounded reads).

### Pitfall 8: Log rotation breaking the live-tail offset cursor

- **What goes wrong:** The log viewer tracks a read offset (byte position) for live-tail polling. When the host process rotates its log (`RotatingFileHandler` renames `app.log` → `app.log.1` and starts a new `app.log`), the stored offset now points past EOF of the new (smaller) file. The viewer either errors, silently stops updating, or re-streams the whole new file from zero on every poll.
- **Warning sign:** Live-tail uses a raw byte offset with no inode/dev check; no handling of "offset > file size"; rotation causes a full re-read or a 500.
- **Prevention:** Detect rotation by comparing file size + mtime (or inode) against the last-seen values; when the file shrinks or inode changes, reset the cursor to 0 and signal "log rotated" to the UI. Cap each poll's delta. If runtime logs don't yet rotate, add `RotatingFileHandler` to channel host logging in Phase 80/82 and test the viewer against an actively-rotating log.
- **Phase:** 82 LOG-VIEW (coordinate with host logging config from 80 ORCHESTRATION).

### Pitfall 9: Leaking secrets and raw legal payloads into the log viewer

- **What goes wrong:** Runtime logs from WeCom/QQBot hosts may contain callback tokens, BotSecrets, message payloads, or legal text that AGENTS.md forbids from reaching operator screens. A naive log viewer renders raw log lines verbatim into HTML — the admin boundary (`AdminUiBoundary`) only applies to assistant output, not to log lines. Even with `html.escape`, the secret is still **displayed**.
- **Warning sign:** Log-view template calls `html.escape(line)` but no redaction filter; no ban-list test for tokens/secrets in log-view output; viewer shows `Authorization: Bearer ...` or `sk-...` in lines.
- **Prevention:** Add a redaction filter **before** escape: mask patterns matching `Bearer ...`, `sk-...`, `BotSecret`, AES keys, `secret://...` refs, and any `*_REF` resolution. Apply the same ban-list discipline as the config secret-ref rule (Phase 73). Test: inject a synthetic secret into a log line → viewer output shows `[REDACTED]`.
- **Phase:** 82 LOG-VIEW (must inherit the Phase 73 SAFE secret-ref discipline).

---

## Report Pitfalls

### Pitfall 10: Rebuilding the full in-memory read model on every report request

- **What goes wrong:** `ContractLogReadModel.from_records` loads, sorts, and fully indexes **all** JSONL records in memory. A reports handler that constructs a fresh read model per HTTP request will, on a large event log, take seconds and consume hundreds of MB per request — and under `ThreadingHTTPServer`, multiple concurrent report requests multiply memory. The console becomes unresponsive exactly when operators need reports most.
- **Warning sign:** Report handler calls `load_records_from_jsonl(...)` then `from_records(...)` inline per request; no caching; no incremental aggregation; tests only use tiny fixtures so the cost is invisible.
- **Prevention:** Build the read model **once** at console startup (or on a refresh cadence) and reuse it for report queries. For large logs, compute aggregates with a **single streaming pass** over the JSONL (counters by event type / status / day) rather than building the full conversation/task index. Cache the aggregate result with an mtime-based invalidation on the JSONL file. Add a perf test with a 50k-event fixture asserting <1s report response and bounded memory.
- **Phase:** 81 REPORTS.

### Pitfall 11: Stale report data after config changes or process restarts

- **What goes wrong:** The read model is built at startup and never refreshed. After the operator restarts a channel host (which writes new events) or saves new config, the reports page shows zero new sessions because the in-memory model is frozen. Operators trust stale "completion rate: 100%" dashboards and miss failures.
- **Warning sign:** Read model constructed in `__main__` once and stored on `server.read_model` with no refresh path; no "last refreshed at" timestamp on the reports page; reports don't change after a known event was written.
- **Prevention:** Add a "last built at" timestamp to the reports page. Provide an explicit "refresh" action (POST with CSRF) that rebuilds the aggregate, and/or mtime-based auto-invalidation. Never auto-close a human gate based on a stale aggregate. Document staleness in the UI ("data through <timestamp>").
- **Phase:** 81 REPORTS.

### Pitfall 12: Timezone inconsistency in time-range report filters

- **What goes wrong:** Contract events store `occurred_at` as ISO strings (often UTC with `Z`). Report filters from the UI send local-time strings. Aggregation by day buckets events into the wrong day; "today's session count" is off by 8 hours; operators compare against their wall clock and lose trust. The existing `_parse_time_filter` in `views.py` does naive string parsing.
- **Warning sign:** Report bucketing slices on the raw `occurred_at` string without tz normalization; UI sends naive local time; no `datetime.fromisoformat` tz handling; tests use fixed UTC strings and never cross a day boundary in local time.
- **Prevention:** Normalize all `occurred_at` to aware UTC at parse time; convert to a configured display tz (default UTC, env-overridable) only at render. Bucket by the display tz explicitly. Add a test that crosses midnight in a non-UTC tz and asserts correct day buckets.
- **Phase:** 81 REPORTS.

### Pitfall 13: Report aggregation scanning unbounded JSONL without a time window

- **What goes wrong:** A "completion rate" report with no time filter scans the entire event log from the beginning of time. As the log grows over months, every report request re-reads years of events. There is no index (no DB allowed), so the only lever is bounding the scan.
- **Warning sign:** Report handler accepts no `from`/`to` params and scans all records; default time range is "all"; no early-exit when streaming past the requested window.
- **Prevention:** Default reports to a bounded window (e.g. last 7 days) with explicit wider ranges opt-in. When streaming, sort events by timestamp (JSONL is append-ordered, so reverse-iterate from EOF for recent windows) and early-exit once outside the window. Document that unbounded "all time" reports are intentionally slow on large logs.
- **Phase:** 81 REPORTS.

---

## Auth Pitfalls

### Pitfall 14: Token leakage in orchestration/audit logs and error responses

- **What goes wrong:** Today `log_message` is suppressed (`pass`) and `csrf.py` documents "no tokens logged." New orchestration logging (process start commands, audit trails) and new auth endpoints (token issue/revoke) reintroduce `print()` or `logging` calls that write the `ADMIN_API_TOKEN`, RBAC secrets, or newly-issued tokens to stdout/log files — which the log viewer (Phase 82) then **displays to operators**. A token-revoke error response echoing the token value is the same leak.
- **Warning sign:** Orchestration code logs `Popen` args that include `--admin-api-token=...`; auth handlers log `Authorization` headers; error responses include the rejected token value; new `logging` calls without a redaction filter.
- **Prevention:** Extend the existing "no tokens logged" invariant to all new code: never log `Authorization`, `ADMIN_API_TOKEN`, RBAC secrets, or issued token values. Pass secrets to children via env vars (not argv, which is visible via `ps`). Error responses return a generic "invalid token" never the value. Add a grep-based gate test: no `token`/`secret`/`bearer` literals reach any log file under tests.
- **Phase:** 80 ORCHESTRATION + 85 AUTH-TOKEN + 82 LOG-VIEW (redaction is defense-in-depth).

### Pitfall 15: Session fixation and weak session IDs from stdlib

- **What goes wrong:** The login session interface (Phase 86) introduces cookies. Using `random` (not `secrets`) for session IDs, or reusing a session ID across pre/post-login, enables session fixation. `BaseHTTPRequestHandler` has no built-in session framework, so a hand-rolled session store in an atomic JSON file is the only option — and a predictable ID makes it guessable.
- **Warning sign:** Session ID generated with `random.random()` or `uuid.uuid1()` (MAC-based); login reuses the pre-login session cookie; session store is a JSON file with no expiry sweep; no `HttpOnly`/`SameSite` on the cookie.
- **Prevention:** Generate session IDs with `secrets.token_urlsafe(32)`. On successful login, **rotate** the session ID (issue a fresh one, invalidate the old). Set cookies with `HttpOnly; SameSite=Strict; Path=/` (no `Secure` since milestone is local HTTP, but document the TLS requirement for any non-local deploy). Store sessions in an atomic JSON file with `expires_at`; sweep expired sessions on each load. Add a fixation test: pre-login cookie is invalid after login.
- **Phase:** 86 AUTH-SESSION.

### Pitfall 16: CSRF gap on new session/login endpoints

- **What goes wrong:** The existing `csrf.py` protects Phase 76 POST routes (`/config/*`) with HMAC tokens bound to identity+route. New endpoints (login, token issue/revoke, process start/stop, log refresh) added without wiring through `issue_csrf_token`/`validate_csrf_token` are CSRF-open. The login endpoint itself is a chicken-and-egg: you can't have a CSRF token before you're authenticated, so teams either skip CSRF on login (login CSRF) or issue a token on the GET login page.
- **Warning sign:** New POST routes not added to `_POST_ROUTES` with CSRF validation; login POST has no CSRF check; token-revoke POST reuses a token scoped to a different route; `validate_csrf_token` not called before mutation.
- **Prevention:** Add every new state-changing route to `_POST_ROUTES` and wire CSRF validation. For login: issue a CSRF token on the GET `/login` page (bound to route `/login` and an anonymous role), validate it on POST `/login`. After login, rotate both the session cookie and the CSRF token (bind the new token to the authenticated identity). For orchestration routes, bind the token to the exact route (`/processes/<name>/start`). Add a test: POST without/with-wrong-route CSRF token → 403.
- **Phase:** 86 AUTH-SESSION (login CSRF) + 80 ORCHESTRATION (orchestration CSRF) + 85 AUTH-TOKEN.

### Pitfall 17: Privilege escalation via dual auth paths with unequal guard enforcement

- **What goes wrong:** The system gains two auth paths: (1) existing static Bearer token → `rbac.verify_token` → `Identity` → `RbacGuard.check`, and (2) new session cookie → `Identity`. If a route checks **only** the token path or **only** the session path, a lawyer/viewer with a session can reach an operator-only route that was previously token-guarded, or vice versa. The existing `RbacGuard` is applied in `handle_admin_web_ui_request`; a new code path that bypasses that function (e.g. a login handler rendered directly) skips the guard.
- **Warning sign:** New handlers resolve `Identity` from the cookie but skip `RbacGuard.check`; some routes check token, others check session, with no unified middleware; token-management UI lets a viewer revoke an operator's token.
- **Prevention:** Unify auth resolution into a single function that returns `Identity | None` from **either** a Bearer token **or** a session cookie, then run **every** route through the existing `RbacGuard.check(role, endpoint)` — no route bypasses it. Token issue/revoke is operator-only (`Role.OPERATOR`); add a guard test per role per new route. Document that the MVP session interface is token-only (no password backend) but the `Identity`→`RbacGuard` path must still be wired so adding passwords later doesn't reopen authz.
- **Phase:** 85 AUTH-TOKEN + 86 AUTH-SESSION.

### Pitfall 18: Session store race on concurrent requests with ThreadingHTTPServer

- **What goes wrong:** If Phase 79 adopts `ThreadingHTTPServer`, concurrent requests both load the session JSON, mutate (e.g. update `last_seen`), and `os.replace` — last writer wins, losing the other request's session update. The atomic `os.replace` protects the **file write** but not the **read-modify-write cycle**. The same race applies to the token-management store and the process table.
- **Warning sign:** Session/token store uses `load()` → mutate → `save()` with no lock; `ThreadingHTTPServer` enabled; intermittent "session dropped" or "token I just revoked still works" under load.
- **Prevention:** Wrap all read-modify-write cycles on shared JSON stores in a `threading.Lock` (one per store). The `OperatorConfigStore.save` already does atomic write but the **load→mutate→save** in config handlers must also hold the lock. If staying single-threaded, document that ThreadingHTTPServer is **not** safe with these stores without locks. Add a concurrency test: N threads revoke/issue tokens → no lost updates.
- **Phase:** 79 ENTRY-RUN (decide threading + mandate locks) → 85/86 (apply locks to new stores).

---

## Integration Pitfalls

### Pitfall 19: Entry point not covered by existing tests (which bypass the socket)

- **What goes wrong:** Every existing test dispatches directly to `handle_admin_web_ui_request` or `_dispatch` — no test ever binds a socket, calls `serve_forever`, or exercises `__main__.py`. The new entry point (port binding, signal handling, `HTTPServer` wiring, attribute setup on `server.*`) ships with zero test coverage. A typo in `__main__.py` (wrong attribute name, missing `handle_admin_put`) passes all existing tests and fails only at runtime.
- **Warning sign:** `__main__.py` has no tests; `conftest` has no fixture that boots the real `HTTPServer` on an ephemeral port; CI runs only the direct-dispatch tests.
- **Prevention:** Add an entry-point integration test that boots `HTTPServer(("127.0.0.1", 0), AdminWebUiServer)` on an ephemeral port, sets all `server.*` attributes, sends a real HTTP request via `urllib.request`, and asserts a 200. Test signal handling by sending SIGINT to the thread. Keep the direct-dispatch tests for unit speed, but add at least one socket-level smoke test per service.
- **Phase:** 79 ENTRY-RUN.

### Pitfall 20: ThreadingHTTPServer introducing concurrency on non-thread-safe shared state

- **What goes wrong:** Switching to `ThreadingHTTPServer` (tempting for non-blocking logs/orchestration) makes every handler run in its own thread. The `OperatorConfigStore`, the in-memory `feedback_queue` list, the new process table, and the `ContractLogReadModel` are all shared mutable state with no locks. Concurrent config saves corrupt the JSON; concurrent reads of a model being rebuilt hit a half-mutated dict.
- **Warning sign:** `ThreadingHTTPServer` used with no `threading.Lock` around stores; `feedback_queue.append` from multiple threads; read model rebuilt in-place while another thread iterates.
- **Prevention:** Treat the threading decision as the **first** artifact of Phase 79 with an explicit thread-safety audit of every `server.*` attribute. Either (a) stay single-threaded and make all potentially-slow handlers non-blocking via bounded work + fast returns, or (b) go threaded and add locks per shared store + make the read model copy-on-rebuild (swap an immutable reference under a lock). Do not mix: a half-threaded server is the worst case.
- **Phase:** 79 ENTRY-RUN.

### Pitfall 21: CSP / no-JS constraint breaking real-time log and audit views

- **What goes wrong:** "Real-time logs" and "audit event stream" tempt implementers toward Server-Sent Events (`EventSource`) or WebSockets — both blocked by `default-src 'self'; script-src 'self'` (SSE is allowed by CSP, but `EventSource` requires JS, and the project is SSR with no JS frameworks). A meta-refresh polling hack (`<meta http-equiv="refresh">`) is CSP-legal but hammers the server on a single-threaded handler.
- **Warning sign:** Audit stream page adds `<script>` for `EventSource`; or relies on `meta refresh` with a 1s interval against a single-threaded server; inline `<script>` violates `script-src 'self'`.
- **Prevention:** Stay SSR: render a bounded snapshot of recent log/audit lines server-side, and use a **manual** "refresh" button (POST with CSRF) or a long-ish `meta refresh` (≥5s) only if threaded. No inline JS, no `EventSource`, no WebSocket. Document that "real-time" means "pollable snapshot," not push. The CSP stays exactly as-is.
- **Phase:** 82 LOG-VIEW + 83 AUDIT-EVENTS.

### Pitfall 22: Reusing the 64KB POST body cap for new endpoints that need different limits

- **What goes wrong:** `do_POST` enforces `MAX_CHANNELS_POST_BYTES = 64 * 1024` on **every** POST. New endpoints with different needs break: a token-issue form is fine, but a log-search with a long query string, or a report config with many filters, may exceed 64KB and get a 413. Conversely, raising the global cap to accommodate one endpoint weakens the DoS protection on config routes.
- **Warning sign:** New POST route silently 413s on real input; or the global cap is raised to 1MB for all routes; per-route limits don't exist.
- **Prevention:** Make the body cap **per-route** (a `{route: max_bytes}` map) with the existing 64KB as the config-route default and explicit limits for new routes. Keep a hard global ceiling. Add a test per new route at its intended limit.
- **Phase:** 79 ENTRY-RUN (per-route cap framework) → each feature phase sets its route's limit.

### Pitfall 23: Breaking the existing read-only / flag-default-OFF / no-new-DB invariants

- **What goes wrong:** Adding process orchestration, sessions, and token management tempts an in-memory DB, a `threading.Event` queue, or a new persistent store outside the atomic-JSON pattern. Or the new features ship with flags defaulting ON, breaking the "all flags default OFF" invariant and the v1.10 `test_read_only.py` expectations. AGENTS.md forbids new DB/queue unless the PRD requires.
- **Warning sign:** New `sqlite3`, `queue.Queue`-as-broker, or `multiprocessing.Manager` imports; new feature flags defaulting to `True`; `test_read_only.py` modified to allow POSTs on previously-GET-only routes; a new long-running daemon process beyond the channel hosts.
- **Prevention:** Keep all new state in atomic JSON files (`os.replace`) or in-process `threading` primitives. Every new feature flag defaults to `False`. Do **not** mutate existing read-only views or their tests — add new routes alongside. Run the existing flag-default-OFF gate test and the read-only test as part of every new phase's verification. No `sqlite3`, no `redis`, no `multiprocessing.Manager`.
- **Phase:** Every phase — enforced at 79 ENTRY-RUN via a "no new DB/queue, flags OFF" checklist item.

### Pitfall 24: Over-engineering process orchestration for local single-machine use

- **What goes wrong:** The milestone is explicitly "local/single-machine ops, prioritize usability." Implementers build a general-purpose process supervisor with retry policies, health-check probes, rolling restarts, and a dependency graph — none of which a single operator on one machine needs. This balloons scope, adds concurrency complexity (violating Pitfall 20), and delays the usable one-click startup script that is the actual deliverable.
- **Warning sign:** Orchestration module has >300 lines before a single start/stop works; retry/backoff classes; dependency ordering engine; "cluster" terminology in docs.
- **Prevention:** Scope orchestration to: start one named process, stop one named process, show status (alive + port), and "apply config → restart." No retries, no rolling, no clustering. The one-click startup script (`scripts/start_inkstatute.sh`) is the primary deliverable; the web orchestration is a convenience on top. Keep the process table a flat dict. If a feature needs >1 screen of design, it's over-engineered for this milestone.
- **Phase:** 80 ORCHESTRATION + 87 POLISH.

---

## Security Pitfalls

### Pitfall 25: Passing secrets to child processes via argv (visible in `ps`)

- **What goes wrong:** Orchestration starts channel hosts with `Popen(["python", "-m", "wecom_service", "--admin-api-token", TOKEN, ...])`. On a shared machine, any user running `ps aux` sees the token. This is a regression of the Phase 73 secret-ref discipline: secrets resolve at the process edge but then leak into the child's argv.
- **Warning sign:** `Popen` args include `--token`, `--secret`, `--api-key` values (not env); child reads config from argv; `ps` shows secret values in tests.
- **Prevention:** Pass all secrets to children via **environment variables** (`Popen(..., env={**os.environ, "ADMIN_API_TOKEN": token, ...})`), never argv. Children resolve `*_REF` / `env:VAR` at their own edge (existing pattern). Add a test that inspects the spawned child's `/proc/<pid>/cmdline` (or mocks `Popen` and asserts env, not argv).
- **Phase:** 80 ORCHESTRATION.

### Pitfall 26: Open redirect / path traversal in log and report file selection

- **What goes wrong:** A log-view route like `/logs/<service>` or a report route like `/reports/<file>` that maps the path segment directly to a filesystem path allows `../../etc/passwd` or `../../.env`. `html.escape` doesn't help — the file content is read, not reflected as HTML. Even with a base dir, symlinks inside the log dir can escape.
- **Warning sign:** `Path(log_dir) / service` with no sanitization; no `resolve()` + prefix check; service name taken raw from URL; no allowlist of valid service names.
- **Prevention:** Validate the service/file name against a **fixed allowlist** (`{"wecom", "qqbot", "adapter", "admin"}`). Resolve the full path and assert it starts with the canonical base dir (`Path(base).resolve()`). Reject paths containing `..`, absolute paths, or symlinks. Add a traversal test: `/logs/../../etc/passwd` → 404/400.
- **Phase:** 82 LOG-VIEW + 81 REPORTS.

### Pitfall 27: Login endpoint enabling timing / enumeration attacks

- **What goes wrong:** The reserved login interface compares a submitted token/password with `==` (not `hmac.compare_digest`) or returns different errors for "user not found" vs "wrong password," enabling username enumeration and token timing attacks. The existing `check_auth_header` correctly uses `compare_digest`, but a new login handler may not.
- **Warning sign:** Login handler uses `==` for token/password compare; distinct error messages per failure reason; response time differs for valid vs invalid usernames.
- **Prevention:** Always use `hmac.compare_digest` for any secret comparison (extend the existing `auth.py` pattern). Return a single generic "invalid credentials" for all failure modes. Constant-time the response regardless of which check failed. Add a timing test (statistical, or assert `compare_digest` is used via code inspection).
- **Phase:** 86 AUTH-SESSION.

### Pitfall 28: Carried human gates auto-closed by health/gate dashboard "green" display

- **What goes wrong:** The enhanced `/gates` dashboard (Phase 84) visualizes gate status. If a human gate (Phase 5 live WeCom UAT, Phase 8 lawyer trial, QQ `--live` acceptance) is rendered as a green checkmark because the underlying check returns "passed" for fixture evidence, operators and auditors mistakenly believe the human gate is closed — violating the carried-gate invariant in PROJECT.md and AGENTS.md.
- **Warning sign:** Gate dashboard shows green for Phase 5/8/QQ-live; `not_live_acceptance` honesty label from Phase 78 is dropped or hidden; human-gate rows look identical to auto-gate rows.
- **Prevention:** Render human gates with a **distinct** visual state (e.g. "HUMAN GATE — carried, not auto-closed") that cannot turn green from fixture evidence. Preserve the Phase 78 `not_live_acceptance` honesty label. Add a test: human-gate rows never render as "passed" regardless of fixture state. Never add a "mark human gate passed" button.
- **Phase:** 84 HEALTH-GATE-DASH.

### Pitfall 29: XSS via unescaped log/search/report content rendered as HTML

- **What goes wrong:** New render surfaces (log lines, search results, report tables, audit event payloads) are larger and more dynamic than the existing config pages. A log line containing `<script>alert(1)</script>` from a malicious inbound message, or an audit event with a user-controlled `trace_id`, reaches the template. `AdminUiBoundary.escape_value` exists but only if **called** — a forgotten escape on one field is XSS. CSP `script-src 'self'` mitigates inline script but `unsafe-inline` on `style-src` and attribute injection still allow exfiltration via CSS.
- **Warning sign:** Template interpolates a value without `html.escape`/`escape_value`; report tables render raw event payloads; no template-level auto-escape (stdlib has none).
- **Prevention:** Mandate that **every** value interpolated into HTML passes through `html.escape` or `AdminUiBoundary.escape_value` — no exceptions. Add a grep/AST gate test: no f-string or `.format` producing HTML with an unescaped variable. Add a reflected-XSS test per new route: inject `<script>` into every user-controlled field → output is escaped. Consider a tiny `render_value(v) -> html.escape(str(v))` helper used everywhere to prevent the "forgot to escape" class.
- **Phase:** Every rendering phase (81 REPORTS, 82 LOG-VIEW, 83 AUDIT-EVENTS, 84 HEALTH-GATE-DASH, 87 POLISH).

### Pitfall 30: Token management UI enabling self-revocation or last-admin lockout

- **What goes wrong:** The RBAC token management page (Phase 85) lets an operator revoke tokens. If an operator revokes their own token (or the only admin token), they're locked out with no recovery path on a local single-machine deploy. Or a viewer can revoke an operator's token (Pitfall 17). There's no DB to reset — the token is an env var, but a UI-issued token may be in a JSON store with no bootstrap override.
- **Warning sign:** No "cannot revoke own active token" guard; no env-var bootstrap token that always works; revocation list checked before env-token check; no confirmation step.
- **Prevention:** Prevent self-revocation (an operator cannot revoke the token they authenticated with). Always honor the `ADMIN_API_TOKEN` env var as a bootstrap override (cannot be revoked via UI), so a locked-out operator can restart with the env token. Require a CSRF'd confirmation for revoke. Add a test: revoke-own → 400; env token still works after all UI tokens revoked.
- **Phase:** 85 AUTH-TOKEN.
