---
phase: 84-health-gate-dashboard-enhancement
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - services/admin-console-api/src/admin_console_api/health.py
  - services/admin-console-api/src/admin_console_api/gates.py
  - services/admin-console-api/src/admin_console_api/api.py
  - services/admin-web-ui/src/admin_web_ui/dashboard.py
  - services/admin-console-api/tests/test_health.py
  - services/admin-web-ui/tests/test_dashboard.py
autonomous: true
requirements:
  - OBS-09
  - OBS-10
user_setup: []

must_haves:
  truths:
    - "handle_health in admin_console_api/health.py accepts process_supervisor and gate_summary parameters and returns a unified health response containing: service (admin-console-api own health), services (list of child service health dicts for admin API, WeCom host, QQBot host), gate_pass_rate (float 0.0–1.0 or null), gate_count, gates_passed, gates_failed, feature_flags (list of {name, enabled} dicts), and carried_human_gates (list of {name, status, auto_closed} dicts)"
    - "collect_service_health(process_supervisor) returns a list of service health dicts with keys: name, status, ok, host, port; the admin-console-api entry uses the existing collect_raw_health/project_health primitives; WeCom and QQBot entries are derived from process_supervisor.status_all() with ok = (status == 'running'); the raw metadata.health payload from each child probe is NOT included — only name, status, ok, host, port are exposed"
    - "collect_feature_flag_states(feature_flags) returns a list of {name, enabled} dicts for every field on RuntimeFeatureFlags, iterated via dataclasses.fields(); enabled is the bool value of each flag; no secret values are exposed (flags are booleans only)"
    - "CARRIED_HUMAN_GATES is a constant tuple of dicts: {name: 'Phase 5 WeCom UAT', status: 'carried', auto_closed: False}, {name: 'Phase 8 lawyer trial', status: 'carried', auto_closed: False}, {name: 'QQ live acceptance', status: 'carried', auto_closed: False}; this list is static and never mutated by any API call"
    - "HEALTH_ALLOWED_FIELDS is extended to include: services, gate_pass_rate, feature_flags, carried_human_gates (in addition to the existing service, status, version, secrets_configured, uptime_seconds, gate_count, gates_passed, gates_failed); project_health retains these new fields"
    - "run_gate_summary in gates.py accepts an optional timeout_seconds parameter (default GATE_TIMEOUT_SECONDS=300); when timeout_seconds is passed, subprocess.run uses that timeout instead of the default; this allows the health endpoint to use a shorter timeout (30s) than the dedicated /gates endpoint (300s)"
    - "handle_admin_get in api.py routes /health to handle_health with process_supervisor passed through; when route_query contains gates=true, run_gate_summary(timeout_seconds=30) is called and passed as gate_summary; otherwise gate_summary is None and gate fields are null"
    - "The /health response never includes secret-related fields (secret_refs_configured, api_base_url, config_path, secret_ref_names, wecom_token_ref, aes_key_ref, callback_token_ref, encoding_aes_key_ref) — project_health drops them via the positive allowlist"
    - "The _render_health_section in dashboard.py renders the unified health view with four sub-sections: (1) Service Health table with columns Service, Status, OK for each entry in services; (2) Gate Pass Rate showing gate_pass_rate as a percentage when non-null, or 'Not run — click Run Gates' with a link to /health?gates=true when null; (3) Feature Flags table with columns Flag, Enabled for each entry in feature_flags; (4) Carried Human Gates rendered with a distinct non-green visual state (amber/orange CSS class 'human-gate-carried') and the text 'HUMAN GATE — carried, not auto-closed'"
    - "No 'mark human gate passed' control, button, form, or API endpoint exists anywhere in the health or gates codebase; the carried_human_gates list is read-only and static; a source scan test asserts no 'mark_human_gate' or 'pass_human_gate' or 'close_human_gate' string appears in dashboard.py or health.py"
    - "All dynamic content in the /health web page is HTML-escaped via html.escape or _esc; CSP header is set on every response; no inline JavaScript"
    - "The gate-honesty banner (_render_gate_honesty_banner) is rendered at the top of the unified health section, preserving the existing copy: 'This console does not close live acceptance gates' and 'not_live_acceptance'"
  artifacts:
    - "admin_console_api.health.CARRIED_HUMAN_GATES constant"
    - "admin_console_api.health.collect_service_health function"
    - "admin_console_api.health.collect_feature_flag_states function"
    - "admin_console_api.health.handle_health process_supervisor + gate_summary parameters"
    - "admin_console_api.health.HEALTH_ALLOWED_FIELDS extended with services, gate_pass_rate, feature_flags, carried_human_gates"
    - "admin_console_api.gates.run_gate_summary timeout_seconds parameter"
    - "admin_console_api.api.handle_admin_get /health route passing process_supervisor and optional gate_summary"
    - "admin_web_ui.dashboard._render_health_section enhanced with service health table, gate pass rate, feature flags, carried human gates"
    - "admin_web_ui.dashboard._render_carried_human_gates_row function (distinct non-green visual state)"
    - "admin_web_ui.dashboard human-gate-carried CSS class"
    - "test_health.py unified health tests"
    - "test_dashboard.py enhanced health section tests"
  key_links:
    - "collect_service_health is called by handle_health to build the services list from process_supervisor.status_all()"
    - "collect_feature_flag_states is called by handle_health to build the feature_flags list from RuntimeFeatureFlags"
    - "run_gate_summary(timeout_seconds=30) is called by handle_admin_get when /health?gates=true is requested"
    - "handle_admin_get passes process_supervisor to handle_health (already received as a parameter)"
    - "admin-web-ui proxies /health to handle_admin_get via AdminApiClient.proxy (process_supervisor already passed in default proxy block)"
    - "_render_health_section renders the unified response from handle_health as four escaped HTML sub-sections"
    - "CARRIED_HUMAN_GATES is referenced by both handle_health (API response) and _render_carried_human_gates_row (UI rendering)"
