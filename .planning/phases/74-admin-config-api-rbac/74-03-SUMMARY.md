---
phase: 74-admin-config-api-rbac
plan: 03
subsystem: testing
tags: [admin-console-api, operator-config, rbac, ADM-01, ADM-03, config-api, read-only]

requires:
  - phase: 74-02
    provides: handle_admin_put, config_api GET/PUT, operator_config_disabled mapping
  - phase: 74-01
    provides: /config ROUTE_PREFIXES + PERMISSIONS_MATRIX ADMIN+OPERATOR
provides:
  - test_config_api ADM-01/SC#4/secret no-echo proofs
  - evolved test_read_only 405 operational PUT contract
  - RBAC integration /config allow+deny matrix
  - README documenting config mutate surface
affects:
  - 75+ channel/provider/vision apply consumers
  - phase verifier for 74 ADM-01/ADM-03

tech-stack:
  added: []
  patterns:
    - temp-path OperatorConfigStore injection in all /config tests
    - evolve (do not delete) read-only suite to config-only PUT contract
    - planted-secret no-echo via JSON blob substring asserts

key-files:
  created:
    - services/admin-console-api/tests/test_config_api.py
  modified:
    - services/admin-console-api/tests/test_read_only.py
    - services/admin-console-api/tests/test_rbac_integration.py
    - services/admin-console-api/README.md

key-decisions:
  - "Evolved test_no_put_handler_exists into put-exists + 405 operational PUT (Pitfall 1)"
  - "RBAC /config cases use temp store + operator_config_enabled=True for allow paths"
  - "TDD RED skipped: handlers already landed in 74-02; this plan is proof-only"

patterns-established:
  - "Config tests always inject OperatorConfigStore(tmp_path) — never default runtime path"
  - "Operational write-proof = 405 method_not_allowed + views write-method scan + read_only metadata"

requirements-completed: [ADM-01, ADM-03]

duration: 2min
completed: 2026-07-10
---

# Phase 74 Plan 03: Config Tests + Read-Only Evolve Summary

**Automated proofs lock ADM-01/ADM-03: admin/operator GET+PUT `/config/*` succeed, lawyer/viewer are denied, operational PUT returns 405, flag-OFF PUT leaves no disk side effects, and planted secrets never echo.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-10T08:00:59Z
- **Completed:** 2026-07-10T08:02:53Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `test_config_api.py` covering section roundtrip, flag-OFF 403, GET-when-OFF, planted-secret 400 no-echo, and sections-only 404
- Evolved `test_read_only.py` to config-only PUT contract (405 on five operational prefixes; views still write-free)
- Extended `test_rbac_integration.py` with ADMIN/OPERATOR allow and LAWYER/VIEWER deny on `/config`
- Documented config surface, flags, and PYTHONPATH in admin README; full admin + rbac discovers green

## Task Commits

Each task was committed atomically:

1. **Task 1: Add test_config_api.py for GET/PUT, flag OFF, secrets** — `dc6ba13` (test)
2. **Task 2: Evolve test_read_only.py + extend test_rbac_integration.py** — `49ebfac` (test)
3. **Task 3: Document config surface in admin README + gate smoke** — `63775ab` (docs)

**Plan metadata:** _(pending final docs commit)_

## Files Created/Modified

- `services/admin-console-api/tests/test_config_api.py` — ADM-01/SC#4/secret no-echo proofs with temp store
- `services/admin-console-api/tests/test_read_only.py` — 405 operational PUT; `handle_admin_put` export allowed
- `services/admin-console-api/tests/test_rbac_integration.py` — `/config` role matrix cases
- `services/admin-console-api/README.md` — config mutate surface, flags, read-only ops, PYTHONPATH

## Decisions Made

- Evolved (did not delete) `test_read_only.py` per RESEARCH Pitfall 1 — operational write-denial kept
- RBAC allow cases inject temp `config_store` with `operator_config_enabled=True`
- Proof-only plan: no production code changes; handlers from 74-02

## TDD Gate Compliance

Tasks marked `tdd="true"` but plan `type: execute` (not `type: tdd`). Implementation already existed from 74-02, so RED (failing tests before implementation) was not applicable — tests were written against the landed handlers and passed immediately. Commits are `test(...)` / `docs(...)` only (no separate `feat` GREEN). This is intentional for a verification-wave plan.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None.

## Threat Mitigations

| Threat ID | Disposition | Evidence |
|-----------|-------------|---------|
| T-74-01 | mitigate | LAWYER/VIEWER 403 + ADMIN/OPERATOR 200 in `test_rbac_integration.py` |
| T-74-03 | mitigate | 405 `method_not_allowed` for all five operational prefixes in `test_read_only.py` |
| T-74-04 | mitigate | Flag-OFF PUT asserts 403 + empty temp dir / no `.tmp` in `test_config_api.py` |
| T-74-05 | mitigate | Planted `api_key` / `sk-` → 400 and substring absent from response JSON |
| T-74-SC | accept | No package installs |

## Known Stubs

None.

## Next Phase Readiness

Phase 74 Wave 3 complete. ADM-01 and ADM-03 are proven by automated tests; README matches the contract. Ready for phase verification / next v1.10 phase.

## Self-Check: PASSED

- FOUND: `services/admin-console-api/tests/test_config_api.py`
- FOUND: `services/admin-console-api/tests/test_read_only.py`
- FOUND: `services/admin-console-api/tests/test_rbac_integration.py`
- FOUND: `services/admin-console-api/README.md`
- FOUND: commits `dc6ba13`, `49ebfac`, `63775ab`

