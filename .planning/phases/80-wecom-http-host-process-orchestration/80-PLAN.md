---
phase: 80-wecom-http-host-process-orchestration
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/wecom-service/src/wecom_service/http_server.py
  - services/wecom-service/src/wecom_service/webhook.py
  - services/wecom-service/src/wecom_service/__main__.py
  - services/qqbot-service/src/qqbot_service/__main__.py
  - services/admin-console-api/src/admin_console_api/process_supervisor.py
  - services/admin-console-api/src/admin_console_api/processes_api.py
  - services/admin-console-api/src/admin_console_api/api.py
  - services/admin-console-api/src/admin_console_api/server.py
  - services/admin-console-api/src/admin_console_api/process_registry.py
  - services/admin-web-ui/src/admin_web_ui/processes.py
  - services/admin-web-ui/src/admin_web_ui/server.py
  - services/admin-web-ui/src/admin_web_ui/dashboard.py
  - services/admin-web-ui/src/admin_web_ui/api_client.py
  - services/wecom-service/tests/test_http_server.py
  - services/wecom-service/tests/test_webhook.py
  - services/qqbot-service/tests/test_main.py
  - services/admin-console-api/tests/test_process_supervisor.py
  - services/admin-web-ui/tests/test_processes.py
  - .env.example
autonomous: true
requirements:
  - ORCH-01
  - ORCH-02
  - ORCH-03
  - ORCH-04
  - ORCH-05

