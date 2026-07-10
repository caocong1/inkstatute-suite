---
phase: 75-channel-config-apply
plan: 05
subsystem: ui
tags: [admin-web-ui, ssr, channels, dual-knob, csrf-deferred, secret-refs]

requires:
  - phase: 75-channel-config-apply
    provides: "GET/PUT /config/channels with additive effective dual-knob block"
  - phase: 74-admin-config-api-rbac
    provides: "handle_admin_put + /config RBAC ADMIN+OPERATOR"
provides:
  - "SSR GET/POST /config/channels Channel Config form per UI-SPEC"
  - "AdminApiClient.proxy_put → handle_admin_put"
  - "Dual-knob visibility + refs-only fields + restart-to-apply honesty"
affects:
  - 78-console-ssr-docs-gate-honesty

tech-stack:
  added: []
  patterns:
    - "stdlib SSR form POST → parse_channels_form → proxy_put(handle_admin_put)"
    - "Platform knobs read-only; host checkbox editable; effective derived"
    - "CSRF hidden field present; full CSRF audit deferred to Phase 78"

key-files:
  created:
    - services/admin-web-ui/src/admin_web_ui/channels.py
  modified:
    - services/admin-web-ui/src/admin_web_ui/api_client.py
    - services/admin-web-ui/src/admin_web_ui/dashboard.py
    - services/admin-web-ui/src/admin_web_ui/server.py
    - services/admin-web-ui/tests/test_channels_form.py
    - services/admin-web-ui/README.md

key-decisions:
  - "Dedicated channels.py module (render + parse) rather than only dashboard section renderer"
  - "WeCom platform label uses wecom_channel_enabled (never channel_delivery_enabled)"
  - "Minimal csrf_token field included; Phase 78 owns complete CSRF surface verification"
  - "POST only on /config/channels; operational routes stay GET-only (405 otherwise)"

patterns-established:
  - "Channel Config SSR: dual-knob matrix + refs-only text inputs + restart flash"
  - "AdminApiClient.proxy_put mirrors GET Authorization injection for handle_admin_put"

requirements-completed: [CHAN-01, CHAN-02, CHAN-03, CHAN-04]

duration: 5min
completed: 2026-07-10
---

# Phase 75 Plan 05: Channel Config SSR Form Summary

**Incremental admin-web-ui `/config/channels` SSR form with dual-knob QQ/WeCom panels, secret-ref fields, and POST→`handle_admin_put` proxy (restart-to-apply; CSRF audit deferred to Phase 78)**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-10T08:29:06Z
- **Completed:** 2026-07-10T08:33:25Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Shipped Channel Config SSR page showing platform (read-only), host (editable), and effective lines for QQ and WeCom — no bypass toggle
- POST `/config/channels` parses form into Phase 74 section body and proxies `handle_admin_put`; success flash requires host restart
- Credential inputs are `type=text` secret-ref fields with `html.escape`; lawyer/viewer denied via RBAC `/config`

## Task Commits

Each task was committed atomically:

1. **Task 1: channels.py form render/parse + api_client.proxy_put** - `a47f9b2` (feat)
2. **Task 2: Wire GET/POST /config/channels + green form tests + README honesty** - `d6e09ce` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `services/admin-web-ui/src/admin_web_ui/channels.py` — render/parse helpers per UI-SPEC
- `services/admin-web-ui/src/admin_web_ui/api_client.py` — `proxy_put` + optional `config_store` on GET proxy
- `services/admin-web-ui/src/admin_web_ui/dashboard.py` — Channel Config nav + index card + form CSS
- `services/admin-web-ui/src/admin_web_ui/server.py` — GET/POST `/config/channels` wiring
- `services/admin-web-ui/tests/test_channels_form.py` — dual-knob + POST proxy + RBAC proofs
- `services/admin-web-ui/README.md` — incremental form, restart-to-apply, CSRF Phase 78 deferral

## Decisions Made

- Dedicated `channels.py` module keeps form copy/parse isolated from operational dashboard renderers
- WeCom platform knob label is `wecom_channel_enabled` (never `channel_delivery_enabled`)
- Include minimal `csrf_token` hidden field now; document that Phase 78 owns full CSRF verification
- Guard path for channels is `/config` so ADMIN+OPERATOR pass and lawyer/viewer get 403

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Pass `config_store` through GET proxy and UI handler**
- **Found during:** Task 1–2 (channels GET needs store for real `handle_admin_get`)
- **Issue:** Plan listed `proxy_put` kwargs with `config_store`, but GET proxy also needed store injection for `/config/channels` round-trips
- **Fix:** Extended `AdminApiClient.proxy` and `handle_admin_web_ui_request` with optional `config_store`
- **Files modified:** `api_client.py`, `server.py`
- **Verification:** Integration temp-store round-trip in `test_channels_form`
- **Committed in:** `a47f9b2` / `d6e09ce`

**Total deviations:** 1 auto-fixed (Rule 2)
**Impact on plan:** Necessary for correct config GET/POST against a temp store; no scope creep.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 75 plans 01–05 complete — ready for phase verification
- Phase 78 should audit CSRF across the full SSR mutate surface and keep gate-honesty docs
- Carried human gates (Phase 5 / 8 / QQ `--live`) remain open — saving config does not close them

## Known Stubs

None — form is wired to real `handle_admin_get` / `handle_admin_put` with dual-knob display from API `effective`.

## TDD Gate Compliance

Wave 0 Plan 01 already committed RED scaffold tests; this plan greened them (feat commits `a47f9b2`, `d6e09ce`) without a new RED commit in 75-05.

## Self-Check: PASSED

- Created/modified files present: channels.py, server.py, api_client.py, test_channels_form.py, SUMMARY
- Commits present: `a47f9b2`, `d6e09ce`
- Key strings present: `proxy_put`, `/config/channels`, `wecom_channel_enabled`, `Save channel config`

---
*Phase: 75-channel-config-apply*
*Completed: 2026-07-10*
