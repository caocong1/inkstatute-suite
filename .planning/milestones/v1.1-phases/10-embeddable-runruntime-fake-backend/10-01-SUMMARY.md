---
phase: 10-embeddable-runruntime-fake-backend
plan: 10-01
subsystem: runtime
tags: [python, platform-runtime, feature-flags, contract-log, ports]

# Dependency graph
requires:
  - phase: 09-platform-foundation-contracts
    provides: [platform-runtime Protocol surface, platform-contract run/channel schemas, boundary allowlist policy]
provides:
  - injected runtime support ports for clocks, IDs, contract-log storage, and assistant output boundary
  - default-off Phase 10 runtime feature flags
  - append-only reference-first in-memory contract log store
affects: [platform-runtime, contract-test-suite, run-runtime, fake-backend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - dependency-injected runtime support ports
    - frozen default-off feature flag dataclass
    - copy-safe append-only in-memory contract log entries

key-files:
  created:
    - packages/platform-runtime/src/platform_runtime/ports.py
    - packages/platform-runtime/src/platform_runtime/feature_flags.py
    - packages/platform-runtime/src/platform_runtime/store.py
    - packages/platform-runtime/tests/test_feature_flags.py
    - packages/platform-runtime/tests/test_contract_log_store.py
  modified:
    - packages/platform-runtime/src/platform_runtime/__init__.py

key-decisions:
  - "Keep platform-runtime support library-only: injected ports and in-memory support types only, with no server, channel, database, queue, backend construction, or background process behavior."
  - "Default every Phase 10 runtime lane to False and require explicit opt-in through RuntimeFeatureFlags.require_enabled."
  - "Harden the contract log store beyond the minimum top-level raw_payload check by rejecting nested raw_payload keys and obvious full-text payload field names while allowing raw_payload_ref and ID/hash/reference fields."

patterns-established:
  - "Runtime support ports are stdlib Protocols and dataclasses exported from platform_runtime."
  - "Contract log store read APIs return copied entries so callers cannot mutate internal records in place."
  - "Privacy validation is enforced at append time before event mappings enter the store."

requirements-completed:
  - REQ-platform-run-runtime
  - REQ-runtime-embeddability

# Metrics
duration: 4 min
completed: 2026-06-28
---

# Phase 10 Plan 10-01: Runtime Ports, Feature Flags, And Append-Only Store Summary

**Injected runtime ports, default-off runtime lanes, and append-only reference-first contract log storage for the embeddable RunRuntime foundation**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-28T19:39:08Z
- **Completed:** 2026-06-28T19:42:49Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Added neutral injected support ports for clocks, ID creation, contract-log storage, and assistant output boundary decisions.
- Added `RuntimeFeatureFlags` with all Phase 10 runtime lanes defaulting to `False`, plus deterministic package-local errors for disabled or unknown lanes.
- Added `InMemoryContractLogStore` with monotonic sequence numbers, reference-first privacy validation, copy-safe reads, and run filtering.

## Task Commits

Each task was committed atomically:

1. **Task 10-01-01: Add neutral runtime ports for injected dependencies** - `4cb9743` (feat)
2. **Task 10-01-02: Add default-off runtime feature flags** - `7d9345f` (feat)
3. **Task 10-01-03: Create an append-only, reference-first in-memory contract log store** - `00df4bb` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `packages/platform-runtime/src/platform_runtime/ports.py` - Defines injected support Protocols and assistant output boundary decision shape.
- `packages/platform-runtime/src/platform_runtime/feature_flags.py` - Defines default-off runtime feature flags and package-local disabled-flag error.
- `packages/platform-runtime/src/platform_runtime/store.py` - Defines copy-safe append-only in-memory contract log entries and store.
- `packages/platform-runtime/src/platform_runtime/__init__.py` - Exports new port, feature-flag, and store symbols.
- `packages/platform-runtime/tests/test_feature_flags.py` - Covers default-off, explicit opt-in, disabled, and unknown flag behavior.
- `packages/platform-runtime/tests/test_contract_log_store.py` - Covers monotonic sequencing, copy-safe reads, privacy rejection, refs, and run filtering.

## Decisions Made

- Keep the runtime support layer as a library-only surface with dependency injection and no server/channel/backend construction behavior.
- Represent runtime lane availability with one frozen dataclass and explicit `require_enabled()` checks so tests and later runtime code cannot accidentally treat lanes as default-on.
- Enforce reference-first log behavior at append time rather than relying only on callers or downstream boundary scans.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Hardened privacy rejection beyond top-level raw_payload**
- **Found during:** Task 10-01-03 (append-only contract log store)
- **Issue:** The task acceptance required top-level `raw_payload` rejection, while the execution requirement also required rejecting `raw_payload` keys and sensitive full-text payload storage.
- **Fix:** The store now rejects `raw_payload` at any nesting level and rejects obvious full-text payload fields such as `payload_text`, `full_text`, `raw_text`, `document_text`, `customer_document_text`, and `case_facts`.
- **Files modified:** `packages/platform-runtime/src/platform_runtime/store.py`, `packages/platform-runtime/tests/test_contract_log_store.py`
- **Verification:** `PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/platform-runtime/tests/test_contract_log_store.py` passed.
- **Committed in:** `00df4bb`

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Privacy enforcement is stricter and still within the plan boundary. No server, channel, backend, database, queue, or runtime service behavior was added.

## Issues Encountered

None.

## Verification

- `python -m compileall packages/platform-runtime/src packages/platform-runtime/tests` exited 0.
- `PYTHONPATH=packages/platform-runtime/src:packages/platform-contract/src python -m unittest packages/platform-runtime/tests/test_feature_flags.py packages/platform-runtime/tests/test_contract_log_store.py` exited 0: ran 10 tests, OK.
- `PYTHONPATH=packages/contract-test-suite/src:packages/platform-contract/src python -m unittest packages/contract-test-suite/tests/test_boundary_allowlist.py packages/contract-test-suite/tests/test_thin_layer_boundaries.py` exited 0: ran 18 tests, OK.

## Known Stubs

None. Stub scan found only the real internal empty list initialization used by `InMemoryContractLogStore`.

## Threat Flags

None. The new runtime files add library-only in-memory support types and introduce no network endpoint, auth path, file access, database, queue, service process, or trust-boundary schema change.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 10-02 to build fake adapters and lifecycle runtime behavior on top of the injected ports, default-off flags, and reference-first contract log store.

## Self-Check: PASSED

- Created files exist: `ports.py`, `feature_flags.py`, `store.py`, `test_feature_flags.py`, `test_contract_log_store.py`, and this summary.
- Task commits exist: `4cb9743`, `7d9345f`, and `00df4bb`.

---
*Phase: 10-embeddable-runruntime-fake-backend*
*Completed: 2026-06-28*
