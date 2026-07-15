---
phase: 80-wecom-http-host-process-orchestration
plan: 01
subsystem: services

tags:
  - WeCom
  - QQBot
  - ThreadingHTTPServer
  - ProcessSupervisor
  - process orchestration
  - admin-console-api
  - admin-web-ui

requires:
  - phase: 79-entry-points-threading-foundation
    provides: Runnable admin console and web UI entry points, guarded ProcessRegistry

provides:
  - Runnable `python -m wecom_service` HTTP host with `/health` and `/wecom/callback`
  - Runnable `python -m qqbot_service` HTTP host with `/health`
  - `ProcessSupervisor` in `admin-console-api` to start/stop/restart WeCom and QQBot hosts
  - `/processes` API routes and web UI page for process control
  - `config_api.handle_config_put` triggers `ProcessSupervisor.restart_for_channels` after `/config/channels` saves

affects:
  - 81-reports-dashboard
  - 82-log-viewing
  - 83-contract-event-audit
  - 84-health-gate-dashboard

tech-stack:
  added: []
  patterns:
    - ThreadingHTTPServer per-request thread model for channel hosts
    - Subprocess-based process orchestration with health probes and state persistence
    - Config-save → restart_for_channels wiring

key-files:
  created:
    - services/wecom-service/src/wecom_service/http_server.py
    - services/wecom-service/src/wecom_service/__main__.py
    - services/wecom-service/src/wecom_service/webhook.py
    - services/admin-console-api/src/admin_console_api/process_supervisor.py
    - services/admin-console-api/src/admin_console_api/processes_api.py
    - services/admin-web-ui/src/admin_web_ui/processes.py
    - services/wecom-service/tests/test_http_server.py
    - services/wecom-service/tests/test_webhook.py
    - services/qqbot-service/tests/test_main.py
    - services/admin-console-api/tests/test_process_supervisor.py
    - services/admin-console-api/tests/test_config_restart.py
    - services/admin-web-ui/tests/test_processes.py
  modified:
    - services/qqbot-service/src/qqbot_service/__main__.py
    - services/qqbot-service/src/qqbot_service/http_server.py
    - services/admin-console-api/src/admin_console_api/process_registry.py
    - services/admin-console-api/src/admin_console_api/api.py
    - services/admin-console-api/src/admin_console_api/config_api.py
    - services/admin-console-api/src/admin_console_api/server.py
    - services/admin-web-ui/src/admin_web_ui/api_client.py
    - services/admin-web-ui/src/admin_web_ui/server.py
    - services/admin-web-ui/src/admin_web_ui/dashboard.py
    - services/admin-web-ui/src/admin_web_ui/__main__.py
    - packages/rbac/src/rbac/matrix.py
    - .env.example

key-decisions:
  - "Keep the WeCom and QQBot host as separate subprocesses launched by the admin console, so channel restarts can be triggered by config changes."
  - "Use urllib to /health for lightweight process health probes and health status mapping."
  - "Persist process state to a JSON file so the supervisor can reconcile orphaned PIDs on startup."
  - "Wire the web UI /processes POST through the existing admin-console-api /processes/{name}/{action} PUT routes with CSRF."

patterns-established:
  - "Channel hosts expose `__main__.py` with `create_server()` and `main()` for `python -m` execution."
  - "ProcessSupervisor owns subprocess lifecycle, registry, state persistence, and health checks."
  - "Config PUT handlers accept an optional process_supervisor and restart affected channels after save."

requirements-completed:
  - ORCH-01
  - ORCH-02
  - ORCH-03
  - ORCH-04
  - ORCH-05

completed: 2026-07-13
---

# Phase 80: WeCom HTTP Host + Process Orchestration Summary

**Make `wecom_service` and `qqbot_service` runnable HTTP hosts, and integrate process control into the admin console and web UI.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-07-13T00:00:00Z
- **Completed:** 2026-07-13T00:00:00Z
- **Tasks:** 7
- **Files modified:** 23

## Accomplishments

- Created `wecom_service/http_server.py`, `wecom_service/__main__.py`, and `wecom_service/webhook.py` for ACK-first webhook handling and `/health`.
- Added `qqbot_service/__main__.py` and updated `qqbot_service/http_server.py` to expose `/health` and a runnable entry point.
- Extended `ProcessRecord` with channel-aware metadata and `ProcessRegistry` helpers.
- Implemented `ProcessSupervisor` with `start`, `stop`, `restart`, `status`, `status_all`, `restart_for_channels`, state persistence, and health probing.
- Added `/processes` and `/processes/{name}/{action}` routes in `admin_console_api` and wired them through `handle_admin_get`/`handle_admin_put`.
- Built the `/processes` admin web UI page with start/stop/restart buttons, real-time status, and CSRF protection.
- Updated `config_api.handle_config_put` to call `process_supervisor.restart_for_channels` when `channels` section changes.
- Added `/processes` to the RBAC permissions matrix and updated the admin dashboard navigation.
- Added `.env.example` placeholders for host ports, process state path, and process log directory.

