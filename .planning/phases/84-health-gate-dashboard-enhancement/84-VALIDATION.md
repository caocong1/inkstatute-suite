# Phase 84: Health & Gate Dashboard Enhancement — Validation Criteria

**Phase:** 84 — Health & Gate Dashboard Enhancement
**Requirements:** OBS-09, OBS-10
**Date:** 2026-07-14

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `unittest` (stdlib) |
| **Config file** | none — stdlib unittest |
| **Quick run command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest services.admin_console_api.tests.test_health services.admin_web_ui.tests.test_dashboard -v` |
| **Full suite command** | `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:packages/operator-config/src:packages/rbac/src:services/conversation-read-view/src:services/feedback-service/src:services/admin-console-api/src:services/admin-web-ui/src python -m unittest discover -s services/admin-console-api/tests services/admin-web-ui/tests -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command (2 updated test modules)
- **After every plan wave:** Run full suite command + RBAC CI scan
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## OBS-09: Unified health/gate/flag dashboard with service health, gate pass rate, feature flags, and carried human gate status

### Criterion 1: Service health from child `/health` endpoints

- [ ] `handle_health` returns a `services` list with entries for admin-console-api, WeCom host, and QQBot host.
- [ ] Each service entry has keys: `name`, `status`, `ok`, `host`, `port`.
- [ ] The admin-console-api entry uses the existing `collect_raw_health` / `project_health` primitives for its own status.
- [ ] WeCom and QQBot entries are derived from `process_supervisor.status_all()` with `ok = (status == "running")`.
- [ ] The raw `metadata.health` payload from child probes is NOT included in the service entry — only `name`, `status`, `ok`, `host`, `port` are exposed.
- [ ] When `process_supervisor` is None, WeCom and QQBot entries have `status="unknown"`, `ok=False`.
- [ ] The web page renders a Service Health table with columns: Service, Status, OK, Host, Port.

### Criterion 2: Gate pass rate

- [ ] `handle_health` returns `gate_pass_rate` as a float (0.0–1.0) when a `gate_summary` is provided.
- [ ] `gate_pass_rate` is `None` when no `gate_summary` is provided (default `/health` without `?gates=true`).
- [ ] `gate_pass_rate` is `None` when the gate summary has zero gates (avoid division by zero).
- [ ] `GET /health?gates=true` runs `run_gate_summary(timeout_seconds=30)` and includes the gate pass rate.
- [ ] `GET /health` (no query param) does NOT run gates — `gate_pass_rate` is `null`.
- [ ] The web page renders the gate pass rate as a percentage (e.g. "75%") when non-null.
- [ ] The web page renders "Not run" with a "Run Gates" link (`href="/health?gates=true"`) when `gate_pass_rate` is null.
- [ ] The gate pass rate percentage uses `gate-pass-rate-ok` CSS class (green) when 100%, `gate-pass-rate-fail` (red) when < 100%.

### Criterion 3: Feature flag states

- [ ] `handle_health` returns a `feature_flags` list with one entry per field on `RuntimeFeatureFlags`.
- [ ] Each feature flag entry has keys: `name` (the field name), `enabled` (bool).
- [ ] `collect_feature_flag_states` iterates via `dataclasses.fields(RuntimeFeatureFlags)` — no hardcoded flag list.
- [ ] A test with `RuntimeFeatureFlags(admin_api_enabled=True, wecom_channel_enabled=True)` asserts those two flags have `enabled=True` and others have `enabled=False`.
- [ ] The web page renders a Feature Flags table with columns: Flag, Enabled.
- [ ] Enabled flags show "on" with `flag-on` CSS class (green); disabled flags show "off" with `flag-off` CSS class (gray).

### Criterion 4: Carried human gate status

- [ ] `handle_health` returns a `carried_human_gates` list with 3 entries.
- [ ] `CARRIED_HUMAN_GATES` is a static tuple of dicts with `name`, `status="carried"`, `auto_closed=False`.
- [ ] The three carried human gates are: "Phase 5 WeCom UAT", "Phase 8 lawyer trial", "QQ live acceptance".
- [ ] The web page renders each carried human gate with `human-gate-carried` CSS class (amber/orange — distinct non-green visual state).
- [ ] Each carried human gate row includes the text "HUMAN GATE — carried, not auto-closed".
- [ ] The carried human gates section appears in the unified health view.

### Criterion 5: Unified view in one dashboard page

- [ ] The `/health` web page renders all four sub-sections in one page: Service Health, Gate Pass Rate, Feature Flags, Carried Human Gates.
- [ ] The gate-honesty banner is rendered at the top of the health section.
- [ ] The `/health` page title is "Health Monitoring" (unchanged from existing).
- [ ] The `/health` nav link is present in the page navigation (unchanged from existing).

---

## OBS-10: Gate honesty preservation

### Criterion 6: No "mark human gate passed" control

- [ ] No API endpoint accepts a mutation to `carried_human_gates` — the list is static and read-only.
- [ ] No "mark human gate passed" button, form, or link exists in the health or gates web pages.
- [ ] A source-scan test asserts `mark_human_gate`, `pass_human_gate`, `close_human_gate` strings do not appear in `health.py` or `dashboard.py`.
- [ ] `CARRIED_HUMAN_GATES` is a `tuple` (immutable) — no code path appends or mutates it.

### Criterion 7: Distinct non-green visual state for human gates

- [ ] Carried human gate rows use the `human-gate-carried` CSS class (amber/orange background `#fff3cd`, border `#ffc107`, text color `#856404`).
- [ ] Carried human gate rows do NOT use `status-ok` (green) CSS class.
- [ ] A test asserts that the human-gate row HTML does not contain `status-ok`.
- [ ] The `human-gate-label` text "HUMAN GATE — carried, not auto-closed" is rendered in uppercase with distinct styling.