must_haves:
  truths:
    - "WeCom service has a runnable `http_server.py` + `__main__.py` that exposes `POST /wecom/callback` and `GET /health` and is mirror-shaped to `qqbot_service`"
    - "QQBot service has a `__main__.py` so it can be orchestrated as `python -m qqbot_service`"
    - "`admin_console_api` has a `ProcessSupervisor` that starts/stops/restarts WeCom and QQBot host subprocesses with SIGTERM → wait → SIGKILL escalation and PID/JSON state persistence"
    - "Console API exposes `/processes` GET and `/processes/<name>/{start,stop,restart}` PUT/POST routes that are gated by auth and feature flags"
    - "Console UI has a `/processes` page that displays real-time process status and start/stop/restart buttons, CSRF-protected"
    - "`config_api.handle_config_put` calls `ProcessSupervisor.restart_for_channels` after `OperatorConfigStore.save` commits, only for the affected channel(s)"
    - "Process health is probed via `urllib.request` GET `http://<host>:<port>/health` on each channel host child"
    - "Process registry state persists to a JSON file and the console re-attaches to live PIDs on startup, warning on orphaned entries without auto-killing unknown PIDs"
    - "Secrets are passed to child processes via `env`, never via command-line arguments, and never logged"
  artifacts:
    - path: "services/wecom-service/src/wecom_service/http_server.py"
      provides: "`WeComWebhookServer` stdlib HTTP handler for `POST /wecom/callback` and `GET /health`"
      contains: "WeComWebhookServer"
    - path: "services/wecom-service/src/wecom_service/webhook.py"
      provides: "`handle_wecom_webhook_request` pure ACK-first webhook handler and post-ACK composition"
      contains: "handle_wecom_webhook_request"
    - path: "services/wecom-service/src/wecom_service/__main__.py"
      provides: "Runnable `python -m wecom_service` entry point with `ThreadingHTTPServer`, signal shutdown, and feature-flag gate"
      contains: "main"
    - path: "services/qqbot-service/src/qqbot_service/__main__.py"
      provides: "Runnable `python -m qqbot_service` entry point with `ThreadingHTTPServer` and signal shutdown"
      contains: "main"
    - path: "services/admin-console-api/src/admin_console_api/process_supervisor.py"
      provides: "`ProcessSupervisor` with `start`, `stop`, `restart`, `status`, `reconcile_on_startup`, and JSON state persistence"
      contains: "ProcessSupervisor"
    - path: "services/admin-console-api/src/admin_console_api/processes_api.py"
      provides: "`/processes` REST route handlers used by `api.py`"
      contains: "handle_process_get"
    - path: "services/admin-console-api/src/admin_console_api/api.py"
      provides: "Routes `/processes` and `/config/*` through `handle_admin_get`/`handle_admin_put` with `process_supervisor` parameter"
      contains: "process_supervisor"
    - path: "services/admin-console-api/src/admin_console_api/server.py"
      provides: "Creates `ProcessSupervisor` and injects it into the `ThreadingHTTPServer` instance"
      contains: "process_supervisor"
    - path: "services/admin-web-ui/src/admin_web_ui/processes.py"
      provides: "SSR process status panel and process-action form parsing"
      contains: "render_processes_page"
    - path: "services/admin-web-ui/src/admin_web_ui/server.py"
      provides: "`/processes` route dispatch and CSRF-protected POST proxying"
      contains: "_handle_processes"
    - path: "services/admin-web-ui/src/admin_web_ui/api_client.py"
      provides: "`proxy_put` accepts and passes `process_supervisor` to `handle_admin_put`"
      contains: "process_supervisor"
  key_links:
    - from: "services/admin-console-api/src/admin_console_api/server.py"
      to: "services/admin-console-api/src/admin_console_api/process_supervisor.py"
      via: "creates `ProcessSupervisor` and passes it to `handle_admin_put`"
      pattern: "ProcessSupervisor"
    - from: "services/admin-console-api/src/admin_console_api/api.py"
      to: "services/admin-console-api/src/admin_console_api/processes_api.py"
      via: "routes `/processes` to `handle_process_get`/`handle_process_put`"
      pattern: "/processes"
    - from: "services/admin-console-api/src/admin_console_api/api.py"
      to: "services/admin-console-api/src/admin_console_api/config_api.py"
      via: "calls `process_supervisor.restart_for_channels` after `handle_config_put` succeeds"
      pattern: "restart_for_channels"
    - from: "services/admin-web-ui/src/admin_web_ui/server.py"
      to: "services/admin-web-ui/src/admin_web_ui/processes.py"
      via: "renders `/processes` with `render_processes_page`"
      pattern: "render_processes_page"
    - from: "services/admin-web-ui/src/admin_web_ui/server.py"
      to: "services/admin-web-ui/src/admin_web_ui/api_client.py"
      via: "proxies process actions through `client.proxy_put` with `process_supervisor`"
      pattern: "proxy_put"
    - from: "services/admin-console-api/src/admin_console_api/process_supervisor.py"
      to: "services/wecom-service/src/wecom_service/__main__.py"
      via: "starts `python -m wecom_service` with env and log path"
      pattern: "wecom_service"
    - from: "services/admin-console-api/src/admin_console_api/process_supervisor.py"
      to: "services/qqbot-service/src/qqbot_service/__main__.py"
      via: "starts `python -m qqbot_service` with env and log path"
      pattern: "qqbot_service"
---

<objective>
Make WeCom a runnable HTTP host that can be orchestrated as a subprocess, and turn the admin console into a process control plane that can start/stop/restart/inspect WeCom and QQBot host processes, restart them after a config save, and probe their `/health` endpoints.

Purpose: ORCH-03 gives WeCom the same host shape as QQBot; ORCH-01 and ORCH-02 give operators a process status panel and lifecycle controls; ORCH-04 wires config-save to a graceful restart; ORCH-05 makes the console persist process state and health-check each child.

Output: `wecom_service/http_server.py`, `wecom_service/__main__.py`, `qqbot_service/__main__.py`, `admin_console_api/process_supervisor.py`, `admin_console_api/processes_api.py`, the `/processes` UI page, and green tests for host boot and orchestration.
</objective>