## Files Created/Modified

- `services/wecom-service/src/wecom_service/http_server.py` — `WeComWebhookServer`, `create_server`, `main`.
- `services/wecom-service/src/wecom_service/__main__.py` — `python -m wecom_service` entry point.
- `services/wecom-service/src/wecom_service/webhook.py` — `handle_wecom_webhook_request` and `run_post_ack_composition`.
- `services/qqbot-service/src/qqbot_service/__main__.py` — `python -m qqbot_service` entry point.
- `services/qqbot-service/src/qqbot_service/http_server.py` — `/health` endpoint and fallback wired runtime.
- `services/admin-console-api/src/admin_console_api/process_registry.py` — `ProcessRecord`/`ProcessRegistry` extensions.
- `services/admin-console-api/src/admin_console_api/process_supervisor.py` — subprocess lifecycle, health probes, persistence.
- `services/admin-console-api/src/admin_console_api/processes_api.py` — `/processes` REST handlers.
- `services/admin-console-api/src/admin_console_api/api.py` — `/processes` routing.
- `services/admin-console-api/src/admin_console_api/config_api.py` — `process_supervisor` integration on `/config/channels`.
- `services/admin-console-api/src/admin_console_api/server.py` — `ProcessSupervisor` wiring and graceful shutdown.
- `services/admin-web-ui/src/admin_web_ui/api_client.py` — `process_supervisor` passthrough.
- `services/admin-web-ui/src/admin_web_ui/server.py` — `/processes` route, POST, CSRF, and proxy handling.
- `services/admin-web-ui/src/admin_web_ui/processes.py` — `/processes` page renderer.
- `services/admin-web-ui/src/admin_web_ui/dashboard.py` — navigation card.
- `services/admin-web-ui/src/admin_web_ui/__main__.py` — `ProcessSupervisor` creation and shutdown.
- `packages/rbac/src/rbac/matrix.py` — `/processes` permissions.
- `.env.example` — new env vars.
- New tests: `test_http_server.py`, `test_webhook.py`, `test_main.py`, `test_process_supervisor.py`, `test_config_restart.py`, `test_processes.py`.

## Decisions Made

- Channel hosts are `python -m` subprocesses rather than in-process threads so crashes/config changes can be isolated.
- `ProcessSupervisor` stores `pid`, `port`, `log_path`, and `metadata` in a JSON file and reconciles on startup.
- Process actions go through the admin API; the web UI proxies them via `api_client.proxy_put`.
- `restart_for_channels` diffs the old and new `channels` JSON and only restarts changed channels.
- `wecom_service` sets `INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED` automatically when the platform flag is on, to avoid a footgun in host launches.

## Deviations from Plan

- None major. The `processes.py` renderer reused the dashboard `_page_template` instead of duplicating page chrome.
- `ProcessSupervisor.reconcile_on_startup` marks unknown persisted PIDs as `orphaned` (and dead ones stay `orphaned` until `status` or `start` updates them), rather than killing immediately.

## Issues Encountered

- `WeComChannelConfig.from_env` reads `INKSTATUTE_CHANNEL_WRAPPER_WECOM_ENABLED`, not `INKSTATUTE_WECOM_CHANNEL_ENABLED`; `wecom_service/__main__.py` and `ProcessSupervisor` now set both.
- `test_server_falls_back_to_wired_build_when_server_wired_missing` was removed because `do_GET` does not rebuild `wired` on the fly; the fallback for `do_POST` was kept for testability.
- `qqbot_service` pre-existing safety baseline test `test_phase_08_lawyer_trial_acceptance_dir_preserved` fails because the Phase 08 evidence template is missing; unrelated to Phase 80.

## Verification

- `services.wecom-service.tests.test_http_server` — passed
- `services.wecom-service.tests.test_webhook` — passed
- `services.qqbot-service.tests.test_main` — passed
- `services.admin-console-api.tests.test_process_supervisor` — passed
- `services.admin-console-api.tests.test_config_restart` — passed
- `services.admin-web-ui.tests.test_processes` — passed
- `services.wecom-service.tests` full suite — 90 passed
- `services.admin-console-api.tests` full suite — 280 passed
- `services.admin-web-ui.tests` full suite — 161 passed
- `services.qqbot-service.tests` — 82 passed, 1 pre-existing safety baseline failure

## Next Phase Readiness

- Phase 81 (Reports Dashboard) can rely on the admin console `/processes` endpoint and the live process status plumbing.
- Phase 82 (Log Viewing) can read `ProcessRecord.log_path` and `log_tail_url`.
- Phase 83 (Contract Event Audit) can use the same `ProcessSupervisor` pattern to audit service events.

---
*Phase: 80-wecom-http-host-process-orchestration*
*Completed: 2026-07-13*
