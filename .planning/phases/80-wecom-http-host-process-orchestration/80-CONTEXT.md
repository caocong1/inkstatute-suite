# Phase 80: WeCom HTTP Host + Process Orchestration - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

WeCom service has a runnable HTTP host mirroring qqbot-service, and operators can start/stop/restart/inspect WeCom and QQBot host subprocesses from the console with graceful shutdown, config-save→restart wiring, and live health probes.

### Requirements

This phase covers:

- **ORCH-01**: Operator can view a process status panel in the console showing WeCom host and QQBot host process state (running/stopped, PID, uptime, last exit code) in real time.
- **ORCH-02**: Operator can start, stop, and restart WeCom and QQBot host subprocesses from the console UI with graceful shutdown (SIGTERM → wait → SIGKILL escalation).
- **ORCH-03**: WeCom service has a runnable HTTP host entry point (`http_server.py` + `__main__.py`) mirroring qqbot-service, so it can be orchestrated as a subprocess.
- **ORCH-04**: Saving channel config from the console orchestrates a restart of the affected channel host process (config-save → graceful restart → apply), consistent with existing `apply_semantics=restart_required`.
- **ORCH-05**: Console probes each channel host's `/health` endpoint via urllib and displays live/unreachable status; process registry state persists across console restarts (re-attach to running children).

### Success Criteria (what must be TRUE)

1. WeCom service has a runnable HTTP host entry point (`http_server.py` + `__main__.py`) mirroring qqbot-service (`POST /wecom/callback` + `GET /health`), so it can be orchestrated as a subprocess.
2. Operator can view a process status panel showing WeCom and QQBot host state (running/stopped/unknown, PID, uptime, last exit code) in real time, and can start/stop/restart each host subprocess with SIGTERM→wait→SIGKILL escalation; secrets are passed to children via environment (never argv).
3. Saving channel config from the console orchestrates a restart of only the affected channel host (config-save atomic commit → graceful restart → apply), consistent with `apply_semantics=restart_required`; a half-written config is never applied to the child.
4. Console probes each channel host's `/health` endpoint via urllib and displays live/unreachable status; process registry state persists across console restarts (re-attach to running children via PID file reconciliation, warning on orphaned entries without auto-killing unknown PIDs).

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

- `qqbot_service` already has a thin stdlib HTTP host: `qqbot_service/http_server.py` (BaseHTTPRequestHandler `QQBotWebhookServer` + `handle_qqbot_webhook_request`) and `qqbot_service/wiring.py` + `webhook.py` that build a wired runtime and do ACK-first POST `/qqbot/callback` handling.
- `wecom_service` has no `http_server.py` or `__main__.py`; it has `wiring.py`, `channel_wiring.py`, `ingress_runtime.py`, `protocol.py`, `normalization.py`, and `session_runtime.py` that can be composed into a host handler.
- `admin_console_api` has a guarded `ProcessRegistry` (Phase 79) in `services/admin-console-api/src/admin_console_api/process_registry.py` with `add/remove/get/list/replace` under `threading.Lock`.
- `admin_console_api/server.py` bootstraps `ThreadingHTTPServer` and sets `config_store`, `read_model`, `feedback_queue`, `feature_flags`, `env`, and `rbac_secret` on the server instance.
- `admin-web-ui` has a `_SECTION_MAP` for dashboard rendering, CSRF-protected POST forms for `/config/channels`, and a `Channel Config` page that currently tells the operator to restart channel hosts manually.
- `RuntimeFeatureFlags` reads `INKSTATUTE_<FIELD_NAME_UPPER>` env vars and defaults all flags to OFF.
- `OperatorConfigStore` is thread-safe (Phase 79) and `config_api.handle_config_put` saves atomically via `store.save`.
</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.
</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.
</deferred>