---

<objective>
Enhance the `/health` endpoint and dashboard page to show a unified health/gate/flag view with service health from child `/health` endpoints (admin API, WeCom host, QQBot host), gate pass rate, feature flag states, and carried human gate status — preserving gate honesty. The unified view aggregates four data sources into one dashboard: (1) service health from `ProcessSupervisor.status_all()` child probes, (2) gate pass rate from `run_gate_summary()`, (3) feature flag states from `RuntimeFeatureFlags`, and (4) a static carried-human-gates list that renders with a distinct non-green visual state and no "mark passed" control.

Purpose: Give operators a single-page operational overview of platform health, gate status, and feature flag configuration, while preserving gate honesty — automated results never claim live acceptance.

Output: An enhanced `handle_health` unified handler, `collect_service_health` / `collect_feature_flag_states` primitives, `CARRIED_HUMAN_GATES` constant, `run_gate_summary` timeout parameter, enhanced `_render_health_section` with four sub-sections, and automated tests.
</objective>

<execution_context>
@$HOME/.codeium/windsurf/gsd-core/workflows/execute-plan.md
@$HOME/.codeium/windsurf/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/84-health-gate-dashboard-enhancement/84-CONTEXT.md
@services/admin-console-api/src/admin_console_api/health.py
@services/admin-console-api/src/admin_console_api/gates.py
@services/admin-console-api/src/admin_console_api/api.py
@services/admin-console-api/src/admin_console_api/server.py
@services/admin-console-api/src/admin_console_api/routes.py
@services/admin-console-api/src/admin_console_api/process_supervisor.py
@services/admin-console-api/src/admin_console_api/process_registry.py
@services/admin-console-api/src/admin_console_api/processes_api.py
@services/admin-web-ui/src/admin_web_ui/dashboard.py
@services/admin-web-ui/src/admin_web_ui/server.py
@services/admin-web-ui/src/admin_web_ui/api_client.py
@packages/platform-runtime/src/platform_runtime/feature_flags.py
@packages/rbac/src/rbac/matrix.py
@services/admin-console-api/tests/test_health.py
@services/admin-console-api/tests/test_gates.py
@services/admin-web-ui/tests/test_dashboard.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Unified health aggregator + endpoint in admin-console-api</name>
  <files>
    services/admin-console-api/src/admin_console_api/health.py
    services/admin-console-api/src/admin_console_api/gates.py
    services/admin-console-api/src/admin_console_api/api.py
    services/admin-console-api/tests/test_health.py
  </files>
  <read_first>
    services/admin-console-api/src/admin_console_api/health.py
    services/admin-console-api/src/admin_console_api/gates.py
    services/admin-console-api/src/admin_console_api/api.py
    services/admin-console-api/src/admin_console_api/process_supervisor.py
    services/admin-console-api/src/admin_console_api/process_registry.py
    services/admin-console-api/src/admin_console_api/processes_api.py
    packages/platform-runtime/src/platform_runtime/feature_flags.py
    services/admin-console-api/tests/test_health.py
    services/admin-console-api/tests/test_gates.py
  </read_first>
  <action>
    ### Modify `services/admin-console-api/src/admin_console_api/gates.py`

    Add a `timeout_seconds` parameter to `run_gate_summary`:

    ```python
    def run_gate_summary(
        repo_root: str | Path | None = None,
        *,
        timeout_seconds: int = GATE_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        """Run ``run_v2_gates.py --json-summary`` via subprocess and parse output.

        Returns a dict with ``passed`` (bool) and ``gates`` (list).  On timeout or
        JSON parse failure, returns an error dict — never raises.
        ``timeout_seconds`` overrides the default 300s ceiling (e.g. for the
        unified health endpoint which uses a shorter 30s timeout).
        """
    ```

    Implementation:
    - Replace the hardcoded `timeout=GATE_TIMEOUT_SECONDS` in the `subprocess.run` call with `timeout=timeout_seconds`.
    - The `except subprocess.TimeoutExpired` clause stays the same (returns `{"passed": False, "gates": [], "error": "timeout"}`).
    - No other changes to `handle_gates` — it calls `run_gate_summary()` with the default timeout.

    ### Modify `services/admin-console-api/src/admin_console_api/health.py`

    1. Add imports at the top:
       ```python
       from dataclasses import fields as dataclass_fields
       from platform_runtime.feature_flags import RuntimeFeatureFlags
       ```
       (`RuntimeFeatureFlags` is already imported.)

    2. Extend `HEALTH_ALLOWED_FIELDS`:
       ```python
       HEALTH_ALLOWED_FIELDS = frozenset({
           "service",
           "status",
           "version",
           "secrets_configured",
           "uptime_seconds",
           "gate_count",
           "gates_passed",
           "gates_failed",
           "gate_pass_rate",
           "services",
           "feature_flags",
           "carried_human_gates",
       })
       ```

    3. Add the `CARRIED_HUMAN_GATES` constant after `HEALTH_EXCLUDED_FIELDS`:
       ```python
       # Static, read-only list of human gates that this console never auto-closes.
       # Rendered with a distinct non-green visual state in the dashboard.
       # No API endpoint or UI control can mutate this list.
       CARRIED_HUMAN_GATES: tuple[dict[str, Any], ...] = (
           {"name": "Phase 5 WeCom UAT", "status": "carried", "auto_closed": False},
           {"name": "Phase 8 lawyer trial", "status": "carried", "auto_closed": False},
           {"name": "QQ live acceptance", "status": "carried", "auto_closed": False},
       )
       ```

    4. Add `collect_service_health` function:
       ```python
       def collect_service_health(
           process_supervisor: Any,
           feature_flags: RuntimeFeatureFlags,
           read_model: Any,
       ) -> list[dict[str, Any]]:
           """Build a list of service health dicts for the unified health view.

           Includes the admin-console-api itself plus WeCom and QQBot host
           processes.  Only name, status, ok, host, and port are exposed —
           the raw metadata.health payload from child probes is NOT included.
           """
       ```
       Implementation:
       - Start with the admin-console-api entry:
         ```python
         own_raw = collect_raw_health(feature_flags, read_model)
         own_projected = project_health(own_raw)
         services: list[dict[str, Any]] = [{
             "name": "admin-console-api",
             "status": own_projected.get("status", "ok"),
             "ok": own_projected.get("status") == "ok",
             "host": None,
             "port": None,
         }]
         ```
       - If `process_supervisor is not None`, call `process_supervisor.status_all()`:
         ```python
         if process_supervisor is not None:
             for record in process_supervisor.status_all():
                 services.append({
                     "name": record.name,
                     "status": record.status,
                     "ok": record.status == "running",
                     "host": record.host,
                     "port": record.port,
                 })
         ```
       - If `process_supervisor is None`, still include WeCom and QQBot entries with `status="unknown"`, `ok=False`:
         ```python
         else:
             for name in ("wecom", "qqbot"):
                 services.append({
                     "name": name,
                     "status": "unknown",
                     "ok": False,
                     "host": None,
                     "port": None,
                 })
         ```
       - Return `services`.

    5. Add `collect_feature_flag_states` function:
       ```python
       def collect_feature_flag_states(
           feature_flags: RuntimeFeatureFlags,
       ) -> list[dict[str, Any]]:
           """Return a list of {name, enabled} dicts for every RuntimeFeatureFlags field."""
           return [
               {"name": field.name, "enabled": bool(getattr(feature_flags, field.name))}
               for field in dataclass_fields(RuntimeFeatureFlags)
           ]
       ```

    6. Modify `collect_raw_health` to accept `process_supervisor` and include the new unified fields:
       ```python
       def collect_raw_health(
           feature_flags: RuntimeFeatureFlags,
           read_model: Any,
           gate_summary: dict[str, Any] | None = None,
           process_supervisor: Any = None,
       ) -> dict[str, Any]:
       ```
       Implementation:
       - Keep the existing raw dict construction (service, status, version, secrets_configured, uptime_seconds, secret_refs_configured, api_base_url, config_path).
       - Keep the existing gate_summary block that sets gate_count, gates_passed, gates_failed.
       - Add `gate_pass_rate`:
         ```python
         if gate_summary is not None:
             gates = gate_summary.get("gates", [])
             total = len(gates)
             passed = sum(1 for g in gates if g.get("exit_code") == 0)
             raw["gate_pass_rate"] = (passed / total) if total > 0 else None
         else:
             raw["gate_pass_rate"] = None
         ```
       - Add the unified fields:
         ```python
         raw["services"] = collect_service_health(process_supervisor, feature_flags, read_model)
         raw["feature_flags"] = collect_feature_flag_states(feature_flags)
         raw["carried_human_gates"] = list(CARRIED_HUMAN_GATES)
         ```
       - Return `raw`.

    7. Modify `handle_health` to accept `process_supervisor`:
       ```python
       def handle_health(
           feature_flags: RuntimeFeatureFlags,
           read_model: Any,
           gate_summary: dict[str, Any] | None = None,
           process_supervisor: Any = None,
       ) -> tuple[int, dict[str, Any]]:
           """Collect raw health data, project through the allowlist, return 200."""
           raw = collect_raw_health(
               feature_flags,
               read_model,
               gate_summary,
               process_supervisor=process_supervisor,
           )
           projected = project_health(raw)
           return 200, projected
       ```

    8. Update `__all__` to include `CARRIED_HUMAN_GATES`, `collect_service_health`, `collect_feature_flag_states`.

    ### Modify `services/admin-console-api/src/admin_console_api/api.py`

    1. Add import: `from .gates import handle_gates, run_gate_summary`
       (currently only `from .gates import handle_gates`).

    2. Change the `/health` route in `handle_admin_get`:
       ```python
       if route_path == "/health":
           gate_summary = None
           if route_query.get("gates") == "true":
               gate_summary = run_gate_summary(timeout_seconds=30)
           return handle_health(
               feature_flags,
               read_model,
               gate_summary=gate_summary,
               process_supervisor=process_supervisor,
           )
       ```
       `process_supervisor` is already a parameter of `handle_admin_get` — no signature change needed.

    ### Tests: `services/admin-console-api/tests/test_health.py`

    Add the following test classes/methods to the existing file:

    **UnifiedHealthTests:**
    1. **test_handle_health_with_process_supervisor:** Create a mock ProcessSupervisor (or a simple stub with `status_all()` returning two ProcessRecord objects with status="running" and status="stopped"). Call `handle_health(flags, None, process_supervisor=stub)`. Assert 200, `services` is a list of 3 dicts (admin-console-api + wecom + qqbot), each with keys `name`, `status`, `ok`, `host`, `port`.
    2. **test_handle_health_without_process_supervisor:** Call `handle_health(flags, None, process_supervisor=None)`. Assert `services` has 3 entries; wecom and qqbot have `status="unknown"`, `ok=False`.
    3. **test_collect_service_health_excludes_raw_metadata:** Build a stub ProcessRecord with `metadata={"health": {"secret": "leak"}}`. Assert the service dict does NOT contain a `metadata` key or `health` key — only `name`, `status`, `ok`, `host`, `port`.
    4. **test_collect_service_health_ok_true_when_running:** Assert `ok=True` when `record.status == "running"`.
    5. **test_collect_service_health_ok_false_when_stopped:** Assert `ok=False` when `record.status == "stopped"`.
    6. **test_collect_feature_flag_states_returns_all_flags:** Call `collect_feature_flag_states(RuntimeFeatureFlags())`. Assert the list has one entry per field on `RuntimeFeatureFlags` (use `dataclasses.fields` to count). Each entry has `name` and `enabled` keys; `enabled` is a bool.
    7. **test_collect_feature_flag_states_reflects_enabled_flags:** Call with `RuntimeFeatureFlags(admin_api_enabled=True, wecom_channel_enabled=True)`. Assert the entries for `admin_api_enabled` and `wecom_channel_enabled` have `enabled=True`; others have `enabled=False`.
    8. **test_carried_human_gates_constant:** Assert `CARRIED_HUMAN_GATES` is a tuple of 3 dicts, each with `name`, `status="carried"`, `auto_closed=False`. Assert the names include "Phase 5 WeCom UAT", "Phase 8 lawyer trial", "QQ live acceptance".
    9. **test_handle_health_includes_carried_human_gates:** Call `handle_health(flags, None)`. Assert `carried_human_gates` is in the response and has 3 entries.
    10. **test_handle_health_includes_feature_flags:** Call `handle_health(flags, None)`. Assert `feature_flags` is in the response and is a list.
    11. **test_handle_health_includes_gate_pass_rate_with_summary:** Pass a `gate_summary` with 4 gates, 3 passed. Assert `gate_pass_rate == 0.75`.
    12. **test_handle_health_gate_pass_rate_null_without_summary:** Call without `gate_summary`. Assert `gate_pass_rate is None`.
    13. **test_handle_health_gate_pass_rate_null_with_empty_gates:** Pass `gate_summary={"passed": True, "gates": []}`. Assert `gate_pass_rate is None`.
    14. **test_health_allowed_fields_includes_new_fields:** Assert `HEALTH_ALLOWED_FIELDS` contains `services`, `gate_pass_rate`, `feature_flags`, `carried_human_gates`.
    15. **test_handle_health_response_subset_of_allowed_fields:** Call `handle_health(flags, None, process_supervisor=None)`. Assert `set(body.keys()).issubset(HEALTH_ALLOWED_FIELDS)`.
    16. **test_handle_health_excludes_secret_fields:** Call `handle_health(flags, None)`. Assert `secret_refs_configured` not in body, `api_base_url` not in body, `config_path` not in body.

    **GateTimeoutTests (add to existing test_health.py or test_gates.py):**
    17. **test_run_gate_summary_accepts_timeout_seconds:** Patch `subprocess.run` and call `run_gate_summary(timeout_seconds=30)`. Assert the `timeout` kwarg passed to `subprocess.run` is 30, not 300.
    18. **test_run_gate_summary_default_timeout_unchanged:** Call `run_gate_summary()` (no timeout). Assert the `timeout` kwarg is `GATE_TIMEOUT_SECONDS` (300).

    **GateHonestyTests:**
    19. **test_no_mark_human_gate_passed_in_health_source:** Read `health.py` source text. Assert `"mark_human_gate"` not in source, `"pass_human_gate"` not in source, `"close_human_gate"` not in source.

    Use `unittest.mock.patch` or simple stub classes for ProcessSupervisor. A minimal stub:
    ```python
    class _StubRecord:
        def __init__(self, name, status, host="127.0.0.1", port=8080):
            self.name = name
            self.status = status
            self.host = host
            self.port = port
            self.metadata = {}

    class _StubSupervisor:
        def __init__(self, records):
            self._records = records
        def status_all(self):
            return list(self._records)
    ```
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src python -m unittest services.admin_console_api.tests.test_health -v</automated>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src python -m unittest services.admin_console_api.tests.test_gates -v</automated>
    <manual>Confirm that handle_health returns a unified response with services, feature_flags, carried_human_gates, and gate_pass_rate fields, and that no secret-related fields leak through project_health.</manual>
  </verify>
