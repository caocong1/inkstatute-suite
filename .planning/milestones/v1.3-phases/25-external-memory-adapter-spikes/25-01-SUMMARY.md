---
phase: "25-external-memory-adapter-spikes"
plan: "25-01"
title: "External adapter spike specs, comparison, and final recommendation"
status: complete
completed: "2026-07-02"
duration: "~20min"
tasks_completed: 3
files_changed: 3
---

# Plan 25-01 Summary: External Memory Adapter Spikes

## What Was Done

### New files
- `packages/platform-runtime/src/platform_runtime/memory_adapter_spikes.py` — `ExternalAdapterSpikeSpec`, `AdapterComparisonResult`, `MemoryAdapterRecommendation`, `ExternalAdapterSpikeRunner`, `canonical_spike_specs()`
- `packages/platform-runtime/tests/test_memory_adapter_spikes.py` — 19 tests covering XMEM-01..XMEM-05

### Modified files
- `packages/platform-runtime/src/platform_runtime/__init__.py` — exported 5 new types + `canonical_spike_specs`

## Key Decisions

- **Zep-style**: `keep_native` — fails `raw_payload_blocked=False` hard gate
- **ReMe-style**: `defer_external` — passes all hard gates but delta=0 in synthetic eval; needs scale/load spiking
- **Mem0-style**: `keep_native` — fails `tenant_isolation=no_built_in` + `raw_payload_blocked=False`
- **Final recommendation**: `defer_all_external` — platform-native memory remains the default
- All spike specs are `sanitized_fixture_only=True`; no live external network calls

## Test Results

- 19 spike tests: all pass
- 201 total runtime tests; 1 pre-existing output_boundary failure unchanged
