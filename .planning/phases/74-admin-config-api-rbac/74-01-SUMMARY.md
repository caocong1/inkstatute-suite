---
phase: 74-admin-config-api-rbac
plan: 01
subsystem: admin-api
tags: [rbac, operator-config, feature-flags, v2-gates, admin-console-api]

requires:
  - phase: 73-operator-config-foundation
    provides: operator_config_enabled flag, packages/operator-config, operator_config_src path var
provides:
  - operator_config_enabled in admin contract-freeze expected flag set
  - /config ADMIN+OPERATOR entry in PERMISSIONS_MATRIX
  - /config in ROUTE_PREFIXES (six prefixes)
  - operator_config_src on admin-console-api, admin-web-ui, rbac, rbac-annotation-scan gate PYTHONPATHs
affects:
  - 74-02 (config HTTP handlers importing inkstatute_operator_config)
  - 74-03 (RBAC enforcement on /config routes)

tech-stack:
  added: []
  patterns:
    - empty-deps + PYTHONPATH composition for operator-config (no pyproject dep)
    - ROUTE_PREFIXES ↔ PERMISSIONS_MATRIX parity via scan_rbac_annotations

key-files:
  created: []
  modified:
    - services/admin-console-api/tests/test_contract_freeze.py
    - scripts/run_v2_gates.py
    - packages/rbac/src/rbac/matrix.py
    - packages/rbac/tests/test_matrix.py
    - services/admin-console-api/src/admin_console_api/routes.py
    - services/admin-console-api/tests/test_routes.py

key-decisions:
  - "/config matrix roles are exactly {ADMIN, OPERATOR}; LAWYER/VIEWER denied at path level"
  - "operator_config_src added to all gates that already compose admin_api_src (not lawyer-web-chat)"
  - "Freeze allowlist keeps exact-set equality; operator_config_enabled added as v1.10 flag"

patterns-established:
  - "Wave 0 unblock: freeze allowlist + gate PYTHONPATH before handlers that import operator-config"
  - "ROUTE_PREFIXES docstring covers GET and PUT dispatch (not GET-only)"

requirements-completed: [ADM-01, ADM-03]

duration: 2min
completed: 2026-07-10
---

# Phase 74 Plan 01: Wave 0 Freeze + /config RBAC Summary

**Admin contract freeze unblocked for `operator_config_enabled`, `/config` registered as ADMIN+OPERATOR in matrix and route table, and operator-config on admin-related V2 gate PYTHONPATHs.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-10T07:50:16Z
- **Completed:** 2026-07-10T07:53:02Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Restored exact-set feature-flag freeze with `operator_config_enabled` (Phase 73 flag no longer fails admin contract freeze)
- Wired `operator_config_src` into admin-console-api, admin-web-ui, rbac, and rbac-annotation-scan gate PYTHONPATHs (count ≥ 5)
- Registered `/config` as ADMIN+OPERATOR only in `PERMISSIONS_MATRIX` and as the sixth `ROUTE_PREFIXES` entry; RBAC annotation scan green

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 — freeze allowlist + operator-config gate PYTHONPATH**
   - `cf54774` test(74-01): add failing gate PYTHONPATH assertion for operator_config
   - `d2b6cff` feat(74-01): unblock freeze allowlist and operator-config gate PYTHONPATH
2. **Task 2: Register /config in ROUTE_PREFIXES + PERMISSIONS_MATRIX**
   - `506df56` test(74-01): add failing /config RBAC matrix and route tests
   - `e091dc3` feat(74-01): register /config in RBAC matrix and ROUTE_PREFIXES

**Plan metadata:** (docs commit after SUMMARY)

_Note: TDD tasks used RED → GREEN commits per task._

## Files Created/Modified

- `services/admin-console-api/tests/test_contract_freeze.py` — freeze allowlist + PYTHONPATH count assertion
- `scripts/run_v2_gates.py` — operator_config_src on four admin-importing gates
- `packages/rbac/src/rbac/matrix.py` — `/config` → ADMIN+OPERATOR
- `packages/rbac/tests/test_matrix.py` — ADMIN_API_ROUTE_PREFIXES + test_config_admin_operator
- `services/admin-console-api/src/admin_console_api/routes.py` — `/config` in ROUTE_PREFIXES; GET+PUT docstring
- `services/admin-console-api/tests/test_routes.py` — six-prefix expectations

## Decisions Made

- `/config` roles exactly `{ADMIN, OPERATOR}` — LAWYER/VIEWER denied at matrix path level (ADM-01)
- No new pip/pyproject dependency; empty-deps + PYTHONPATH composition retained
- lawyer-web-chat gate left without operator_config_src (does not compose admin_api_src)

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

- Task 1: RED `cf54774` → GREEN `d2b6cff`
- Task 2: RED `506df56` → GREEN `e091dc3`

## Verification Results

- `test_contract_freeze` — OK (7 tests)
- `test_matrix` + `test_routes` — OK (11 tests)
- `scan_rbac_annotations.py` — OK: all 6 admin API endpoints have RBAC annotations
- `operator_config_src` count in `run_v2_gates.py` — 6 (≥ 5)

## Threat Mitigations

| Threat ID | Disposition | Evidence |
|-----------|-------------|---------|
| T-74-01 | mitigate | `test_config_admin_operator` asserts ADMIN+OPERATOR and not LAWYER/VIEWER |
| T-74-02 | mitigate | `scan_rbac_annotations.py` green with 6 prefixes |
| T-74-SC | accept | No package installs |

## Known Stubs

None.

## Next Phase Readiness

Wave 0 complete. Plan 74-02 can implement `/config` HTTP handlers importing `inkstatute_operator_config` under the updated gate PYTHONPATHs; Plan 74-03 can enforce RBAC on those routes.

## Self-Check: PASSED

- Files: test_contract_freeze.py, run_v2_gates.py, matrix.py, test_matrix.py, routes.py, test_routes.py, 74-01-SUMMARY.md — all present
- Commits: cf54774, d2b6cff, 506df56, e091dc3 — all present