<execution_context>
@$HOME/.codeium/windsurf/gsd-core/workflows/execute-plan.md
@$HOME/.codeium/windsurf/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/80-wecom-http-host-process-orchestration/80-CONTEXT.md
@.planning/phases/80-wecom-http-host-process-orchestration/80-RESEARCH.md
@.planning/research/STACK.md
@.planning/research/PITFALLS.md
@.planning/research/ARCHITECTURE.md
@services/qqbot-service/src/qqbot_service/http_server.py
@services/qqbot-service/src/qqbot_service/webhook.py
@services/qqbot-service/src/qqbot_service/wiring.py
@services/qqbot-service/src/qqbot_service/config.py
@services/wecom-service/src/wecom_service/wiring.py
@services/wecom-service/src/wecom_service/ingress_runtime.py
@services/wecom-service/src/wecom_service/protocol.py
@services/wecom-service/src/wecom_service/normalization.py
@packages/channels/wecom/src/inkstatute_channels_wecom/adapter.py
@packages/channels/wecom/src/inkstatute_channels_wecom/config.py
@packages/platform-runtime/src/platform_runtime/feature_flags.py
@packages/platform-runtime/src/platform_runtime/fakes.py
@packages/platform-runtime/src/platform_runtime/protocols.py
@packages/platform-runtime/src/platform_runtime/runtime.py
@services/admin-console-api/src/admin_console_api/process_registry.py
@services/admin-console-api/src/admin_console_api/api.py
@services/admin-console-api/src/admin_console_api/server.py
@services/admin-console-api/src/admin_console_api/config_api.py
@services/admin-console-api/src/admin_console_api/health.py
@services/admin-web-ui/src/admin_web_ui/server.py
@services/admin-web-ui/src/admin_web_ui/api_client.py
@services/admin-web-ui/src/admin_web_ui/dashboard.py
@services/admin-web-ui/src/admin_web_ui/channels.py
@.env.example
</context>

<tasks>

