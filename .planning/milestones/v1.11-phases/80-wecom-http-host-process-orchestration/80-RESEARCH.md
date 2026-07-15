# Phase 80 — Research Notes

**Phase:** 80 — WeCom HTTP Host + Process Orchestration  
**Researched:** 2026-07-13  
**Domain:** WeCom stdlib `http.server` host, subprocess process orchestration, health probes, and config-save→restart wiring for the v1.11 Product Console.  
**Confidence:** HIGH

> Note: `gsd-phase-researcher` subagent spawning was not available in this environment (no MCP subagent server, no Anthropic API key). The orchestrator performed the research directly using the repository, Python stdlib docs, and the existing GSD research artifacts.

## User Constraints

Copied from `80-CONTEXT.md` (auto-generated, no locked decisions):

- **Claude's Discretion:** All implementation choices are at Claude's discretion. Use the ROADMAP phase goal, success criteria, and codebase conventions.
- **Deferred Ideas:** None — discuss phase skipped.

### Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ORCH-01 | Process status panel showing WeCom and QQBot host state (running/stopped, PID, uptime, last exit code) in real time. | `ProcessRegistry` stub exists (Phase 79); need `ProcessSupervisor` + `/processes` API + UI panel. |
| ORCH-02 | Start/stop/restart WeCom and QQBot host subprocesses with SIGTERM → wait → SIGKILL escalation. | `subprocess.Popen` + `os.kill` stdlib; `start_new_session=True` for clean process groups. |
| ORCH-03 | WeCom service has runnable HTTP host entry point (`http_server.py` + `__main__.py`) mirroring qqbot-service. | `wecom_service` has wiring/adapter/ingress primitives; needs a `WeComWebhookServer` and `__main__.py` with `ThreadingHTTPServer`. |
| ORCH-04 | Saving channel config orchestrates a restart of the affected channel host (config-save → graceful restart → apply). | `config_api.handle_config_put` already atomic; `ProcessSupervisor.restart(channel)` must be called after successful save. |
| ORCH-05 | Console probes each channel host's `/health` endpoint via urllib and displays live/unreachable status; process registry persists across console restarts. | `urllib.request` to child's `/health`; PID-file/JSON state file for re-attach; `os.kill(pid, 0)` for liveness. |

## Summary

Phase 80 turns the WeCom service into a runnable subprocess host and makes the admin console a process control plane. The work falls into three areas:

1. **WeCom HTTP host (`wecom_service/http_server.py` + `__main__.py`)** — mirror `qqbot_service` ACK-first webhook handling: `POST /wecom/callback` delegates to `WeComChannelAdapter.verify_and_ack` and schedules post-ACK composition (`normalize_inbound` → `WeComRuntimeIngress.handle_callback` → `output_boundary` → `adapter.deliver`). `GET /health` returns the adapter's `ComponentHealth` as JSON.
2. **Process orchestrator (`admin_console_api/process_supervisor.py`)** — start/stop/restart `wecom_service` and `qqbot_service` as `subprocess.Popen` children, with SIGTERM→wait→SIGKILL escalation, PID-file persistence, and `/health` polling via `urllib`.
3. **Console integration (`admin_console_api` routes + `admin_web_ui` `/processes` page + `/config/channels` restart wiring)** — a read-only process status panel, POST start/stop/restart actions (CSRF-protected), and a config-save hook that restarts the affected channel after `OperatorConfigStore.save` commits.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| WeCom HTTP host / port binding | `wecom_service` | `packages/platform-runtime` | The host is a stdlib HTTP wrapper around the existing WeCom adapter/runtime primitives. |
| Process lifecycle (start/stop/restart) | `admin_console_api` | `admin_web_ui` | Console API owns the control plane; UI only renders forms and proxies POSTs. |
| Child health probing | `admin_console_api` | — | `urllib.request` GET `/health` from each channel host child. |
| Process state persistence | `admin_console_api` | — | JSON state file under `INKSTATUTE_RUNTIME_DIR` so console restart can re-attach to running children. |
| Config-save → restart trigger | `admin_console_api` (`config_api`) | `admin_console_api` (`process_supervisor`) | Config save must commit first, then restart only the affected channel. |
| Process status UI | `admin_web_ui` | `admin_console_api` | SSR page; all dynamic content escaped; CSRF tokens on POST actions. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `http.server.ThreadingHTTPServer` | Python stdlib | WeCom host HTTP binding with concurrent request handling. | Reuses the same pattern as `qqbot_service/http_server.py` and the admin console entry points. |
| `subprocess.Popen` | Python stdlib | Launch and signal channel host processes. | Stdlib-only, no `psutil` or external supervisor. |
| `signal` | Python stdlib | Graceful shutdown and SIGTERM escalation. | Required for clean process group termination. |
| `urllib.request` | Python stdlib | Probe each channel host's `/health` endpoint. | No external HTTP client; matches the no-new-deps constraint. |
| `threading` | Python stdlib | `Lock` for `ProcessSupervisor` registry and `ProcessRegistry`. | `ThreadingHTTPServer` in admin console requires thread-safe state. |
| `json` / `os` / `pathlib` | Python stdlib | PID/state file persistence, env construction, path resolution. | Already used by `OperatorConfigStore` and runtime audit. |
| `datetime` | Python stdlib | Uptime and `started_at` timestamps in `ProcessRecord`. | ISO 8601 UTC strings. |

