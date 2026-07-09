---
phase: 61-access-token-manager
plan: 01
subsystem: channels
tags: [qqbot, access-token, asyncio, urllib, transport-injection]

requires:
  - phase: 59-ed25519-signature
    provides: qqbot package scaffold with dependencies = []
provides:
  - TokenManager with cache, auto-refresh, and single-flight lock
  - TokenTransport Protocol + FakeTokenTransport + UrllibTokenTransport
  - Lifecycle and import-safety unit tests for token acquisition
affects: [62-egress-sender, 61-02]

tech-stack:
  added: []
  patterns:
    - "Transport Protocol + Fake + lazy urllib via asyncio.to_thread"
    - "Injectable monotonic clock for cache expiry tests"
    - "asyncio.Lock single-flight with lock re-check"

key-files:
  created:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py
    - packages/channels/qqbot/tests/test_token_manager.py
  modified: []

key-decisions:
  - "Default transport is UrllibTokenTransport(); tests inject FakeTokenTransport"
  - "Cache TTL uses response expires_in, never hardcoded 7200"
  - "Credentials injected as constructor strings; no env/file reads"
  - "TokenManager stays internal — not exported from __init__.py"

patterns-established:
  - "TokenTransport injection mirrors OllamaTransport for dependencies = [] HTTP"
  - "Fast-path get_token without lock; slow-path lock + re-check + refresh"
  - "Sanitized TokenError messages with optional status_code only"

requirements-completed: [EGRESS-01]

duration: 2min
completed: 2026-07-09
---

# Phase 61 Plan 01: Access Token Manager Summary

**QQ Bot TokenManager with transport injection, expires_in-based cache, and 60s pre-expiry auto-refresh — stdlib-only, dependencies = [] preserved.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-09T08:59:19Z
- **Completed:** 2026-07-09T09:00:56Z
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

- Delivered `TokenManager` with acquire → cache → 60s pre-expiry refresh → invalidate lifecycle
- Production `UrllibTokenTransport` POSTs to `https://bots.qq.com/app/getAppAccessToken` via lazy urllib + `asyncio.to_thread`
- Lifecycle and import-safety tests green with FakeTokenTransport only (no network I/O)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create token_manager.py** - `c97bdae` (feat)
2. **Task 2: Create test_token_manager.py** - `77d1836` (test)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py` — TokenTransport, FakeTokenTransport, UrllibTokenTransport, TokenError, TokenManager
- `packages/channels/qqbot/tests/test_token_manager.py` — TokenManagerLifecycleTests + TokenManagerImportSafetyTests

## Decisions Made

- Followed OllamaRunner transport-injection pattern: Protocol + Fake + lazy urllib inside method body
- `TokenManager` defaults to `UrllibTokenTransport()` when transport is omitted
- Cache TTL always from response `expires_in`; refresh at `expires_at - refresh_margin` (default 60.0)
- Credentials are constructor-injected strings; host owns secret-store resolution
- Left `__init__.py` unchanged — Phase 62 imports `.token_manager` directly

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None — library-only module; no external service configuration in this plan.

## Known Stubs

None — FakeTokenTransport is intentional test infrastructure; UrllibTokenTransport is production-ready.

## Threat Flags

None — threat mitigations T-61-01 (sanitized errors), T-61-02 (credential injection), T-61-04 (asyncio.Lock) implemented as planned; no new endpoints or auth paths beyond the planned getAppAccessToken transport.

## Next Phase Readiness

Plan 02 can extend `test_token_manager.py` with concurrent single-flight, error-handling, and wecom-import isolation tests. TokenManager API is ready for Phase 62 egress sender consumption.

## Self-Check: PASSED

- FOUND: packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py
- FOUND: packages/channels/qqbot/tests/test_token_manager.py
- FOUND: c97bdae
- FOUND: 77d1836