<task type="auto">
  <name>Task 1: WeCom HTTP host and QQBot runnable entry point</name>
  <files>
    services/wecom-service/src/wecom_service/http_server.py
    services/wecom-service/src/wecom_service/webhook.py
    services/wecom-service/src/wecom_service/__main__.py
    services/qqbot-service/src/qqbot_service/__main__.py
    services/wecom-service/tests/test_http_server.py
    services/wecom-service/tests/test_webhook.py
    services/qqbot-service/tests/test_main.py
    .env.example
  </files>
  <read_first>
    services/qqbot-service/src/qqbot_service/http_server.py
    services/qqbot-service/src/qqbot_service/webhook.py
    services/wecom-service/src/wecom_service/wiring.py
    services/wecom-service/src/wecom_service/ingress_runtime.py
    packages/platform-runtime/src/platform_runtime/feature_flags.py
    packages/platform-runtime/src/platform_runtime/fakes.py
  </read_first>
  <action>
    Create `services/wecom-service/src/wecom_service/http_server.py`. It contains `WeComWebhookServer(BaseHTTPRequestHandler)` with `do_POST` for `/wecom/callback` and `do_GET` for `/health`. The `do_POST` handler reads `Content-Length` bytes with `read_request_body_once`, then awaits `handle_wecom_webhook_request(...)`. It sets `server.wired`, `server.env`, and `server.post_ack_scheduler` from the `ThreadingHTTPServer` instance. The `do_GET` handler returns `200` and JSON from `await wired.adapter.health()` when the path is `/health`; otherwise `405`. `log_message` is suppressed to avoid logging secrets.

    Create `services/wecom-service/src/wecom_service/webhook.py`. It exports `CALLBACK_PATH = "/wecom/callback"`, `build_raw_inbound_from_http`, `map_ack_to_http_response`, `run_post_ack_composition`, and `handle_wecom_webhook_request`. The handler mirrors `qqbot_service/webhook.py`: build a `RawInbound` with `channel_id="wecom"` and `metadata["callback"] = parsed_body`; await `wired.adapter.verify_and_ack(raw)`; map `AckResponse` to HTTP status/body; schedule post-ACK composition on a daemon thread when accepted and not a validation challenge. `run_post_ack_composition` calls `await wired.adapter.normalize_inbound(raw)`, branches on feedback vs message, uses `WeComRuntimeIngress.handle_callback` for messages, resolves the reply text via `runtime.output_boundary.apply("ordinary_user", ...)` and `wired.adapter.deliver` for the visible reply. All evidence is sanitized.

    Create `services/wecom-service/src/wecom_service/__main__.py` with `create_server()` and `main()`. It resolves `WECOM_HOST_HOST` (default `127.0.0.1`) and `WECOM_HOST_PORT` (default `8082`) from env, builds `RuntimeFeatureFlags.from_env()`, requires `wecom_channel_enabled` (exit `1` if OFF), resolves `INKSTATUTE_OPERATOR_CONFIG_PATH`, creates `OperatorConfigStore` if a path is set, builds a `WeComWiredRuntime` via `build_wecom_wired_runtime` with a `FakeBackendAdapter` (or configured Hermes backend if available), creates a `ThreadingHTTPServer`, sets `server.wired`, `server.env`, `server.post_ack_scheduler`, registers SIGINT/SIGTERM shutdown via a daemon thread, and runs `serve_forever()`. `main()` also parses `--host` and `--port` CLI args and sets them into `os.environ` before `create_server()`. If sibling packages are not importable, add the repo's `packages/*/src` and `services/*/src` directories to `sys.path`.

    Create `services/qqbot-service/src/qqbot_service/__main__.py` with the same entry-point shape: resolve `QQBOT_HOST_HOST` (default `127.0.0.1`) and `QQBOT_HOST_PORT` (default `8083`), require `qqbot_channel_enabled`, build `QQBotWiredRuntime` via `build_qqbot_wired_runtime` with `FakeBackendAdapter`, create a `ThreadingHTTPServer`, set `server.wired`, `server.env`, `server.post_ack_scheduler`, register signal shutdown, and run. The `QQBotWebhookServer` class already exists; this `__main__.py` only adds the entry point.

    Update `.env.example` to add `WECOM_HOST_HOST=127.0.0.1`, `WECOM_HOST_PORT=8082`, `QQBOT_HOST_HOST=127.0.0.1`, `QQBOT_HOST_PORT=8083`, `INKSTATUTE_WECOM_HOST_LOG_DIR`, `INKSTATUTE_QQBOT_HOST_LOG_DIR`, `INKSTATUTE_PROCESS_STATE_PATH`, and `INKSTATUTE_PROCESS_LOG_DIR`. Keep all values commented out by default so feature flags still default OFF.

    Create `services/wecom-service/tests/test_http_server.py`: boot `WeComWebhookServer` on an ephemeral port via `ThreadingHTTPServer`, send a `GET /health` and assert `200` and JSON containing `ok`; send a `POST /wecom/callback` with a simple sanitized callback body and assert `200` and `success` or JSON ACK body; send an oversized body and assert `400`; test that `__main__.create_server()` returns a server and refuses to boot when `wecom_channel_enabled` is OFF.

    Create `services/wecom-service/tests/test_webhook.py`: unit test `handle_wecom_webhook_request` with a `FakeBackendAdapter` and a `WeComWiredRuntime` built with a fake `OperatorConfigStore`, asserting the returned status/body is `200` and an ACK; test that a feedback callback branches to feedback handling and a message callback branches to ingress/delivery.

    Create `services/qqbot-service/tests/test_main.py`: assert `qqbot_service.__main__.create_server()` returns a `ThreadingHTTPServer` and `GET /health` returns `200` (or `405` if the existing `do_GET` returns `405`); test that it refuses to boot when `qqbot_channel_enabled` is OFF.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src:packages/operator-config/src:packages/channel-core/src:packages/channels/wecom/src:packages/channels/qqbot/src:packages/rbac/src:packages/backends/hermes/src:services/wecom-service/src:services/qqbot-service/src:services/feedback-service/src:services/conversation-read-view/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.wecom-service.tests.test_http_server services.wecom-service.tests.test_webhook services.qqbot-service.tests.test_main -q</automated>
  </verify>
  <done>`wecom_service` and `qqbot_service` have runnable `__main__.py` entry points, `POST /wecom/callback` and `GET /health` are exercised, and the new tests pass.</done>
</task>

