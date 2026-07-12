---
phase: 77-vision-routing-runtime
plan: 04
subsystem: ui
tags: [python, stdlib, html, csrf, ssr, admin-web-ui]

requires:
  - phase: 77-vision-routing-runtime
    provides: "Plan 77-02 API metadata (routing_modes, vision_status, provider list, catalog entries) consumed by the SSR form"
  - phase: 76-provider-registry-model-catalog
    provides: "Signed CSRF helpers (csrf.py), provider/catalog render patterns, and /config/providers/probe infrastructure"

provides:
  - "Vision Config SSR form module (vision.py) with render/parse helpers and exact UI-SPEC copy"
  - "Route-bound CSRF enforcement on GET/POST /config/vision and POST /config/providers/probe (return_to=vision)"
  - "Server dispatch (server.py) and nav link (dashboard.py) for /config/vision"
  - "Green UI tests covering routing-mode select, provider/model filtering, main_only disabled state, CSRF, probe re-render, escaping, and no-secret boundaries"

affects:
  - "Phase 77 runtime (vision_router.py) - policy shape finalized"
  - "Phase 78 - complete SSR surface audit"

tech-stack:
  added: []
  patterns:
    - "Metadata-driven stdlib SSR with html.escape for all dynamic content"
    - "Separate route-bound CSRF tokens for save (/config/vision) and probe (/config/providers/probe)"
    - "Non-nested sibling forms for save and probe actions"

key-files:
  created:
    - services/admin-web-ui/src/admin_web_ui/vision.py
    - services/admin-web-ui/tests/test_vision_form.py
  modified:
    - services/admin-web-ui/src/admin_web_ui/server.py
    - services/admin-web-ui/src/admin_web_ui/dashboard.py

key-decisions:
  - "Vision save POST validates a CSRF token bound to /config/vision before any API proxy call"
  - "Vision probe POST reuses /config/providers/probe with a hidden return_to=vision field to re-render the vision page"
  - "Model select is filtered server-side by the selected provider's kind -> built-in catalog vendor_id; custom providers show a blank-only model select with a note"
  - "main_model_id is rendered as a hidden input echoed from the stored catalog selection"

patterns-established:
  - "Vision Config page: single-purpose stdlib SSR page with two cards and separate save/probe forms"
  - "Refs-only UI: no resolved secrets, api_key_ref, base URLs, store paths, or raw image bytes rendered"

requirements-completed:
  - VIS-01

duration: 18min
completed: 2026-07-11
---

# Phase 77-04: Vision Config SSR Summary

**Vision Config SSR page with routing-mode selector, provider/model selects, route-bound CSRF, and probe re-render, consuming Phase 77-02 API metadata.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-07-11T04:20:00Z
- **Completed:** 2026-07-11T04:38:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Implemented `vision.py` with `render_vision_page`, `render_vision_form`, and `parse_vision_form` using exact UI-SPEC copy constants.
- Wired `GET /config/vision` and `POST /config/vision` in `server.py` with CSRF-before-proxy ordering.
- Extended `POST /config/providers/probe` to support `return_to=vision` and re-render the Vision Config page.
- Added the "Vision Config" nav link to `_page_template` in `dashboard.py`.
- Wrote `test_vision_form.py` (TDD) covering defaults, `main_only` disabled state, provider/model filtering, custom-provider note, CSRF, RBAC, probe re-render, escaping, and no-secret boundaries.

## Task Commits

1. **Task 1: Implement Vision Config SSR render and parse helpers** - `TBD` (feat + test)
2. **Task 2: Wire vision route dispatch, CSRF, and nav link** - `TBD` (feat + test)

## Files Created/Modified

- `services/admin-web-ui/src/admin_web_ui/vision.py` - Vision Config SSR render/parse helpers, UI-SPEC copy constants, no secrets.
- `services/admin-web-ui/tests/test_vision_form.py` - 28 UI/route tests for the Vision Config SSR surface.
- `services/admin-web-ui/src/admin_web_ui/server.py` - `/config/vision` route dispatch, CSRF validation, probe `return_to` re-render.
- `services/admin-web-ui/src/admin_web_ui/dashboard.py` - Added "Vision Config" nav link after "Model Catalog".

## Decisions Made

- Followed the existing `catalog.py` / `providers.py` stdlib SSR pattern.
- Kept save and probe forms as non-nested sibling forms.
- Used `html.escape(..., quote=False)` for the custom-provider note so the UI-SPEC apostrophe is preserved in text content.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

- Test fixtures initially omitted `providers`/`catalog_entries` in direct-render tests; added to fixtures so provider/model filtering tests have data.
- `CUSTOM_PROVIDER_NOTE` apostrophe was being escaped by `html.escape` with `quote=True`; switched the note span to `quote=False` to preserve the UI-SPEC copy in page text.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Vision Config UI is complete and tested.
- Phase 77 runtime (`vision_router.py`) and Phase 78 SSR surface audit can proceed.

---
*Phase: 77-vision-routing-runtime*
*Completed: 2026-07-11*
