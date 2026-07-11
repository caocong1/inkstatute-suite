---
phase: 78-console-ssr-docs-gate-honesty
status: auto-gathered
generated: 2026-07-11
source: autonomous context gathering (skip_discuss=true) + 78-UI-SPEC.md
---

# Phase 78 Context: Console SSR, Docs & Gate Honesty

## Goal

Operators have complete CSRF-protected SSR config pages and honest docs/smoke evidence that never auto-claims carried live acceptance gates.

## Requirements

- **ADM-02**: Admin Web UI exposes config pages (channels, providers/catalog, vision) as SSR forms with CSRF protection, extending the existing stdlib `admin-web-ui` (not a new SPA stack).
- **DOC-01**: Operator docs (README / `.env.example` / runbook) document console fields ↔ env/ref keys, dual-knob, vision policy, and “do not edit Hermes for InkStatute providers”.
- **DOC-02**: Config/smoke evidence never auto-claims Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ `--live` acceptance (`not_live_acceptance` honesty preserved).

## Success Criteria (from ROADMAP.md)

1. Admin Web UI exposes config pages for channels, providers/catalog, and vision as SSR forms with CSRF protection, extending the existing stdlib `admin-web-ui` (not a new SPA stack).
2. Operator docs (README / `.env.example` / runbook) document console fields ↔ env/ref keys, dual-knob, vision policy, and “do not edit Hermes for InkStatute providers”.
3. Config/smoke evidence never auto-claims Phase 5 WeCom UAT, Phase 8 lawyer trial, or QQ `--live` acceptance (`not_live_acceptance` honesty preserved).

## Implementation Decisions

### UI/UX (locked via 78-UI-SPEC.md)

- **D-01:** Extend `services/admin-web-ui` stdlib `http.server` + escaped HTML + CSP. Do **not** introduce React, Vite, Next, or shadcn.
- **D-02:** Preserve the existing InkStatute Admin palette (60/30/10), four typography sizes, and spacing scale inherited from Phases 75–77. Apply Phase 78 chrome fixes: `.header h1` = 1.25rem/600, `.section h2`/card `h3` = 1.125rem/600/1.2, `.identity` = 0.875rem/600, `.nav-link` = 0.875rem/600, `.data-table` = 0.875rem.
- **D-03:** Use exact UI-SPEC copy for CTAs, empty states, errors, and gate-honesty notices. Primary CTAs: “Save channel config”, “Save provider config”, “Save catalog selection”, “Save vision config”. Probe CTAs: “Probe connection” / “Probe vision connection”.
- **D-04:** Gate-honesty banner appears on every config page (`/config/*`), the dashboard index (`/`), and the Gate Status page (`/gates`). Heading: “This console does not close live acceptance gates”. Body: exact UI-SPEC text with `not_live_acceptance` in monospace.
- **D-05:** Gate Status page (`/gates`) adds a “Carried human gates” card after the automated gate list with the same honesty text.
- **D-06:** Dashboard index (`/`) adds config section cards (Channel Config, Provider Config, Model Catalog, Vision Config) and a gate-honesty card.

### CSRF (locked via 78-UI-SPEC.md)

- **D-07:** All mutating config routes (`/config/channels`, `/config/providers`, `/config/catalog`, `/config/vision`, `/config/providers/probe`) use the same signed CSRF pattern as Phases 76/77.
- **D-08:** GET handlers issue a route-bound token with `issue_csrf_token(identity, route, signing_key=rbac_secret)`. The token is rendered as `<input type="hidden" name="csrf_token" value="...">` inside the relevant form.
- **D-09:** POST handlers parse the form and call `validate_csrf_token(token, identity, route, signing_key=rbac_secret)` before proxying. On missing/malformed/mismatched token, return 403 and render the exact error copy: “Request could not be verified. Refresh the page and try again.”
- **D-10:** The `/config/channels` route is upgraded from the Phase 75 placeholder random token to the signed, route-bound token pattern.
- **D-11:** Probe tokens are bound to `/config/providers/probe`, not to the save route. No token is reused across routes.
- **D-12:** CSRF token is never logged, echoed, or rendered outside the hidden input.

### Security & refs-only (locked)

- **D-13:** Preserve `packages/operator-config` refs-only policy: no raw secrets in form bodies or responses. Never render resolved secrets, `.env` contents, store paths, probe response bodies, `Authorization` headers, or `api_key_ref` values.
- **D-14:** CSP stays strict (`default-src 'self'; script-src 'self'; style-src 'self'`); no inline scripts; no `innerHTML` of untrusted data — all dynamic strings through `html.escape`.
- **D-15:** Output boundary (`AdminUiBoundary`) applies to any free-text API messages before render.

### Docs (locked via DOC-01 / 78-UI-SPEC.md)

- **D-16:** Update `README.md` to describe the Operator Config Console and link to the operator config runbook.
- **D-17:** Update `.env.example` to document console fields ↔ env/ref keys for QQ, WeCom, provider, vision, and feature flags.
- **D-18:** Add/update `runbook/OPERATOR_CONFIG_RUNBOOK.md` covering console fields, dual-knob, vision policy, and “do not edit Hermes for InkStatute providers”.
- **D-19:** Update `services/admin-web-ui/README.md` to reflect all config pages and CSRF/gate-honesty coverage.

