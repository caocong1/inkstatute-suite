---
phase: 74-admin-config-api-rbac
plan: 02
subsystem: admin-api
tags: [admin-console-api, operator-config, config-api, rbac, ADM-01, ADM-03]

requires:
  - phase: 74-01
    provides: /config ROUTE_PREFIXES + PERMISSIONS_MATRIX ADMIN+OPERATOR, operator_config gate PYTHONPATH
  - phase: 73-operator-config-foundation
    provides: OperatorConfigStore, document_from_payload/document_to_payload, OperatorConfigDisabledError
provides:
  - config_api section GET/PUT over OperatorConfigStore
  - handle_admin_put exported; operational PUT → 405 method_not_allowed
  - OperatorConfigDisabledError → 403 operator_config_disabled via store.save
affects:
  - 74-03 (test_config_api, evolve test_read_only, RBAC integration)
  - 75+ channel/provider/vision apply consumers of /config HTTP surface

tech-stack:
  added: []
  patterns:
    - pure (status, body) config_api adapters; auth stays in api.handle_admin_*
    - section merge via document_to_payload → replace key → document_from_payload → store.save
    - shared _authenticate_admin pipeline for GET and PUT

key-files:
  created:
    - services/admin-console-api/src/admin_console_api/config_api.py
  modified:
    - services/admin-console-api/src/admin_console_api/api.py
    - services/admin-console-api/src/admin_console_api/__init__.py

key-decisions:
  - "Sections-only: bare /config and unknown sections → 404; no full-document GET"
  - "Providers PUT body prefers list (section value); optional {\"providers\": [...]} unwrap"
  - "Auth then method: unauthorized still 401 before operational 405"

patterns-established:
  - "Config mutate lives in config_api.py — views.py stays operational read-only"
  - "Error map: disabled→403 operator_config_disabled; validation→400 invalid_config; store→500 config_store_error"

requirements-completed: [ADM-01, ADM-03]

duration: 3min
completed: 2026-07-10
---

# Phase 74 Plan 02: Section GET/PUT config_api + handle_admin_put Summary

**Admin/operator can GET and PUT `/config/{channels,providers,catalog,vision}` through pure store-backed handlers; operational PUT returns 405 after auth; flag-OFF PUT maps to 403 `operator_config_disabled` without bypassing `OperatorConfigStore.save`.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-07-10T07:55:03Z
- **Completed:** 2026-07-10T07:58:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `config_api.py` with `CONFIG_SECTIONS`, `handle_config_get`, `handle_config_put` over Phase 73 store APIs
- Wired GET `/config/*` dispatch and new `handle_admin_put` (exported) with auth-then-405 for operational paths
- Prescribed error mapping: disabled / invalid_config / config_store_error; refs-only responses; no store path in bodies

## Task Commits

Each task was committed atomically:

1. **Task 1: Create config_api.py section GET/PUT handlers** — `cc1ba7c` (feat)
2. **Task 2: Wire handle_admin_get / handle_admin_put dispatch** — `cb943ac` (feat)

**Plan metadata:** `8d6893d` (docs: complete plan)

## Files Created/Modified

- `services/admin-console-api/src/admin_console_api/config_api.py` — section allowlist + GET/PUT + error mapping
- `services/admin-console-api/src/admin_console_api/api.py` — shared auth helper; GET config dispatch; `handle_admin_put`
- `services/admin-console-api/src/admin_console_api/__init__.py` — export `handle_admin_put`

## Decisions Made

- Sections-only surface (resolved OQ1): no full-document GET `/config`
- Providers body is the section list value (optional wrapped object accepted once)
- Extracted `_authenticate_admin` so GET/PUT share identical flag/auth/RBAC/tenant steps

## Deviations from Plan

None - plan executed exactly as written.

Note: `_authenticate_admin` helper is an internal DRY of the prescribed mirror pipeline, not a scope change.

## Issues Encountered

- Plan Task 1 verify PYTHONPATH omits conversation-read-view; package `__init__` imports `api` which needs it. Verified with the fuller Task 2 PYTHONPATH (same as Wave 2 smoke).
- `test_read_only.py` still asserts `handle_admin_put` must not exist — expected until Plan 74-03 evolves that suite. Not fixed here (out of 74-02 scope).

## User Setup Required

None.

## Threat Mitigations

| Threat ID | Disposition | Evidence |
|-----------|-------------|---------|
| T-74-03 | mitigate | `handle_admin_put` returns 405 `method_not_allowed` for non-`/config` after auth |
| T-74-04 | mitigate | PUT always calls `store.save`; maps `OperatorConfigDisabledError` → 403 |
| T-74-05 | mitigate | `document_to_payload` refs-only; no resolve; store messages strip path-like text |
| T-74-06 | mitigate | Section replace then full `document_from_payload` + `store.save` validation |
| T-74-SC | accept | No package installs |

## Known Stubs

None.

## Next Phase Readiness

Wave 2 handlers ready. Plan 74-03 should add `test_config_api.py`, evolve `test_read_only.py` (405 contract), extend RBAC integration, and document the mutate surface.

## Self-Check: PASSED

- Files: config_api.py, api.py, __init__.py, 74-02-SUMMARY.md — present
- Commits: cc1ba7c, cb943ac — present