### Supporting

| Library | Purpose | When to Use |
|---------|---------|-------------|
| `wecom_service.wiring` | Build `WeComWiredRuntime` for the host handler. | In `wecom_service/http_server.py` to compose adapter + runtime. |
| `wecom_service.protocol` | `ack_response()`, `parse_callback_envelope()`. | In `handle_wecom_webhook_request` and `WeComChannelAdapter`. |
| `qqbot_service` | Existing QQBot host handler and wiring. | `ProcessSupervisor` starts `python -m qqbot_service` after adding a `__main__.py`. |
| `platform_runtime.feature_flags` | `RuntimeFeatureFlags.from_env()` and `require_enabled`. | Gate each channel host and the orchestrator routes. |

### Package Legitimacy Audit

No external packages are introduced. All stack items are Python stdlib or existing monorepo packages.

## Architecture Patterns

### WeCom HTTP host pattern

Mirror `qqbot_service/http_server.py`:

1. `WeComWebhookServer(BaseHTTPRequestHandler)` accepts `POST /wecom/callback` and `GET /health`.
2. `read_request_body_once` reads `Content-Length` bytes and builds a `RawInbound` with `channel_id="wecom"`.
3. `handle_wecom_webhook_request` awaits `wired.adapter.verify_and_ack(raw)` and returns the ACK body.
4. Accepted non-challenge callbacks schedule post-ACK composition on a daemon thread (matching `qqbot_service` default scheduler).
5. `GET /health` returns `json.dumps(await wired.adapter.health())` with `Content-Type: application/json`.
6. `__main__.py` builds `WeComWiredRuntime` from env/operator-config, binds `ThreadingHTTPServer`, sets `server.wired`, and installs SIGINT/SIGTERM shutdown handlers.

### Process orchestration pattern

1. `ProcessSupervisor` owns a `dict[str, ProcessRecord]` guarded by a `threading.Lock`.
2. `start(channel)`:
   - Resolve command: `python -m wecom_service` / `python -m qqbot_service`.
   - Build child `env` from `os.environ` plus `INKSTATUTE_WECOM_*` / `INKSTATUTE_QQBOT_*` values (if using `env:*` refs) — but prefer refs: the child resolves refs from `env` at startup.
   - `Popen` with `stdout=open(log_path, "ab")`, `stderr=STDOUT`, `start_new_session=True`.
   - Write PID file (`<runtime_dir>/wecom-host.pid` or `qqbot-host.pid`) and JSON state file.
   - Return `ProcessRecord` immediately; UI polls for status.
3. `stop(channel)`:
   - `proc.terminate()` (SIGTERM to process group).
   - `proc.wait(timeout=graceful)`.
   - If still alive, `proc.kill()`.
   - Update `ProcessRecord` with `last_exit_code` and `status: stopped`; remove/clear PID file.
4. `restart(channel)`:
   - `stop(channel)` then `start(channel)` after confirming port freed (or with `SO_REUSEADDR` on the host).
5. `status(channel)`:
   - `os.kill(pid, 0)` for liveness, then `urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)`.
   - Map to `running`, `degraded`, `stopped`, `unknown`.
