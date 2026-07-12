---
phase: 78-console-ssr-docs-gate-honesty
plan: 02
subsystem: ui
tags:
  - csrf
  - ssr
  - security

requires:
  - phase: 78-01
    provides: gate-honesty banner helper and dashboard chrome fixes

provides:
  - Signed, route-bound CSRF tokens for /config/channels
  - CSRF validation before form parsing or PUT proxy
  - Gate-honesty banner on channel config page
  - Exact UI-SPEC CSRF and validation error copy

affects:
  - 78-04

tech-stack:
  added: []
  patterns:
    - "Channel POST follows providers/catalog/vision CSRF pattern via _validate_post_csrf"

key-files:
  created: []
  modified:
    - services/admin-web-ui/src/admin_web_ui/server.py
    - services/admin-web-ui/src/admin_web_ui/channels.py
    - services/admin-web-ui/tests/test_channels_form.py

key-decisions:
  - "Body-usability guard runs before CSRF validation so empty/marker-less POSTs keep their 400 semantics"
  - "ERROR_VALIDATION updated to UI-SPEC generic 'Invalid config. Check the fields and try again.'"
  - "Routine OFF platform/host knob state uses muted .empty instead of destructive .status-err"

patterns-established:
  - "All /config/* POST routes now issue and validate a route-bound CSRF token before proxying"

requirements-completed:
  - ADM-02

duration: 12min
completed: 2026-07-12
---

# Phase 78 Plan 02 Summary

**Upgraded `/config/channels` to signed, route-bound CSRF protection and added the gate-honesty banner to the channel form.**

## Performance

- **Duration:** 12 min
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Replaced random `secrets.token_urlsafe` token in `_handle_channels` with `issue_csrf_token(identity, _CHANNELS_PATH, signing_key=rbac_secret)`.
- Added `_validate_post_csrf` before `parse_channels_form`; missing/invalid/cross-route/tampered tokens return 403 with exact UI-SPEC CSRF error.
- Kept the empty/marker-less POST guard and metadata merge behavior intact.
- Added `ERROR_CSRF` and updated `ERROR_VALIDATION` to the exact UI-SPEC strings.
- Inserted the shared gate-honesty banner at the top of `render_channels_form`.
- Switched routine OFF platform/host knob status to muted `.empty` per UI-SPEC.
- Updated and expanded `test_channels_form.py` with CSRF proof tests and valid-token POSTs.

## Task Commits

1. **Task 1: Add signed CSRF issue and validation to _handle_channels** - `f75ecb0` (feat)
2. **Task 2: Update channels form with gate-honesty banner and CSRF error copy** - `f75ecb0` (feat)
3. **Task 3: Update and expand test_channels_form.py for CSRF** - `f75ecb0` (test)

## Files Created/Modified

- `services/admin-web-ui/src/admin_web_ui/server.py` - `_handle_channels` now issues and validates route-bound CSRF tokens
- `services/admin-web-ui/src/admin_web_ui/channels.py` - Gate-honesty banner, `ERROR_CSRF`, UI-SPEC validation copy, muted OFF status
- `services/admin-web-ui/tests/test_channels_form.py` - CSRF validation proofs and valid-token POSTs

## Decisions Made

- Ran the body-usability guard before CSRF validation so empty/marker-less POSTs still return 400, preserving existing CR-01 behavior.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Next Phase Readiness

- Channel form is ready for the provider/catalog/vision banner integration in Plan 78-03.

---
*Phase: 78-console-ssr-docs-gate-honesty / Plan 02*
*Completed: 2026-07-12*
