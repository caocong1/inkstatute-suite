---
phase: 18-external-memory-adapter-evaluation-and-acceptance-gates
plan: 18-01
subsystem: runtime-memory-adapters
tags: [memory, adapter-contract, capability-manifest, privacy, unittest]
requires:
  - phase: 17-long-term-memory-and-feedback-learning
    provides: Platform-native memory store and feedback learning policy
provides:
  - MemoryStore adapter protocol
  - MemoryStoreCapabilityManifest
  - MemoryAdapterEvaluation and decision helper
  - Local unit tests for external adapter acceptance gates
affects: [platform-runtime, contract-test-suite, phase-18-recommendation]
tech-stack:
  added: []
  patterns: [stdlib-only, provider-neutral-manifest, sanitized-spike-gates, no-runtime-coupling]
key-files:
  created:
    - packages/platform-runtime/src/platform_runtime/memory_adapters.py
    - packages/platform-runtime/tests/test_memory_adapter_contract.py
  modified:
    - packages/platform-runtime/src/platform_runtime/__init__.py
key-decisions:
  - "Represent external memory providers through a dependency-free capability manifest rather than SDK-specific code."
  - "Classify Mem0/Zep-style providers as accepted_for_sanitized_spike, not live legal defaults."
  - "Reject manifests that store raw payloads by default or try to become legal default without explicit live approval."
patterns-established:
  - "Adapter evaluation is a local manifest classification; it never contacts providers."
  - "RunRuntime and channel constructors remain unchanged by external memory adapter evaluation."
requirements-completed: [EXT-02]
duration: 8 min
completed: 2026-07-01
---

# Phase 18 Plan 01: Memory Adapter Contract Summary

**Provider-neutral adapter contract and capability manifest for external memory evaluation**

## Accomplishments

- Added `MemoryStoreAdapter` Protocol with manifest, upsert, search, tombstone/delete, and export hooks.
- Added `MemoryStoreCapabilityManifest`, `MemoryAdapterEvaluation`, `MemoryAdapterDecision`, and `evaluate_memory_adapter_manifest`.
- Added privacy validation for manifest refs and metadata, including raw payload keys and secret-like values.
- Added decision gates for current legal use, sanitized spikes, deferred legal production, and rejected legal memory.
- Exported the adapter contract surface from `platform_runtime`.

## Task Commits

1. **Tasks 1-2: Adapter manifest, evaluation helper, exports, and tests** - `32a0cb3` (feat)

## Verification

- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_adapter_contract.py` - passed, 8 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest discover -s packages/platform-runtime/tests` - passed, 98 tests.

## Deviations from Plan

None.

## Issues Encountered

None.

## Next Phase Readiness

Ready for Plan 18-02. The contract-test-suite fixture can now use the same decision vocabulary: `accepted_for_current_legal_use`, `accepted_for_sanitized_spike`, `deferred_for_legal_production`, and `rejected_for_legal_memory`.

## Self-Check: PASSED

---
*Phase: 18-external-memory-adapter-evaluation-and-acceptance-gates*
*Completed: 2026-07-01*