6. `reconcile_on_startup()`:
   - Read persisted JSON state; for each entry with a PID, `os.kill(pid, 0)` to test liveness.
   - If live, adopt into `ProcessRecord`; if not, warn and mark orphaned (do not auto-kill unknown PIDs).

### Config-save → restart pattern

1. `config_api.handle_config_put` commits `store.save(updated, feature_flags=feature_flags)`.
2. On successful save, if the section is `channels`, call `process_supervisor.restart_for_channel_changes` with the changed channels (wecom, qqbot, or both).
3. The restart only happens when `apply_semantics=restart_required` — which is already in the config metadata.
4. Strict ordering: config must be committed before the child re-reads it. The child reads the operator config at startup, so `stop` + `start` after save guarantees the new config is visible.

### Anti-Patterns to Avoid

- Do **not** call `Popen.wait()` in a request handler thread — block the console UI. Return status and poll.
- Do **not** pass secrets on the command line — pass them via `env` or store refs only.
- Do **not** auto-kill unknown PIDs on startup — warn and mark orphaned.
- Do **not** restart the child before `OperatorConfigStore.save` returns — the child may read a half-written config.
- Do **not** call `server.shutdown()` inside a signal handler on the same thread — use a daemon thread.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Process start/stop | A custom supervisor daemon | `subprocess.Popen` + `ProcessSupervisor` | Stdlib is sufficient for single-machine ops; external supervisor is out of scope. |
| Health probing | `socket` connect + parse | `urllib.request.urlopen` to `/health` | Reuses existing HTTP endpoint; no new protocol. |
| Process state persistence | SQLite / DB | Atomic JSON state file (`pathlib` + `json` + `os.replace`) | Matches existing `OperatorConfigStore` atomic-file pattern; no new DB. |
| WeCom callback dispatch | New routing logic | `WeComChannelAdapter.verify_and_ack` + `WeComRuntimeIngress` | Existing package primitives already implement ACK-first, normalize, and deliver. |
| Signal escalation | `os.kill` loops with `time.sleep` | `Popen.terminate()` → `Popen.wait(timeout)` → `Popen.kill()` | Clean, stdlib, reaps child process. |

## Common Pitfalls

### Pitfall 1: Blocking the console UI with subprocess waits
- **What goes wrong:** `AdminWebUiServer` (or `AdminConsoleApiServer`) dispatches on `ThreadingHTTPServer`, but a long `Popen.wait()` inside a request handler still blocks the response thread and can exhaust the pool.
- **How to avoid:** Start/stop/restart handlers return immediately with a `status` of `stopping` / `starting` and a `last_action_at` timestamp; the UI polls `/processes` to see the final state.

### Pitfall 2: Orphaned channel hosts on console restart
- **What goes wrong:** The process registry is in-memory; after a console crash, the WeCom/QQBot hosts keep running and the new console can't find them.
- **How to avoid:** Persist a small JSON state file (`process-state.json`) with `name`, `pid`, `started_at`, `host`, `port`, `log_path`. On startup, `reconcile` and adopt live PIDs. Do not auto-kill unknown PIDs.

### Pitfall 3: Half-written config on restart
- **What goes wrong:** `config_api.handle_config_put` triggers restart before `store.save` completes, so the child reads stale or `.tmp` data.
- **How to avoid:** Only call `ProcessSupervisor.restart` after `store.save` returns successfully. The child must call `OperatorConfigStore.load()` at startup, not read the file directly.

### Pitfall 4: Port conflict on rapid start/stop
- **What goes wrong:** Stop then immediate start can fail with `EADDRINUSE` because the OS has not released the port.
- **How to avoid:** Set `SO_REUSEADDR` on channel host listeners, and gate `start` with a short cooldown / port-free check. The process status reflects `cooling_down` until the port is free.

### Pitfall 5: Secret leakage in process logs or command lines
- **What goes wrong:** `Popen` args or env are logged, or child stdout contains secrets.
- **How to avoid:** Never put secrets in argv. Pass `env` only. Suppress `Popen` logging and child access logs (`log_message` no-op). Redact any token in `process_supervisor` state file.