</task>

<task type="auto">
  <name>Task 2: Enhanced health dashboard rendering in admin-web-ui</name>
  <files>
    services/admin-web-ui/src/admin_web_ui/dashboard.py
    services/admin-web-ui/tests/test_dashboard.py
  </files>
  <read_first>
    services/admin-web-ui/src/admin_web_ui/dashboard.py
    services/admin-web-ui/src/admin_web_ui/server.py
    services/admin-web-ui/src/admin_web_ui/api_client.py
    services/admin-console-api/src/admin_console_api/health.py
    services/admin-web-ui/tests/test_dashboard.py
  </read_first>
  <action>
    ### Modify `services/admin-web-ui/src/admin_web_ui/dashboard.py`

    1. Add a CSS class for the carried human gate visual state in the `<style>` block of `_page_template`:
       ```css
       .human-gate-carried {{ background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 0.5rem; color: #856404; font-weight: 600; }}
       .human-gate-label {{ font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #856404; }}
       .health-services-table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; margin-bottom: 1rem; }}
       .health-services-table th {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 2px solid #eee; font-weight: 600; font-size: 0.8125rem; color: #555; }}
       .health-services-table td {{ padding: 0.4rem 0.6rem; border-bottom: 1px solid #eee; }}
       .flags-table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
       .flags-table th {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 2px solid #eee; font-weight: 600; font-size: 0.8125rem; color: #555; }}
       .flags-table td {{ padding: 0.4rem 0.6rem; border-bottom: 1px solid #eee; }}
       .flag-on {{ color: #27ae60; font-weight: 600; }}
       .flag-off {{ color: #888; }}
       .gate-pass-rate {{ font-size: 1.5rem; font-weight: 700; margin: 0.5rem 0; }}
       .gate-pass-rate-ok {{ color: #27ae60; }}
       .gate-pass-rate-fail {{ color: #c0392b; }}
       .gate-pass-rate-na {{ color: #888; font-size: 1rem; font-weight: 400; }}
       .run-gates-link {{ display: inline-block; margin: 0.5rem 0; padding: 6px 12px; background: #1a1a2e; color: #fff; border-radius: 6px; text-decoration: none; font-size: 0.875rem; font-weight: 600; }}
       ```
       Place these after the existing `.probe-result` / `select` styles, before the closing `</style>`.

    2. Add a `_render_carried_human_gates_row` function after `_render_carried_human_gates_card`:
       ```python
       def _render_carried_human_gates_row(gate: dict[str, Any]) -> str:
           """Render a single carried human gate with a distinct non-green visual state."""
           name = _esc(gate.get("name", ""))
           return (
               f'    <div class="human-gate-carried" role="status" aria-label="Carried human gate">\n'
               f'      <span class="human-gate-label">HUMAN GATE — carried, not auto-closed</span><br>\n'
               f'      <span>{name}</span>\n'
               f'    </div>'
           )
       ```

    3. Replace the existing `_render_health_section` with an enhanced version that renders four sub-sections:
       ```python
       def _render_health_section(data: dict[str, Any], boundary: AdminUiBoundary) -> str:
           """Render the unified health monitoring section.

           Sub-sections:
           1. Gate honesty banner (always rendered first)
           2. Service Health table (admin API, WeCom host, QQBot host)
           3. Gate Pass Rate (percentage or 'Not run' with Run Gates link)
           4. Feature Flags table
           5. Carried Human Gates (distinct non-green visual state)
           """
           parts: list[str] = []
           parts.append(_render_gate_honesty_banner())

           # Service Health table
           services = data.get("services", [])
           if isinstance(services, list) and services:
               parts.append('    <h3>Service Health</h3>')
               parts.append('    <table class="health-services-table">')
               parts.append('      <thead><tr><th>Service</th><th>Status</th><th>OK</th><th>Host</th><th>Port</th></tr></thead>')
               parts.append('      <tbody>')
               for svc in services:
                   if isinstance(svc, dict):
                       name = _esc(svc.get("name", ""))
                       status = _esc(svc.get("status", ""))
                       ok = svc.get("ok", False)
                       ok_class = "status-ok" if ok else "status-err"
                       ok_text = "yes" if ok else "no"
                       host = _esc(svc.get("host") or "—")
                       port = _esc(svc.get("port") or "—")
                       parts.append(f'        <tr><td>{name}</td><td>{status}</td><td class="{ok_class}">{ok_text}</td><td>{host}</td><td>{port}</td></tr>')
               parts.append('      </tbody>')
               parts.append('    </table>')
           else:
               parts.append('    <h3>Service Health</h3>')
               parts.append('    <p class="empty">No service health data available.</p>')

           # Gate Pass Rate
           parts.append('    <h3>Gate Pass Rate</h3>')
           gate_pass_rate = data.get("gate_pass_rate")
           if gate_pass_rate is not None:
               pct = f"{gate_pass_rate * 100:.0f}%"
               rate_class = "gate-pass-rate-ok" if gate_pass_rate >= 1.0 else "gate-pass-rate-fail"
               parts.append(f'    <div class="gate-pass-rate {rate_class}">{_esc(pct)}</div>')
               gate_count = data.get("gate_count")
               gates_passed = data.get("gates_passed")
               gates_failed = data.get("gates_failed")
               if gate_count is not None:
                   parts.append(f'    <p>{_esc(gates_passed)} passed / {_esc(gate_count)} total ({_esc(gates_failed)} failed)</p>')
           else:
               parts.append('    <div class="gate-pass-rate gate-pass-rate-na">Not run</div>')
               parts.append('    <a href="/health?gates=true" class="run-gates-link">Run Gates</a>')

           # Feature Flags
           feature_flags = data.get("feature_flags", [])
           if isinstance(feature_flags, list) and feature_flags:
               parts.append('    <h3>Feature Flags</h3>')
               parts.append('    <table class="flags-table">')
               parts.append('      <thead><tr><th>Flag</th><th>Enabled</th></tr></thead>')
               parts.append('      <tbody>')
               for flag in feature_flags:
                   if isinstance(flag, dict):
                       fname = _esc(flag.get("name", ""))
                       enabled = flag.get("enabled", False)
                       flag_class = "flag-on" if enabled else "flag-off"
                       flag_text = "on" if enabled else "off"
                       parts.append(f'        <tr><td>{fname}</td><td class="{flag_class}">{flag_text}</td></tr>')
               parts.append('      </tbody>')
               parts.append('    </table>')
           else:
               parts.append('    <h3>Feature Flags</h3>')
               parts.append('    <p class="empty">No feature flag data available.</p>')

           # Carried Human Gates
           carried = data.get("carried_human_gates", [])
           if isinstance(carried, list) and carried:
               parts.append('    <h3>Carried Human Gates</h3>')
               for gate in carried:
                   if isinstance(gate, dict):
                       parts.append(_render_carried_human_gates_row(gate))
           else:
               parts.append('    <h3>Carried Human Gates</h3>')
               parts.append('    <p class="empty">No carried human gates data available.</p>')

           return "\n".join(parts)
       ```

    4. No changes needed to `render_dashboard` — the `health` section already dispatches to `_render_health_section`.

    5. No changes needed to `_page_template` nav_items — `/health` is already in the nav.

    6. No changes needed to `_render_index` — the Health section card already links to `/health`.

    ### Tests: `services/admin-web-ui/tests/test_dashboard.py`

    Add the following test methods to the existing `DashboardRenderingTests` class (or a new `UnifiedHealthDashboardTests` class):

    1. **test_render_health_unified_service_table:** Call `render_dashboard("health", {"services": [{"name": "admin-console-api", "status": "ok", "ok": True, "host": None, "port": None}, {"name": "wecom", "status": "running", "ok": True, "host": "127.0.0.1", "port": 8082}]}, identity=self.identity, boundary=self.boundary)`. Assert HTML contains "Service Health", `<table class="health-services-table">`, "admin-console-api", "wecom", "running", "yes".
    2. **test_render_health_service_ok_false:** Assert `status-err` class and "no" text when `ok=False`.
    3. **test_render_health_gate_pass_rate:** Call with `gate_pass_rate=0.75, gate_count=4, gates_passed=3, gates_failed=1`. Assert HTML contains "75%", "3 passed", "4 total", "1 failed".
    4. **test_render_health_gate_pass_rate_100:** Call with `gate_pass_rate=1.0`. Assert HTML contains "100%" and `gate-pass-rate-ok` class.
    5. **test_render_health_gate_pass_rate_null:** Call with `gate_pass_rate=None`. Assert HTML contains "Not run" and `run-gates-link` class and `href="/health?gates=true"`.
    6. **test_render_health_feature_flags_table:** Call with `feature_flags=[{"name": "admin_api_enabled", "enabled": True}, {"name": "wecom_channel_enabled", "enabled": False}]`. Assert HTML contains "Feature Flags", `<table class="flags-table">`, "admin_api_enabled", "wecom_channel_enabled", "flag-on", "flag-off".
    7. **test_render_health_carried_human_gates:** Call with `carried_human_gates=[{"name": "Phase 5 WeCom UAT", "status": "carried", "auto_closed": False}]`. Assert HTML contains "Carried Human Gates", "Phase 5 WeCom UAT", "HUMAN GATE — carried, not auto-closed", `human-gate-carried` class.
    8. **test_render_health_carried_human_gate_non_green:** Assert the `human-gate-carried` CSS class is present and `status-ok` class is NOT present in the carried human gates section. (Check that the human-gate row HTML does not contain `status-ok`.)
    9. **test_render_health_gate_honesty_banner_present:** Call `render_dashboard("health", {"services": []}, ...)`. Assert HTML contains "This console does not close live acceptance gates" and "not_live_acceptance".
    10. **test_render_health_no_mark_human_gate_control:** Read `dashboard.py` source text. Assert `"mark_human_gate"` not in source, `"pass_human_gate"` not in source, `"close_human_gate"` not in source, no `<form` tag contains "human_gate" in the health section.
    11. **test_render_health_html_escaped:** Call with a service name containing `<script>alert(1)</script>`. Assert HTML contains `&lt;script&gt;` not `<script>alert(1)</script>`.
    12. **test_render_health_empty_services:** Call with `services=[]`. Assert HTML contains "No service health data available."
    13. **test_render_health_empty_feature_flags:** Call with `feature_flags=[]`. Assert HTML contains "No feature flag data available."
    14. **test_render_health_no_innerhtml_or_dangerous_attributes:** Assert no `innerHTML`, `onclick`, `onerror`, `onload`, `javascript:` in the health HTML output.
    15. **test_render_health_run_gates_link:** Assert the "Run Gates" link uses `href="/health?gates=true"` when `gate_pass_rate` is None.
    16. **test_render_health_full_unified:** Call with all four sub-sections populated (services, gate_pass_rate, feature_flags, carried_human_gates). Assert all section headings are present: "Service Health", "Gate Pass Rate", "Feature Flags", "Carried Human Gates".
  </action>
  <verify>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.admin_web_ui.tests.test_dashboard -v</automated>
    <automated>PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.admin_web_ui.tests.test_main -v</automated>
    <manual>Confirm that the /health page renders with four sub-sections (Service Health, Gate Pass Rate, Feature Flags, Carried Human Gates), that carried human gates have a distinct amber/orange visual state, and that no 'mark human gate passed' button or form exists.</manual>
  </verify>