<task type="auto">
  <name>Task 2: Process supervisor, health probe, and `/processes` API</name>
  <files>
    services/admin-console-api/src/admin_console_api/process_supervisor.py
    services/admin-console-api/src/admin_console_api/processes_api.py
    services/admin-console-api/src/admin_console_api/api.py
    services/admin-console-api/src/admin_console_api/server.py
    services/admin-console-api/src/admin_console_api/process_registry.py
    services/admin-console-api/tests/test_process_supervisor.py
    .env.example
  </files>
  <read_first>
    services/admin-console-api/src/admin_console_api/process_registry.py
    services/admin-console-api/src/admin_console_api/api.py
    services/admin-console-api/src/admin_console_api/server.py
    services/admin-console-api/src/admin_console_api/config_api.py
    packages/platform-runtime/src/platform_runtime/feature_flags.py
  </read_first>
  <action>
    Create `services/admin-console-api/src/admin_console_api/process_supervisor.py`. It defines `ProcessSupervisor` with a `threading.Lock` and a `ProcessRecord` dataclass (name, status, pid, started_at, last_exit_code, host, port, log_path, metadata). The supervisor is initialized with `env` and `config_store` and resolves `INKSTATUTE_PROCESS_STATE_PATH` (default `<INKSTATUTE_RUNTIME_DIR>/process-state.json` or `/tmp/inkstatute-process-state.json`). It has:
    - `start(name)` — allowlist `name` in `{"wecom", "qqbot"}`; build the command `python -m wecom_service` / `python -m qqbot_service`; compute `host`/`port` from env (`WECOM_HOST_HOST/PORT`, `QQBOT_HOST_HOST/PORT`); open a log file at `<INKSTATUTE_PROCESS_LOG_DIR>/<name>-host.log`; call `subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT, env=child_env, start_new_session=True)`; write a PID file and update the JSON state atomically; return the `ProcessRecord` with `status="starting"`.
    - `stop(name)` — send `proc.terminate()` (SIGTERM to process group), then `proc.wait(timeout=5)`; if still alive, `proc.kill()` and `proc.wait()`; update `ProcessRecord` with `status="stopped"` and `last_exit_code`; persist state.
    - `restart(name)` — `stop(name)` then `start(name)`, with a short `cooldown` check that waits for the previous port to become free (or just `time.sleep(0.5)` capped at 2s).
    - `status(name)` — if no `pid`, return `stopped`; call `os.kill(pid, 0)`; if alive, probe `urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2)`; map to `running`/`degraded`/`unknown`; if not alive, return `stopped` and `last_exit_code`. `status_all()` returns the list of records.
    - `reconcile_on_startup()` — read the JSON state file; for each entry, `os.kill(pid, 0)` to test liveness; if alive, wrap in `ProcessRecord` and adopt; if not, warn and mark `orphaned` (do not auto-kill).
    - `restart_for_channels(old_channels, new_channels)` — compare `old_channels` and `new_channels` (wecom/qqbot dicts); for each channel whose values differ, call `restart(channel)` unless the channel is already in `starting`/`stopping`.
    - `shutdown_all()` — called on console SIGINT/SIGTERM; terminate all managed children with SIGTERM→wait→SIGKILL.

    All `subprocess` stdout/stderr is redirected to a log file; no child `env` is logged and no secret is ever written to the state file.

    Create `services/admin-console-api/src/admin_console_api/processes_api.py` with `handle_process_get(path, supervisor, feature_flags)` and `handle_process_put(path, body, supervisor, feature_flags)`. The GET returns `200` with `{"processes": [...]}` and `{"wecom": {...}, "qqbot": {...}}` for `/processes`. The PUT handles `/processes/<name>/start`, `/processes/<name>/stop`, and `/processes/<name>/restart` by calling the supervisor. The body is ignored; only the path action matters. The `feature_flags` must have `admin_api_enabled` (or a new `process_orchestration_enabled` flag) ON; return `403` if disabled. The channel name must be in the allowlist.

    Update `services/admin-console-api/src/admin_console_api/api.py`:
    - Extend `handle_admin_get` to route `/processes` or `/processes/` to `handle_process_get(path, process_supervisor, feature_flags)` when a new optional `process_supervisor` kwarg is provided.
    - Extend `handle_admin_put` to route `/processes/<name>/...` to `handle_process_put(path, body, process_supervisor, feature_flags)`.
    - Keep the existing `/config/*` flow.

    Update `services/admin-console-api/src/admin_console_api/server.py`:
    - In `create_server`, build a `ProcessSupervisor(env, config_store)` and assign it to `httpd.process_supervisor`.
    - Call `process_supervisor.reconcile_on_startup()` before `serve_forever()`.
    - Update `_dispatch` to pass `process_supervisor=self.server.process_supervisor` to `handle_admin_get` and `handle_admin_put`.
    - Register a shutdown sequence that calls `process_supervisor.shutdown_all()` before `httpd.shutdown()`. The SIGINT/SIGTERM handler should first call `shutdown_all()` then `httpd.shutdown()` (both on a daemon thread).

    Create `services/admin-console-api/tests/test_process_supervisor.py` with unit/integration tests: start a dummy long-running Python child script and assert `status` becomes `running` and `/health` probe works (child exposes a tiny HTTP server or just `http.server` on a port); stop and assert `status` becomes `stopped` and the child PID no longer exists; restart and assert a new PID; test double-start returns the existing process; test reconcile reads a stale PID and warns without killing; test SIGTERM escalation returns `last_exit_code`.

    Update `.env.example` to add `INKSTATUTE_PROCESS_STATE_PATH` and `INKSTATUTE_PROCESS_LOG_DIR`.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src:packages/operator-config/src:packages/channel-core/src:packages/channels/wecom/src:packages/channels/qqbot/src:packages/rbac/src:packages/backends/hermes/src:services/wecom-service/src:services/qqbot-service/src:services/feedback-service/src:services/conversation-read-view/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.admin-console-api.tests.test_process_supervisor -q</automated>
  </verify>
  <done>`ProcessSupervisor` starts/stops/restarts channel hosts, probes `/health`, persists state, and the `/processes` API routes are wired into `admin_console_api`.</done>