### Pitfall 6: CSRF on orchestration actions
- **What goes wrong:** New POST endpoints `/processes/wecom/start` etc. are not protected by the existing CSRF token.
- **How to avoid:** Add start/stop/restart POSTs to `_POST_ROUTES` and validate CSRF via `validate_csrf_token` in `admin_web_ui/server.py`.

## Code Examples

### Minimal WeCom HTTP host

```python
import asyncio
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

class WeComWebhookServer(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.split("?", 1)[0] != "/wecom/callback":
            self._send(404, b'{"error":"not_found"}')
            return
        body = self._read_body()
        status, resp_body, headers = asyncio.run(
            handle_wecom_webhook_request(
                "POST", self.path, dict(self.headers), body,
                wired=self.server.wired,
                env=self.server.env,
            )
        )
        self._send(status, resp_body, headers)

    def do_GET(self):
        if self.path == "/health":
            health = asyncio.run(self.server.wired.adapter.health())
            self._send(200, json.dumps(health).encode("utf-8"))
            return
        self._send(405, b'{"error":"method_not_allowed"}')
```

### Process supervisor start/stop sketch

```python
from subprocess import Popen, STDOUT

class ProcessSupervisor:
    def start(self, name: str, command: list[str], env: dict[str, str]) -> ProcessRecord:
        log_path = self._log_path(name)
        proc = Popen(
            command,
            stdout=open(log_path, "ab"),
            stderr=STDOUT,
            env=env,
            start_new_session=True,
        )
        record = ProcessRecord(name=name, status="starting", pid=proc.pid, started_at=now_iso())
        self._records[name] = record
        self._persist()
        return record

    def stop(self, name: str) -> ProcessRecord:
        record = self._records.get(name)
        proc = record and record._proc
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except TimeoutExpired:
                proc.kill()
                proc.wait()
        record.status = "stopped"
        record.last_exit_code = proc.returncode if proc else None
        self._persist()
        return record
```

## Validation Architecture

