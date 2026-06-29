---
phase: 11-hermes-backendadapter-parity-spike
plan: 11-02
subsystem: backend
tags: [hermes, capability-probe, backend-adapter, safety]

requires:
  - phase: 11-hermes-backendadapter-parity-spike
    provides: 11-01 Hermes one-shot backend package
provides:
  - Non-mutating Hermes capability probe transport protocol
  - Probe report and issue dataclasses
  - Probe-to-manifest mapping with safe one-shot fallback
  - Tests for endpoint safety and sanitized fallback audit
affects: [hermes-backend, adapter-manifest]

tech-stack:
  added: []
  patterns: [injected read-only transport, safe endpoint allowlist, sanitized fallback manifests]

key-files:
  created:
    - packages/backends/hermes/src/inkstatute_backends_hermes/probe.py
    - packages/backends/hermes/tests/test_capability_probe.py
  modified:
    - packages/backends/hermes/src/inkstatute_backends_hermes/manifest.py
    - packages/backends/hermes/src/inkstatute_backends_hermes/__init__.py

key-decisions:
  - "Capability probing is transport-injected and dependency-free; hosts own actual HTTP wiring."
  - "The probe calls only /health, /v1/capabilities, and /v1/models."
  - "Probe failures and partial capability payloads fall back to one-shot with bounded reason codes."

patterns-established:
  - "Use SAFE_PROBE_PATHS as the single endpoint allowlist for Hermes startup capability detection."
  - "Build API-capable manifests only when probe results explicitly advertise runs_api support."

requirements-completed:
  - REQ-adapter-capability-probe

duration: 4min
completed: 2026-06-29
---

# Phase 11 Plan 02: Non-Mutating Capability Probe And Fallback Audit Summary

**Read-only Hermes capability probe with endpoint allowlist and sanitized one-shot fallback manifests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-29T00:07:11Z
- **Completed:** 2026-06-29T00:10:36Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `HermesProbeTransport`, `HermesCapabilityProbe`, `HermesProbeReport`, and `HermesProbeIssue`.
- Locked probing to `["/health", "/v1/capabilities", "/v1/models"]`.
- Added capability mapping into `AdapterCapabilitySet`, always preserving `no_channel_io=True`.
- Added `build_probe_manifest` so API-capable manifests require explicit `runs_api`; otherwise one-shot remains default with a sanitized `fallback_reason`.
- Added tests for healthy, partial, and failing probe responses, including URL/token/private-path sanitization.

## Task Commits

Tasks were grouped into one coherent probe feature commit:

1. **Tasks 11-02-01 through 11-02-03: probe model, mapping, fallback, and tests** - `0099523` (feat)

**Plan metadata:** this summary commit

## Files Created/Modified

- `packages/backends/hermes/src/inkstatute_backends_hermes/probe.py` - Probe protocol, report model, endpoint allowlist, and capability parsing.
- `packages/backends/hermes/src/inkstatute_backends_hermes/manifest.py` - Shared one-shot capabilities and probe-derived manifest builder.
- `packages/backends/hermes/src/inkstatute_backends_hermes/__init__.py` - Probe public exports.
- `packages/backends/hermes/tests/test_capability_probe.py` - Endpoint safety, fallback, and sanitization tests.

## Verification

- `python -m compileall packages/backends/hermes/src packages/backends/hermes/tests` - PASS
- `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/backends/hermes/tests/test_capability_probe.py` - PASS, 5 tests OK
- `PYTHONPATH=packages/backends/hermes/src:packages/platform-runtime/src:packages/platform-contract/src python -m unittest discover packages/backends/hermes/tests` - PASS, 14 tests OK

## Decisions Made

- The probe is synchronous and injected; this package does not introduce `requests`, `httpx`, `aiohttp`, sockets, subprocesses, or host-specific networking.
- Fallback audit records use reason codes such as `probe_endpoint_unavailable`, never raw exception text.
- API-run capability is represented as an opt-in lane, not a default lane.

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

Wave 3 can add the default-off `/v1/runs` lane using `build_probe_manifest` and the existing one-shot fallback as safety rails.

---
*Phase: 11-hermes-backendadapter-parity-spike*
*Completed: 2026-06-29*