### Criterion 8: Automated gate results never claim live acceptance

- [ ] The gate-honesty banner is present on the `/health` page: "This console does not close live acceptance gates".
- [ ] The banner includes `not_live_acceptance` text and `role="note"` aria attribute.
- [ ] The gate pass rate is labeled as automated gate results — it does not claim Phase 5, Phase 8, or QQ live acceptance.
- [ ] Forbidden phrases absent from `dashboard.py` source: "lawyer trial acceptance complete", "live wecom uat passed", "live qq openapi acceptance", "live provider reachability" (existing test continues to pass).

---

## Privacy and Allowlist Validation

### Criterion 9: Positive field allowlist extended

- [ ] `HEALTH_ALLOWED_FIELDS` includes the new fields: `services`, `gate_pass_rate`, `feature_flags`, `carried_human_gates`.
- [ ] `HEALTH_ALLOWED_FIELDS` retains the existing fields: `service`, `status`, `version`, `secrets_configured`, `uptime_seconds`, `gate_count`, `gates_passed`, `gates_failed`.
- [ ] `project_health` retains the new fields (they pass through the allowlist).
- [ ] `handle_health` response keys are a subset of `HEALTH_ALLOWED_FIELDS`.

### Criterion 10: Secret fields excluded

- [ ] `project_health` still excludes `secret_refs_configured`, `api_base_url`, `config_path`, `config_file`, `secret_ref_names`, `wecom_token_ref`, `aes_key_ref`, `callback_token_ref`, `encoding_aes_key_ref`.
- [ ] The `services` list does not include `metadata` or `health` keys from child probes.
- [ ] The `feature_flags` list exposes only boolean values — no secret strings, no config paths.
- [ ] A test verifies `secret_refs_configured` is not in the `handle_health` response.
- [ ] A test verifies `api_base_url` is not in the `handle_health` response.

---

## Gate Subprocess Timeout Validation

### Criterion 11: Configurable timeout

- [ ] `run_gate_summary` accepts a `timeout_seconds` keyword parameter (default `GATE_TIMEOUT_SECONDS=300`).
- [ ] `run_gate_summary(timeout_seconds=30)` passes `timeout=30` to `subprocess.run`.
- [ ] `run_gate_summary()` (no argument) passes `timeout=300` to `subprocess.run` (backward compatible).
- [ ] The `/health?gates=true` endpoint uses `timeout_seconds=30` (not 300).
- [ ] The `/gates` endpoint continues to use the default 300-second timeout.
- [ ] On timeout, `run_gate_summary` returns `{"passed": False, "gates": [], "error": "timeout"}` and `gate_pass_rate` is `None` (zero gates).

---

## RBAC and Feature Flag Validation

### Criterion 12: RBAC unchanged

- [ ] `/health` is already in `ROUTE_PREFIXES` — no new route prefix added.
- [ ] `/health` is already in `PERMISSIONS_MATRIX` with `frozenset({Role.ADMIN, Role.OPERATOR})` — no matrix change.
- [ ] The RBAC CI scan (`scripts/scan_rbac_annotations.py`) passes with exit code 0 (no route changes).
- [ ] ADMIN role token → 200 on `GET /health`.
- [ ] OPERATOR role token → 200 on `GET /health`.
- [ ] LAWYER role token → 403 on `GET /health`.
- [ ] `admin_api_enabled=False` → 403 on `GET /health` (existing behavior unchanged).

---

## Web UI Validation

### Criterion 13: SSR with html.escape

- [ ] All dynamic content in the `/health` HTML page is HTML-escaped via `html.escape()` or the local `_esc()` helper.
- [ ] A test with `<script>alert(1)</script>` in a service name asserts the HTML contains `&lt;script&gt;` not `<script>`.
- [ ] The CSP header on `/health` responses is `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'`.
- [ ] No inline `<script>` tags are present in the `/health` HTML output.
- [ ] No `innerHTML`, `onclick`, `onerror`, `onload`, or `javascript:` in the health HTML output.

### Criterion 14: Empty state handling

- [ ] When `services` is an empty list, the page renders "No service health data available."
- [ ] When `feature_flags` is an empty list, the page renders "No feature flag data available."
- [ ] When `carried_human_gates` is an empty list, the page renders "No carried human gates data available."
- [ ] When `gate_pass_rate` is `None`, the page renders "Not run" with a Run Gates link.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 84-01-01 | 01 | 1 | OBS-09 | T-84-01 | Service health from child probes excludes raw metadata; feature flags expose only booleans | unit | `python -m unittest services.admin_console_api.tests.test_health -v` | ✅ exists | ⬜ pending |
| 84-02-01 | 01 | 1 | OBS-10 | T-84-02 | Carried human gates render with non-green visual state; no mark-passed control; source scan clean | unit | `python -m unittest services.admin_web_ui.tests.test_dashboard -v` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `services/admin-console-api/tests/test_health.py` — existing file, extended with unified health tests
- [ ] `services/admin-web-ui/tests/test_dashboard.py` — existing file, extended with enhanced health section tests

*Existing unittest infrastructure covers all phase requirements — no new test files needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual inspection of amber/orange human-gate styling | OBS-10 | Requires browser rendering | Open `/health` in browser, confirm carried human gates have amber/orange background, not green |
| Run Gates link triggers gate subprocess | OBS-09 | Requires running server + gate subprocess | Click "Run Gates" link on `/health`, confirm page reloads with gate pass rate percentage |
| CSP header inspection in browser | OBS-10 | Requires browser DevTools | Open DevTools Network tab, load `/health`, confirm CSP header is present and no inline script violations |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
