---
phase: 10-embeddable-runruntime-fake-backend
reviewed: 2026-06-28T20:18:30Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - packages/contract-test-suite/fixtures/phase10_runruntime_fake_backend.json
  - packages/contract-test-suite/scripts/run_contract_tests.py
  - packages/contract-test-suite/tests/test_phase10_runruntime_contracts.py
  - packages/contract-test-suite/tests/test_schema_validation.py
  - packages/platform-runtime/README.md
  - packages/platform-runtime/src/platform_runtime/__init__.py
  - packages/platform-runtime/src/platform_runtime/fakes.py
  - packages/platform-runtime/src/platform_runtime/feature_flags.py
  - packages/platform-runtime/src/platform_runtime/output_boundary.py
  - packages/platform-runtime/src/platform_runtime/ports.py
  - packages/platform-runtime/src/platform_runtime/runtime.py
  - packages/platform-runtime/src/platform_runtime/store.py
  - packages/platform-runtime/tests/test_contract_log_store.py
  - packages/platform-runtime/tests/test_feature_flags.py
  - packages/platform-runtime/tests/test_output_boundary.py
  - packages/platform-runtime/tests/test_run_runtime_lifecycle.py
findings:
  critical: 2
  warning: 1
  info: 0
  total: 3
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-06-28T20:18:30Z
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

Reviewed the Phase 10 runtime support layer, fake adapters, output boundary, contract fixture, runner wiring, and tests. The runtime shape is mostly aligned with the embeddable fake-backend plan, but the stream boundary has a real leak path when visible text is carried in event metadata, and contract-log-enabled operations can mutate the backend before discovering that the log store is missing. One support API also accepts a callable clock despite the project clock port exposing `now()`.

## Critical Issues

### CR-01: Output boundary leaves blocked or rewritten visible metadata on yielded events

**File:** `packages/platform-runtime/src/platform_runtime/runtime.py:169`
**Issue:** `_event_visible_text()` intentionally treats both `event.payload` and `event.metadata` as possible visible-text carriers, but `_apply_output_boundary()` only scrubs or rewrites `event.payload`. If a backend puts visible text in metadata, blocked text remains in the yielded event metadata and rewritten backend notices remain alongside the sanitized replacement. This violates the Phase 10 requirement that blocked originals never appear in yielded events or audit metadata.
**Fix:** When the boundary blocks or rewrites an event, remove visible-text keys from metadata as well as payload. For rewrites, emit the owned replacement in the payload and do not preserve the original metadata text. Add regression tests for metadata-carried blocked and rewritten text.

### CR-02: Contract-log-enabled operations mutate the backend before failing on missing log store

**File:** `packages/platform-runtime/src/platform_runtime/runtime.py:46`
**Issue:** `create_run()`, `cancel()`, and `approve()` call the backend before `_contract_log()` checks whether `contract_log_enabled` has a store. With `contract_log_enabled=True` and no `contract_log_store`, `create_run()` raises `RunRuntimeStateError` only after `backend.submit_run()` created a run. That leaves an unlogged backend side effect in a mode that explicitly requires contract-log evidence.
**Fix:** Preflight the contract log dependency immediately after feature-flag checks and before any backend mutation in `create_run()`, `cancel()`, and `approve()`. Add tests asserting no backend submit/cancel/approval side effects occur when the log store is missing.

## Warnings

### WR-01: In-memory contract log store does not accept the declared clock port shape

**File:** `packages/platform-runtime/src/platform_runtime/store.py:131`
**Issue:** `RuntimeClock` is declared as a port with a `now()` method, and Phase 10 introduces fake runtime clocks with that method. `InMemoryContractLogStore` names its dependency `clock` but calls it directly, so passing a `RuntimeClock` implementation such as `FakeRuntimeClock()` raises `TypeError: 'FakeRuntimeClock' object is not callable`. Tests only cover the workaround `clock=clock.now`.
**Fix:** Resolve the current time through either a callable clock or an object with a callable `now()` method, while preserving the existing callable behavior. Add a focused test for a `now()`-based clock object.

---

_Reviewed: 2026-06-28T20:18:30Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