> Included because `workflow.nyquist_validation` is `true` in `.planning/config.json`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `unittest` (stdlib) |
| Quick run command | `python -m unittest services.wecom-service.tests.test_http_server services.admin-console-api.tests.test_process_supervisor services.admin-web-ui.tests.test_processes -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command |
|--------|----------|-----------|-------------------|
| ORCH-03 | WeCom host boots and responds to `POST /wecom/callback` and `GET /health` | integration | `python -m unittest services.wecom-service.tests.test_http_server -q` |
| ORCH-01 | Process status API returns WeCom/QQBot state with PID, uptime, last exit code | unit + integration | `python -m unittest services.admin-console-api.tests.test_process_supervisor -q` |
| ORCH-02 | Start/stop/restart with SIGTERM→wait→SIGKILL works | integration | `python -m unittest services.admin-console-api.tests.test_process_supervisor -q` |
| ORCH-04 | Config save triggers restart of affected channel host | integration | `python -m unittest services.admin-console-api.tests.test_config_restart -q` |
| ORCH-05 | `/health` probe via `urllib` and re-attach after console restart | integration | `python -m unittest services.admin-console-api.tests.test_process_supervisor -q` |

### Wave 0 Gaps

- `services/wecom-service/src/wecom_service/http_server.py` — new stdlib HTTP handler.
- `services/wecom-service/src/wecom_service/__main__.py` — runnable entry point.
- `services/admin-console-api/src/admin_console_api/process_supervisor.py` — process lifecycle.
- `services/admin-console-api/src/admin_console_api/processes_api.py` — `/processes` REST routes.
- `services/admin-web-ui/src/admin_web_ui/processes.py` — SSR process status panel.
- `services/admin-console-api/tests/test_process_supervisor.py` — orchestration tests.
- `services/wecom-service/tests/test_http_server.py` — WeCom host tests.
- `.env.example` — add `INKSTATUTE_WECOM_HOST_ENABLED`, `WECOM_HOST_PORT`, `WECOM_HOST_HOST`, `QQBOT_HOST_PORT`, `INKSTATUTE_PROCESS_STATE_PATH`, etc.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | Channel hosts run as separate OS processes; console does not crash with a channel host. |
| V2 Authentication | yes | Existing RBAC token / static Bearer for admin routes; no new auth. |
| V3 Session Management | no | No new session state in this phase. |
| V4 Access Control | yes | Orchestration routes must pass `_authenticate_admin` + `RbacGuard` (operator/admin). |
| V5 Input Validation | yes | Channel name and action must be allowlisted (`wecom`, `qqbot`, `start`, `stop`, `restart`). |
| V6 Cryptography | no | No new crypto; reuse `rbac` HMAC and CSRF tokens. |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Command injection via channel name | Elevation | Allowlist channel names; never interpolate user input into `Popen` args. |
| Secret leakage in child env / argv | Information Disclosure | Pass refs via `env`; never log `env` or argv; no raw secrets in state file. |
| CSRF on start/stop/restart | Elevation | Require CSRF token on every POST; bind to route and identity. |
| Orphaned privileged host processes | Denial of Service | PID-file persistence + re-attach; graceful shutdown on console SIGINT. |
| Half-written config applied | Tampering | Restart only after `store.save` returns; child calls `store.load()`. |

## Sources

### Primary (HIGH confidence)

- Codebase `services/qqbot-service/src/qqbot_service/http_server.py` — `QQBotWebhookServer` and `read_request_body_once` pattern.
- Codebase `services/qqbot-service/src/qqbot_service/webhook.py` — `handle_qqbot_webhook_request` ACK-first + post-ACK composition.
- Codebase `services/wecom-service/src/wecom_service/wiring.py` — `build_wecom_wired_runtime` and `WeComWiredRuntime`.
- Codebase `services/wecom-service/src/wecom_service/ingress_runtime.py` — `WeComRuntimeIngress.handle_callback`.
- Codebase `packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py` — `WeComChannelAdapter.verify_and_ack`, `normalize_inbound`, `deliver`, `health`.
- Codebase `services/admin-console-api/src/admin_console_api/process_registry.py` — `ProcessRegistry` and `ProcessRecord`.
- Codebase `services/admin-console-api/src/admin_console_api/config_api.py` — atomic `handle_config_put`.
- Python stdlib `subprocess` docs: https://docs.python.org/3/library/subprocess.html
- Python stdlib `http.server` docs: https://docs.python.org/3/library/http.server.html
- Python stdlib `urllib.request` docs: https://docs.python.org/3/library/urllib.request.html

### Secondary (MEDIUM confidence)

- `.planning/research/ARCHITECTURE.md` — Phase 80 architecture sketch.
- `.planning/research/PITFALLS.md` — Process orchestration pitfalls.
- `.planning/research/STACK.md` — v1.11 Product Console stack research.

## Assumptions / Low-Confidence Items

| # | Claim | Risk if Wrong |
|---|-------|---------------|
| A1 | QQBot service can be made runnable by adding `qqbot_service/__main__.py` (it has `http_server.py` but no entry point). | If another entry point is expected, `ProcessSupervisor` command can be adjusted. |
| A2 | Channel hosts are started as `python -m <package>` on the same Python interpreter as the console. | In a container, paths may differ; command can be made configurable. |
| A3 | WeCom callback signature verification is deferred to the WeCom adapter (`WeComChannelAdapter.verify_and_ack` returns `accepted` based on `config.enabled` but does not validate crypto in this phase). | If signature validation is required, `wecom_service.protocol.verify_callback_signature` can be wired in `http_server.py` after secret resolution. |
| A4 | `/health` endpoint returns a JSON dict containing at least `ok` and `component_id`. | `WeComChannelAdapter.health` already returns `ComponentHealth`; `qqbot_service` may need to add an adapter `health` method or `http_server.py` can return a static health response. |

## Out of Scope

- Live WeCom/QQ OpenAPI acceptance (carried human gates).
- Process auto-restart watchdog / supervisor (deferred to CON-F06).
- TLS/HTTPS termination in channel hosts (deferred to CON-F05).
- Log viewing / reports / audit dashboards (Phases 81–83).
- Login-session auth and RBAC token management UI (Phases 85–86).
- UI product polish (Phase 86) and integration smoke (Phase 87).

## Metadata

- **Confidence breakdown:** Standard stack HIGH, Architecture HIGH, Pitfalls HIGH, WeCom adapter behavior HIGH.
- **Research date:** 2026-07-13
- **Valid until:** 30 days (stdlib + existing codebase is stable)
