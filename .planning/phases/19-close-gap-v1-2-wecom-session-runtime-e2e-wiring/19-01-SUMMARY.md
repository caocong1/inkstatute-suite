---
phase: 19-close-gap-v1-2-wecom-session-runtime-e2e-wiring
plan: 19-01
subsystem: wecom-session-runtime-e2e
tags: [wecom, session-runtime, context, interrupt, pytest]
requires:
  - phase: 15
    provides: Session resolver and interrupt runtime primitives
  - phase: 16
    provides: Context assembler metadata contract
  - phase: 18
    provides: v1.2 audit gap evidence
provides:
  - WeCom continue/start runtime create-run handoff
  - Pure WeCom callback ingress runtime helper
  - Service-level tests for continue, start-new, clarification resume, and context metadata refs
affects: [wecom-service, platform-runtime-integration, phase-19-verification]
tech-stack:
  added: []
  patterns: [dependency-injected-runtime, reference-first-privacy, no-live-wecom-fixtures]
key-files:
  created:
    - services/wecom-service/src/wecom_service/ingress_runtime.py
    - services/wecom-service/tests/test_ingress_runtime.py
  modified:
    - services/wecom-service/src/wecom_service/session_runtime.py
    - services/wecom-service/src/wecom_service/__init__.py
    - services/wecom-service/tests/test_session_interrupt_runtime.py
key-decisions:
  - "Use `RunRuntime.create_run()` for WeCom continue/start-new session decisions."
  - "Keep pending clarification answers on `RunRuntime.resume_interrupt()` with duplicate-answer idempotency."
  - "Expose a pure `WeComRuntimeIngress` host boundary instead of adding a server, database, queue, or live WeCom dependency."
  - "Carry bounded-context inputs as metadata refs and reject raw payload/full-text metadata keys."
requirements-completed: [CTX-01, CTX-02, CTX-03, INT-02, STM-01, STM-02]
duration: 35 min
completed: 2026-07-02
---

# Phase 19 Plan 01: WeCom Session Runtime E2E Closure Summary

## Accomplishments

- Updated `WeComSessionRuntime.handle_turn()` so `CONTINUE_SESSION` and `START_NEW_SESSION` decisions call `runtime.create_run()` and return the created run id.
- Preserved `RESUME_INTERRUPT` behavior and active-task fast control-plane behavior.
- Added privacy-safe create-run metadata for session decision id/action/reason, session id, current turn ref, raw payload refs, and context assembly refs.
- Added `WeComRuntimeIngress`, a host-callable pure ingress boundary that normalizes sanitized callbacks, builds `SessionScope` and `RunRequest`, and invokes `WeComSessionRuntime`.
- Exported `WeComRuntimeIngress` from `wecom_service`.
- Added regression tests for continue/create-run, start-new/create-run, duplicate create-run idempotency, active-task no-run preservation, callback ingress wiring, clarification resume, and context metadata attachment.

## Verification

- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:services/wecom-service/src python -m pytest services/wecom-service/tests/test_session_interrupt_runtime.py services/wecom-service/tests/test_ingress_runtime.py` - passed, 14 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:services/wecom-service/src python -m pytest services/wecom-service/tests` - passed, 51 tests.
- `python -m py_compile services/wecom-service/src/wecom_service/session_runtime.py services/wecom-service/src/wecom_service/ingress_runtime.py services/wecom-service/tests/test_session_interrupt_runtime.py services/wecom-service/tests/test_ingress_runtime.py` - passed.

## Deviations from Plan

- The closure used a pure `WeComRuntimeIngress` orchestration class rather than a live callback server. This matches the project boundary: no new service process, database, queue, live WeCom dependency, or Hermes core rebuild in this repo phase.

## Issues Encountered

- The first broad service test run failed during collection because `contract_test_suite` was missing from `PYTHONPATH`. Rerunning with `packages/contract-test-suite/src` included passed.
- Two new continue-session tests initially used the wall clock, making synthetic recent sessions stale. They were corrected to use the existing fake clock.

## Result

Phase 19 Plan 01 passed. The critical v1.2 audit gaps for ordinary WeCom continue/start-new runtime handoff and concrete service-level ingress wiring are closed at the dependency-injected library boundary.

## Self-Check: PASSED

---
*Phase: 19-close-gap-v1-2-wecom-session-runtime-e2e-wiring*
*Completed: 2026-07-02*