### Gate honesty (locked via DOC-02 / 78-UI-SPEC.md)

- **D-20:** Forbidden text in any config response, smoke output, or documentation: “lawyer trial acceptance complete”, “live wecom uat passed”, “live qq openapi acceptance”, “live provider reachability”.
- **D-21:** Smoke evidence and probe results remain `not_live_acceptance`; do not auto-close Phase 5, Phase 8, or QQ live gates.

### Claude's Discretion

- Exact CSS implementation of the gate-honesty banner (`.notice-honesty`) and dashboard index cards.
- Whether to create a new `gate_honesty.py` helper module or keep the banner renderer in `dashboard.py`.
- Specific test file names and coverage depth beyond the existing `test_dashboard.py`, `test_channels_form.py`, `test_providers_form.py`, `test_catalog_form.py`, `test_vision_form.py`, and `test_server.py`.
- Minor README wording and runbook structure, as long as the required concepts are documented.

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase-specific specs

- `.planning/phases/78-console-ssr-docs-gate-honesty/78-UI-SPEC.md` — Visual, interaction, CSRF, and gate-honesty contract.
- `.planning/REQUIREMENTS.md` — ADM-02, DOC-01, DOC-02.
- `.planning/ROADMAP.md` — Phase 78 goal, success criteria, dependency on Phases 73–77.

### Existing admin-web-ui contracts

- `services/admin-web-ui/src/admin_web_ui/server.py` — Request dispatch for `/config/*` and CSRF enforcement.
- `services/admin-web-ui/src/admin_web_ui/dashboard.py` — `_page_template`, `_render_index`, `_render_gates_section`.
- `services/admin-web-ui/src/admin_web_ui/csrf.py` — `issue_csrf_token` / `validate_csrf_token`.
- `services/admin-web-ui/src/admin_web_ui/channels.py` — Channel Config SSR form (uses random token; Phase 78 upgrades to signed).
- `services/admin-web-ui/src/admin_web_ui/providers.py` — Provider Config SSR form with signed CSRF.
- `services/admin-web-ui/src/admin_web_ui/catalog.py` — Model Catalog SSR form with signed CSRF.
- `services/admin-web-ui/src/admin_web_ui/vision.py` — Vision Config SSR form with signed CSRF.
- `services/admin-web-ui/src/admin_web_ui/boundary.py` — `AdminUiBoundary` for output filtering.
- `services/admin-web-ui/src/admin_web_ui/api_client.py` — `AdminApiClient` proxy.

### Admin API / backend

- `services/admin-console-api/src/admin_console_api/api.py` — `handle_admin_get` / `handle_admin_put`.
- `services/admin-console-api/src/admin_console_api/config_api.py` — Config section GET/PUT.
- `services/admin-console-api/src/admin_console_api/probe.py` — `handle_config_probe`.
- `services/admin-console-api/src/admin_console_api/gates.py` — Gate status response.

### Existing docs

- `README.md` — Project-level overview.
- `.env.example` — Env/ref key example.
- `runbook/SMOKE_TEST_RUNBOOK.md` — QQ smoke gate-honesty precedent.
- `services/admin-web-ui/README.md` — Admin Web UI docs.

## Existing Code Insights

### Reusable Assets

- `dashboard._page_template` — full page chrome with header, nav, identity bar, main section.
- `csrf.issue_csrf_token` / `validate_csrf_token` — signed, route- and identity-bound tokens already used by providers, catalog, and vision.
- `_render_kv_table`, `_esc`, `_esc_dict` — existing HTML escape helpers in `dashboard.py`.
- `channels.py`, `providers.py`, `catalog.py`, `vision.py` — existing config form render/parse modules.
- `AdminApiClient.proxy_put` — already proxies config PUT to `admin_console_api`.

### Established Patterns

- `html.escape(str(value), quote=True)` on all dynamic strings.
- POST handler pattern: validate CSRF → parse form → call `client.proxy_put` → re-render with flash or error.
- Error mapping: `forbidden` → permission error, `operator_config_disabled` → flag-off error, `invalid_config` → validation error, else generic.
- Config pages use `operator_config_enabled` metadata to disable submit buttons.
- Probe results display generic status (`ok` / `not_configured` / `fail`) and never expose secrets or bodies.

### Integration Points

- `admin-web-ui` → `admin-console-api` via `AdminApiClient` and `handle_admin_web_ui_request`.
- `admin_console_api` → `OperatorConfigStore` for config persistence.
- `admin_console_api` → `scripts/run_v2_gates.py` for `/gates`.
- `admin-web-ui` → `rbac` package for identity and role checks.

## Deferred Ideas

- Hot-reload without runtime restart (CFG-F01).
- Per-lawyer self-serve model switching (PROV-F03).
- New React/Next/Vite/SPA UI stack (out of scope forever).
- Auto-close carried human gates (Phase 5 / Phase 8 / QQ live) — never.

---

*Phase: 78-console-ssr-docs-gate-honesty*
*Context gathered: 2026-07-11*