</task>

<task type="auto">
  <name>Task 3: Process status panel UI and config-save→restart wiring</name>
  <files>
    services/admin-web-ui/src/admin_web_ui/processes.py
    services/admin-web-ui/src/admin_web_ui/server.py
    services/admin-web-ui/src/admin_web_ui/dashboard.py
    services/admin-web-ui/src/admin_web_ui/api_client.py
    services/admin-console-api/src/admin_console_api/config_api.py
    services/admin-console-api/src/admin_console_api/api.py
    services/admin-web-ui/tests/test_processes.py
    services/admin-console-api/tests/test_config_restart.py
  </files>
  <read_first>
    services/admin-web-ui/src/admin_web_ui/server.py
    services/admin-web-ui/src/admin_web_ui/api_client.py
    services/admin-web-ui/src/admin_web_ui/dashboard.py
    services/admin-web-ui/src/admin_web_ui/channels.py
    services/admin-console-api/src/admin_console_api/config_api.py
    services/admin-console-api/src/admin_console_api/api.py
  </read_first>
  <action>
    Create `services/admin-web-ui/src/admin_web_ui/processes.py` with:
    - `render_processes_page(api_data, identity, csrf_token, error_message=None, success_flash=None)` that returns an HTML page with a nav header, a gate-honesty banner, a process status table showing `name`, `status`, `pid`, `uptime`, `last_exit_code`, `health`/`live` status, and one form per process with CSRF-protected start/stop/restart buttons. All dynamic values are passed through `html.escape`. The form POSTs to `/processes` with fields `name` and `action`.
    - `parse_processes_form(form_map)` to validate `name` in `{"wecom", "qqbot"}` and `action` in `{"start", "stop", "restart"}`.
    - `ERROR_*` and `SUCCESS_FLASH` strings consistent with `channels.py`.

    Update `services/admin-web-ui/src/admin_web_ui/server.py`:
    - Add `("/processes", "Process Orchestration")` to `_SECTION_MAP` and `_POST_ROUTES`.
    - Add `_handle_processes(...)` function that handles GET (renders status) and POST (validates CSRF, calls `client.proxy_put(handle_admin_put, f"/processes/{name}/{action}", body={}, ..., process_supervisor=process_supervisor)`, then re-renders the page with a flash).
    - Update `handle_admin_web_ui_request` to dispatch `/processes` to `_handle_processes`.
    - Ensure `httpd.process_supervisor` is created in `create_server` and passed to `_handle_processes`.

    Update `services/admin-web-ui/src/admin_web_ui/dashboard.py`:
    - Add `("/processes", "Process Orchestration")` to `_page_template` `nav_items`.
    - Add a card in `_render_index` for `Process Orchestration`.

    Update `services/admin-web-ui/src/admin_web_ui/api_client.py`:
    - Extend `proxy_put` signature to accept `process_supervisor` kwarg and pass it as `process_supervisor=process_supervisor` to `handle_admin_put`.

    Update `services/admin-console-api/src/admin_console_api/config_api.py`:
    - Add an optional `process_supervisor` parameter to `handle_config_put`.
    - Before returning, after `store.save(updated, feature_flags=feature_flags)` succeeds, if the section is `channels` and `process_supervisor` is not None, call `process_supervisor.restart_for_channels(old_channels, new_channels)`. Compute `old_channels` from `document_to_payload(current)["channels"]` and `new_channels` from `document_to_payload(updated)["channels"]`. Only restart channels whose `wecom` or `qqbot` values differ.

    Update `services/admin-console-api/src/admin_console_api/api.py`:
    - Pass `process_supervisor` from `handle_admin_put` into `handle_config_put(path, body, store, feature_flags, process_supervisor=process_supervisor)`.

    Create `services/admin-web-ui/tests/test_processes.py` with integration tests: GET `/processes` returns the page with the status table; POST `/processes` with `name=wecom` and `action=start` and a valid CSRF token proxies the action and re-renders; POST with invalid CSRF token returns `403`; POST with unknown name/action returns `400`.

    Create `services/admin-console-api/tests/test_config_restart.py` with integration tests: `PUT /config/channels` with changed `wecom.enabled` triggers `ProcessSupervisor.restart_for_channels` and only `wecom` is restarted; unchanged `qqbot` is not restarted; a `wecom` ref-only change still triggers restart; the config is saved before the restart is initiated.
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src:packages/operator-config/src:packages/channel-core/src:packages/channels/wecom/src:packages/channels/qqbot/src:packages/rbac/src:packages/backends/hermes/src:services/wecom-service/src:services/qqbot-service/src:services/feedback-service/src:services/conversation-read-view/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.admin-web-ui.tests.test_processes services.admin-console-api.tests.test_config_restart -q</automated>
  </verify>
  <done>The `/processes` UI panel renders real-time status with start/stop/restart controls, config save triggers a graceful restart of only the affected channel, and all orchestration routes are CSRF-protected.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Operator browser → `admin-web-ui` | SSR HTML over HTTP; process status and action buttons are escaped. |