</task>

</tasks>

<post_conditions>
After both tasks are complete:

1. **All new tests pass:** `test_health.py` (admin-console-api) with unified health tests, `test_dashboard.py` (admin-web-ui) with enhanced health section tests.
2. **Existing tests still pass:** `test_gates.py`, `test_health_allowlist_integration.py`, `test_dashboard_audit.py`, `test_dashboard_logs.py`, `test_dashboard_reports.py`, `test_main.py` — no regressions from the `health.py` / `gates.py` / `api.py` / `dashboard.py` changes.
3. **RBAC CI scan passes:** `PYTHONPATH=packages/rbac/src:services/admin-console-api/src python3 scripts/scan_rbac_annotations.py` exits 0. No new route prefixes are added — `/health` is already in `ROUTE_PREFIXES` and `PERMISSIONS_MATRIX`.
4. **No new dependencies:** `dependencies = []` in all `pyproject.toml` files; no new third-party imports. `dataclasses.fields` is stdlib.
5. **Privacy:** `project_health` still excludes all secret-related fields via the positive allowlist. The new `services` list exposes only `name`, `status`, `ok`, `host`, `port` — never the raw `metadata.health` payload from child probes. Feature flags expose only boolean values.
6. **Gate honesty:** `CARRIED_HUMAN_GATES` is a static, read-only tuple. No API endpoint or UI control mutates it. No "mark human gate passed" control exists. A source-scan test asserts no `mark_human_gate` / `pass_human_gate` / `close_human_gate` strings in `health.py` or `dashboard.py`. Human-gate rows render with `human-gate-carried` CSS class (amber/orange), never `status-ok` (green).
7. **Gate pass rate is optional:** The `/health` endpoint includes `gate_pass_rate` only when `?gates=true` is passed (running `run_gate_summary` with a 30-second timeout). Without it, `gate_pass_rate` is `null` and the UI shows a "Run Gates" link. This prevents slow gate runs on every dashboard page load.
8. **CSP compliance:** The `/health` page uses only HTML-escaped content; no inline `<script>` tags; CSP header set on every response.
9. **Backward compatibility:** The existing `/health` response fields (`service`, `status`, `version`, `secrets_configured`, `uptime_seconds`, `gate_count`, `gates_passed`, `gates_failed`) are preserved. New fields are additive.
10. **`run_gate_summary` timeout parameter:** The default timeout remains 300s for the dedicated `/gates` endpoint. The `/health` endpoint uses 30s. Existing `test_gates.py` tests pass unchanged.
</post_conditions>
