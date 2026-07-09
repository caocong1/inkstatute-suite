---
phase: 61-access-token-manager
plan: 02
subsystem: channels
tags: [qqbot, access-token, asyncio, single-flight, wecom-isolation]

requires:
  - phase: 61-01
    provides: TokenManager with asyncio.Lock single-flight and TokenError paths
provides:
  - Concurrent single-flight + error-handling TokenManager tests (SC-3/SC-4)
  - AST wecom_service import isolation coverage for token_manager.py
affects: [62-egress-sender]

tech-stack:
  added: []
  patterns:
    - "asyncio.gather concurrent get_token single-flight assertion via FakeTokenTransport.call_count"
    - "TokenError sanitized-message assertions without credential/token leakage"
    - "AST _imported_modules scan for token_manager.py wecom isolation"

key-files:
  created: []
  modified:
    - packages/channels/qqbot/tests/test_token_manager.py
    - packages/channels/qqbot/tests/test_no_wecom_import.py

key-decisions:
  - "No production TokenManager changes required — Plan 01 lock re-check already satisfies SC-3"
  - "Error leak test uses invalid expires_in type path so access_token value never enters TokenError message"

patterns-established:
  - "TokenManagerConcurrentRefreshTests + TokenManagerErrorTests extend lifecycle suite in one file"
  - "test_token_manager_does_not_import_wecom_service inserted after normalization AST check"

requirements-completed: [EGRESS-01]

duration: 1min
completed: 2026-07-09
---

# Phase 61 Plan 02: Access Token Manager Verification Summary

**EGRESS-01 SC-3/SC-4 proven: 10 concurrent get_token waiters trigger one refresh, TokenError paths stay sanitized, and token_manager.py is covered by wecom AST isolation.**

## Performance

- **Duration:** 1 min
- **Started:** 2026-07-09T09:03:59Z
- **Completed:** 2026-07-09T09:04:43Z
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

- Extended `test_token_manager.py` with `TokenManagerConcurrentRefreshTests` (10× gather → `call_count == 2`) and `TokenManagerErrorTests` (HTTP 401, missing/invalid fields, no credential leak)
- Added `test_token_manager_does_not_import_wecom_service` to `test_no_wecom_import.py`
- Full qqbot safety suite remains green: `dependencies = []`, feature flag default-off, contract freeze, no wecom import (159 discover tests OK)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend test_token_manager.py with concurrent single-flight and error-handling tests** - `83711a9` (test)
2. **Task 2: Add token_manager.py to test_no_wecom_import.py and verify qqbot safety suite** - `0d3fea4` (test)

**Plan metadata:** `eac51e2` (docs: complete plan)

## Files Created/Modified

- `packages/channels/qqbot/tests/test_token_manager.py` — concurrent single-flight + error-handling classes
- `packages/channels/qqbot/tests/test_no_wecom_import.py` — AST isolation for `token_manager.py`

## Decisions Made

- Left `token_manager.py` unchanged — Plan 01 already implements lock re-check; concurrent test passed without production fix
- Kept all new coverage in existing test files (no second test module)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None — test-only plan; FakeTokenTransport only.

## Known Stubs

None

## Threat Flags

None — mitigations T-61-01 (sanitized errors), T-61-04 (single-flight), T-61-05 (wecom AST) covered by new tests; no new network endpoints or auth paths.

## Next Phase Readiness

Phase 61 EGRESS-01 verification complete. Phase 62 egress sender can consume `TokenManager.get_token()` with proven single-flight refresh and sanitized error propagation.

## Self-Check: PASSED

- FOUND: packages/channels/qqbot/tests/test_token_manager.py
- FOUND: packages/channels/qqbot/tests/test_no_wecom_import.py
- FOUND: 83711a9
- FOUND: 0d3fea4