| Admin console UI → `admin-console-api` | In-process `handle_admin_put` calls with `process_supervisor`; `admin-console-api` server is a separate process with its own supervisor and shared state file. |
| Console → channel host child | `subprocess.Popen` with `env` injection; no command-line secrets; stdout/stderr redirected to log files. |
| Channel host → external services | WeCom/QQBot hosts are gated by `*_channel_enabled` flags; live IO is fail-closed. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-80-01 | Elevation | Process start/stop via forged POST | mitigate | CSRF token validation on every `/processes` POST; `RbacGuard` on API routes. |
| T-80-02 | Information Disclosure | Child env leaked in logs | mitigate | Never log `env` or `Popen` args; suppress `log_message`; state file stores refs and process metadata only. |
| T-80-03 | Elevation | Command injection via `name` | mitigate | Allowlist `name` to `wecom`/`qqbot`; action allowlist `start`/`stop`/`restart`; command is a fixed list `[python, -m, <package>]`. |
| T-80-04 | Denial of Service | Orphaned children after console crash | mitigate | PID/JSON state file + `reconcile_on_startup`; console SIGINT handler calls `shutdown_all`. |
| T-80-05 | Tampering | Config-save applies half-written config | mitigate | `store.save` returns before `restart_for_channels`; child re-reads config at startup. |
| T-80-06 | Denial of Service | Blocked console thread on `Popen.wait` | mitigate | Start/stop/restart return immediately; `status` is polled on GET. |
| T-80-07 | Information Disclosure | `/health` response exposes secrets | mitigate | `WeComChannelAdapter.health` returns `ComponentHealth` with `secret_refs_configured` booleans; `qqbot_service` `do_GET` returns a static allowlisted health JSON. |
</threat_model>

