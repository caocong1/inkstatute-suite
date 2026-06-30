---
phase: 11-hermes-backendadapter-parity-spike
plan: 11-03
subsystem: backend
tags: [hermes, runs-api, feature-flag, approval-safety]

requires:
  - phase: 11-hermes-backendadapter-parity-spike
    provides: 11-02 non-mutating capability probe and manifest mapping
provides:
  - Adapter-local INKSTATUTE_HERMES_API_RUNS_ENABLED parsing
  - Default-off Hermes /v1/runs client seam
  - Known-state Hermes status mapper
  - High-risk legal approval rejection guard
affects: [hermes-backend, parity-fixtures, approval-safety]

tech-stack:
  added: []
  patterns: [default-off API lane, injected runs transport, sanitized status mapping]

key-files:
  created:
    - packages/backends/hermes/src/inkstatute_backends_hermes/runs_api.py
    - packages/backends/hermes/tests/test_runs_lane.py
  modified:
    - packages/backends/hermes/src/inkstatute_backends_hermes/config.py
    - packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py
    - packages/backends/hermes/src/inkstatute_backends_hermes/__init__.py

key-decisions:
  - "Enable /v1/runs only through exact true-ish env values: 1, true, yes."
  - "HermesBackendAdapter keeps one-shot default unless invocation_mode='runs_api', config.api_runs_enabled=True, and a runs client is injected."
  - "High-risk legal approvals never call one-shot runner or /v1/runs transport."

patterns-established:
  - "Default-off backend lanes should fail closed at the client seam and fall back to one-shot at the adapter default."
  - "Unknown backend statuses map to AsyncTaskState.FAILED with hashed status evidence, never raw backend text."

requirements-completed:
  - REQ-hermes-backend-adapter
  - REQ-hermes-run-parity-spike

duration: 5min
completed: 2026-06-29
---

# Phase 11 Plan 03: Default-Off Runs Lane And Approval Safety Summary

**Opt-in Hermes `/v1/runs` client seam with default-off gating, one-shot fallback, and high-risk legal approval rejection**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-29T00:10:36Z
- **Completed:** 2026-06-29T00:15:19Z
- **Tasks:** 4
- **Files modified:** 5

## Accomplishments

- Extended `HermesBackendConfig` with `api_runs_enabled`, `api_base_url`, and safe env parsing.
- Added `HermesRunsClient`, `HermesRunsTransport`, `HermesRunsDisabledError`, and `map_hermes_run_status`.
- Wired `HermesBackendAdapter` so API runs require explicit `invocation_mode="runs_api"`, enabled config, and an injected client.
- Preserved one-shot as the default and fallback when API runs are disabled.
- Added high-risk legal approval detection with `approval_rejected: "high_risk_legal_human_review_required"`.
- Added tests for disabled fail-closed behavior, enabled run paths, event path usage, status mapping, fallback, and approval safety.

## Task Commits

Tasks were grouped into one coherent runs-lane feature commit:

1. **Tasks 11-03-01 through 11-03-04: config gate, runs client, adapter wiring, approval safety, and tests** - `635f9c2` (feat)

**Plan metadata:** this summary commit

## Files Created/Modified

- `packages/backends/hermes/src/inkstatute_backends_hermes/runs_api.py` - Default-off `/v1/runs` client seam and status mapper.
- `packages/backends/hermes/src/inkstatute_backends_hermes/config.py` - API-run config and env parsing.
- `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py` - Optional API-run adapter path and approval guard.
- `packages/backends/hermes/src/inkstatute_backends_hermes/__init__.py` - Runs-lane exports.
- `packages/backends/hermes/tests/test_runs_lane.py` - Focused default-off and approval-safety tests.

## Verification

- `python -m compileall packages/backends/hermes/src packages/backends/hermes/tests` - PASS
- `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_runs_lane.py` - PASS, 9 tests OK
- `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest discover packages/backends/hermes/tests` - PASS, 23 tests OK

## Decisions Made

- The adapter does not promote `/v1/runs` based on probe success alone; explicit construction is still required.
- The runs client serializes request content as refs and hashes, not raw prompt text.
- Unknown status text is represented by SHA-256 evidence and `unknown_status=True`.

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written.

---

**Total deviations:** 0 auto-fixed
**Impact on plan:** No scope change.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Wave 4 can compare one-shot observations with `/v1/runs` observations using sanitized fixtures without promoting `/v1/runs`.

---
*Phase: 11-hermes-backendadapter-parity-spike*
*Completed: 2026-06-29*
