---
phase: 86-product-polish
plan: 03
subsystem: infra
tags: [bash, startup-script, env-docs, pid-tracking, session-auth]

# Dependency graph
requires:
  - phase: 85-session-auth
    provides: ADMIN_USERNAME, ADMIN_PASSWORD, SESSION_TTL_SECONDS, ADMIN_WEB_UI_SECURE_COOKIE env vars
  - phase: 79-admin-console
    provides: admin_web_ui and admin_console_api __main__.py entry points
provides:
  - "scripts/start-console.sh — one-click startup for admin-web-ui + admin-console-api"
  - ".env.example Session auth (Phase 85) section with documented env vars"
  - "TestStartupScript test class (5 tests)"
  - "TestEnvDocs test class (3 tests)"
affects: [operator-console, product-polish]

# Tech tracking
tech-stack:
  added: []
  patterns: [bash-env-loading, json-pid-tracking, trap-cleanup, dry-run-ci-testing]

key-files:
  created:
    - scripts/start-console.sh
    - services/admin-web-ui/tests/test_startup_script.py
    - services/admin-web-ui/tests/test_env_docs.py
  modified:
    - .env.example

key-decisions:
  - "Used JSON PID file (~/.inkstatute/console-pids.json) instead of .pid files to match ProcessSupervisor pattern and .gitignore rules"
  - "Env file missing prints warning and continues (not error) since env vars may already be set in shell"
  - "All .env.example auth entries commented out with inline # comments explaining purpose, default, constraints"

patterns-established:
  - "Pattern: set -a; source .env; set +a for env loading in startup scripts"
  - "Pattern: JSON PID file in ~/.inkstatute/ for process tracking"
  - "Pattern: trap EXIT cleanup for child process lifecycle management"
  - "Pattern: --dry-run flag for CI testing without port binding"

requirements-completed:
  - POLISH-04
  - POLISH-05

# Metrics
duration: 3min
completed: 2026-07-14
---

# Phase 86 Plan 03: Startup Script + Env Docs Summary

**One-click bash startup script for admin-web-ui + admin-console-api with env loading, JSON PID tracking, trap cleanup, and complete .env.example auth var documentation**

## Performance

- **Duration:** ~3 min
- **Tasks:** 2
- **Files modified:** 4 (2 created, 1 modified, 1 created)

## Accomplishments
- Created `scripts/start-console.sh` with env loading (set -a; source; set +a), dual service launch, JSON PID file, trap EXIT cleanup, and --dry-run flag
- Documented all 4 Phase 85 auth env vars in `.env.example` with inline comments and section header
- 8 tests passing (5 TestStartupScript + 3 TestEnvDocs)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create scripts/start-console.sh with env loading, PID tracking, and trap cleanup** - `7016c9f` (feat)
2. **Task 2: Add Phase 85 auth env vars to .env.example with inline comments** - `9df670e` (docs)

## Files Created/Modified
- `scripts/start-console.sh` - NEW: Bash startup script launching admin-web-ui + admin-console-api with env loading, JSON PID tracking, trap cleanup, --dry-run support
- `.env.example` - MODIFIED: Added "# --- Session auth (Phase 85) ---" section with ADMIN_USERNAME, ADMIN_PASSWORD, SESSION_TTL_SECONDS, ADMIN_WEB_UI_SECURE_COOKIE
- `services/admin-web-ui/tests/test_startup_script.py` - NEW: TestStartupScript class (5 tests verifying script structure)
- `services/admin-web-ui/tests/test_env_docs.py` - NEW: TestEnvDocs class (3 tests verifying env var documentation)

## Decisions Made
- Used JSON PID file (`~/.inkstatute/console-pids.json`) instead of .pid files — matches ProcessSupervisor pattern and .gitignore ignores *.pid files
- Env file missing prints warning to stderr and continues (not error exit) — env vars may already be set in shell
- All .env.example auth entries are commented out (prefixed with #) following existing example file pattern

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Pre-existing V2 gate failures (4 failures, 7 errors in wecom-service CHAN-03 tests) are unrelated to this plan's changes. Verified identical failure count before and after our commits.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- start-console.sh ready for operator use (requires .env with feature flags enabled)
- All Phase 85 auth env vars now documented for operator reference
- Test suite covers script structure and env documentation completeness

## Self-Check: PASSED

- `bash -n scripts/start-console.sh` — PASS (syntax valid)
- `test -x scripts/start-console.sh` — PASS (executable)
- `test -f scripts/start-console.sh` — PASS (file exists)
- TestStartupScript: 5/5 tests PASS
- TestEnvDocs: 3/3 tests PASS
- `grep -c "ADMIN_USERNAME|ADMIN_PASSWORD|SESSION_TTL_SECONDS|ADMIN_WEB_UI_SECURE_COOKIE" .env.example` returns 4 (≥4 required)
- V2 gate suite: pre-existing failures unchanged (no new failures introduced)

---
*Phase: 86-product-polish*
*Plan: 03*
*Completed: 2026-07-14*