<verification>
`services.wecom-service.tests.test_http_server`, `services.wecom-service.tests.test_webhook`, `services.qqbot-service.tests.test_main`, `services.admin-console-api.tests.test_process_supervisor`, `services.admin-web-ui.tests.test_processes`, and `services.admin-console-api.tests.test_config_restart` all pass. `python -m wecom_service` and `python -m qqbot_service` boot on configured ports and respond to `GET /health`. The console `/processes` page shows live WeCom/QQBot state and config save restarts the affected channel.
</verification>

<success_criteria>
1. WeCom service has a runnable HTTP host entry point (`http_server.py` + `__main__.py`) mirroring qqbot-service, with `POST /wecom/callback` and `GET /health`.
2. Operator can view a process status panel showing WeCom and QQBot host state (running/stopped/unknown, PID, uptime, last exit code) in real time, and can start/stop/restart each host subprocess with SIGTERM→wait→SIGKILL escalation; secrets are passed to children via environment (never argv).
3. Saving channel config from the console orchestrates a restart of only the affected channel host (config-save atomic commit → graceful restart → apply), consistent with `apply_semantics=restart_required`; a half-written config is never applied to the child.
4. Console probes each channel host's `/health` endpoint via urllib and displays live/unreachable status; process registry state persists across console restarts (re-attach to running children via PID file reconciliation, warning on orphaned entries without auto-killing unknown PIDs).
</success_criteria>

<output>
Create `.planning/phases/80-wecom-http-host-process-orchestration/80-SUMMARY.md` when done.
</output>

## Source Audit

| SOURCE | ID | Feature/Requirement | Plan | Status | Notes |
|--------|----|---------------------|------|--------|-------|
| GOAL | — | "WeCom service has a runnable HTTP host mirroring qqbot-service, and operators can start/stop/restart/inspect WeCom and QQBot host subprocesses from the console with graceful shutdown, config-save→restart wiring, and live health probes" | 01 | COVERED | Task 1 covers WeCom host; Task 2 covers supervisor and health probes; Task 3 covers UI and config-save restart. |
| REQ | ORCH-01 | Process status panel showing WeCom and QQBot host state | 01 | COVERED | Task 3 UI `/processes` and Task 2 API `/processes`. |
| REQ | ORCH-02 | Start/stop/restart WeCom and QQBot host subprocesses with SIGTERM→wait→SIGKILL | 01 | COVERED | Task 2 `ProcessSupervisor.start/stop/restart`. |
| REQ | ORCH-03 | WeCom runnable HTTP host entry point (`http_server.py` + `__main__.py`) mirroring qqbot-service | 01 | COVERED | Task 1 creates `wecom_service/http_server.py`, `webhook.py`, and `__main__.py`; also adds `qqbot_service/__main__.py` to make QQBot orchestrable. |
| REQ | ORCH-04 | Config-save orchestrates restart of affected channel host | 01 | COVERED | Task 3 `config_api.handle_config_put` calls `process_supervisor.restart_for_channels` after `store.save`. |
| REQ | ORCH-05 | Console probes `/health` via urllib; process registry persists across restarts | 01 | COVERED | Task 2 `ProcessSupervisor.status` uses `urllib.request`; `reconcile_on_startup` and JSON state file provide persistence. |
| RESEARCH | — | WeCom HTTP host mirroring `qqbot_service` pattern | 01 | COVERED | Task 1. |
| RESEARCH | — | `ProcessSupervisor` with `subprocess.Popen`, PID files, JSON state, `urllib` health probe | 01 | COVERED | Task 2. |
| RESEARCH | — | Config-save→restart ordering, no half-written config | 01 | COVERED | Task 3. |
| CONTEXT | — | Claude's Discretion (all implementation choices) | 01 | COVERED | Plan uses existing stdlib and codebase patterns. |
| CONTEXT | — | Deferred Ideas: none | 01 | COVERED | No deferred ideas are implemented. |
