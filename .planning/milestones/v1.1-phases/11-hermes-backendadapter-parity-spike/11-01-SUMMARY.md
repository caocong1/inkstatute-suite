---
phase: 11-hermes-backendadapter-parity-spike
plan: 11-01
subsystem: backend
tags: [hermes, backend-adapter, one-shot, platform-runtime]

requires:
  - phase: 10-embeddable-runruntime-fake-backend
    provides: injected BackendAdapter runtime contract
provides:
  - Concrete Hermes backend package outside neutral runtime code
  - Reduced one-shot Hermes BackendAdapter with no channel I/O
  - Reference-first adapter state and artifact refs
  - Stdlib conformance and privacy tests
affects: [platform-runtime, contract-test-suite, hermes-backend]

tech-stack:
  added: []
  patterns: [injected BackendAdapter runner, reduced one-shot manifest, reference-first run metadata]

key-files:
  created:
    - packages/backends/hermes/pyproject.toml
    - packages/backends/hermes/src/inkstatute_backends_hermes/__init__.py
    - packages/backends/hermes/src/inkstatute_backends_hermes/config.py
    - packages/backends/hermes/src/inkstatute_backends_hermes/manifest.py
    - packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py
    - packages/backends/hermes/tests/test_hermes_backend_adapter.py
  modified: []

key-decisions:
  - "Keep Hermes implementation in packages/backends/hermes so platform-runtime remains backend-neutral."
  - "Use an injected HermesOneShotRunner seam for one-shot execution; runtime secrets and profile paths stay outside the repo."
  - "Expose truthful reduced capabilities: one-shot sync, no streaming/cancel/approval/live update/parallel task support."

patterns-established:
  - "Concrete backend packages implement platform_runtime.protocols.BackendAdapter without changing neutral runtime packages."
  - "Backend adapter metadata stores raw_payload_ref, refs, hashes, and sanitized runner metadata instead of raw prompts/transcripts."

requirements-completed:
  - REQ-hermes-backend-adapter

duration: 20min
completed: 2026-06-29
---

# Phase 11 Plan 01: Hermes Backend Package And One-Shot Adapter Summary

**Concrete Hermes one-shot BackendAdapter package with reduced capabilities, reference-first state, and privacy/conformance tests**

## Performance

- **Duration:** 20 min
- **Started:** 2026-06-28T23:47:00Z
- **Completed:** 2026-06-29T00:07:11Z
- **Tasks:** 4
- **Files modified:** 6

## Accomplishments

- Added `inkstatute-backends-hermes` with a `src/` package layout and stdlib-only runtime dependencies.
- Added `HermesBackendConfig`, reduced one-shot manifest builder, `HermesOneShotRunner`, `HermesOneShotResult`, and `HermesBackendAdapter`.
- Implemented one-shot run submission through an injected runner, with platform `RunHandle`, `Run`, and `ArtifactRecord` outputs.
- Locked unsupported streaming/cancel/approval behavior to deterministic non-runner paths, including high-risk legal approval human-review protection.
- Added stdlib unit tests for manifest validation, reduced capabilities, protocol method surface, privacy, artifact refs, unsupported methods, and neutral-runtime isolation.

## Task Commits

Tasks were grouped into one importable package commit:

1. **Tasks 11-01-01 through 11-01-04: Hermes one-shot backend package, manifest, adapter, and tests** - `e38a4f1` (feat)

**Plan metadata:** this summary commit

## Files Created/Modified

- `packages/backends/hermes/pyproject.toml` - Package metadata for the concrete Hermes backend.
- `packages/backends/hermes/src/inkstatute_backends_hermes/config.py` - Frozen Hermes backend config.
- `packages/backends/hermes/src/inkstatute_backends_hermes/manifest.py` - Reduced one-shot manifest builder.
- `packages/backends/hermes/src/inkstatute_backends_hermes/adapter.py` - One-shot `BackendAdapter` implementation.
- `packages/backends/hermes/src/inkstatute_backends_hermes/__init__.py` - Public package exports.
- `packages/backends/hermes/tests/test_hermes_backend_adapter.py` - Focused stdlib tests.

## Verification

- `python -m compileall packages/backends/hermes/src packages/backends/hermes/tests` - PASS
- `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_hermes_backend_adapter.py` - PASS, 9 tests OK
- `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest discover packages/backends/hermes/tests` - PASS, 9 tests OK
- Neutral runtime import scan for `inkstatute_backends_hermes|HermesBackendAdapter` - PASS, no matches

## Decisions Made

- The adapter requires an injected one-shot runner for execution; no Hermes core, live gateway, session storage, or model router is rebuilt in this package.
- `bootstrap_check` reports runner/command readiness but does not perform live Hermes I/O.
- Result metadata is sanitized recursively, and request content is represented by `request_content_sha256` plus `raw_payload_ref`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Commit Integrity] Grouped four new-package tasks into one feature commit**
- **Found during:** Task close-out
- **Issue:** Committing the package shell before config/manifest/adapter files would leave `__init__.py` imports pointing at missing modules.
- **Fix:** Committed the new package as one coherent importable unit and recorded the grouping here.
- **Files modified:** `packages/backends/hermes/*`
- **Verification:** Compile and focused test suite pass.
- **Committed in:** `e38a4f1`

---

**Total deviations:** 1 auto-fixed (Rule 3)
**Impact on plan:** No scope expansion; the grouped commit keeps the package bisectable as an importable unit.

## Issues Encountered

One test assertion initially banned the substring `raw_payload`, which incorrectly rejected the required `raw_payload_ref` field. The assertion was tightened to ban a raw `raw_payload` field while allowing references.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Wave 2 can build the non-mutating capability probe on top of the package exports and reduced manifest.

---
*Phase: 11-hermes-backendadapter-parity-spike*
*Completed: 2026-06-29*
