---
phase: 19-close-gap-v1-2-wecom-session-runtime-e2e-wiring
status: passed
verified_at: 2026-07-02
score: 5/5
human_verification: []
review_status: local_self_review
---

# Phase 19 Verification

## Goal

Ordinary WeCom continue/start-new turns reach `WeComSessionRuntime.handle_turn()` and submit backend runs through `RunRuntime.create_run()` while pending clarification answers still use `resume_interrupt()`.

## Must-Haves

1. `WeComSessionRuntime.handle_turn()` calls `RunRuntime.create_run()` for `CONTINUE_SESSION` and `START_NEW_SESSION` decisions and returns the created run id.
2. Pending clarification answers still use `RunRuntime.resume_interrupt()` exactly once with duplicate-answer idempotency preserved.
3. A service-level WeCom ingress orchestration helper normalizes sanitized callbacks, builds `SessionScope` and `RunRequest`, and invokes `WeComSessionRuntime.handle_turn()` without adding a server, database, queue, or live WeCom dependency.
4. Ordinary WeCom create-run requests carry bounded-context metadata references such as current turn, raw payload, recent turns, memory refs, feedback correction refs, artifacts, and output policy refs without storing raw legal/customer payloads.
5. Service-level tests cover continue, start-new, clarification resume, active-task fast-path preservation, callback ingress wiring, and context metadata attachment.

## Evidence

- `services/wecom-service/src/wecom_service/session_runtime.py` now calls `runtime.create_run()` for continue/start decisions, replaces the request session id with the resolved decision session, records `runtime_create_called`, and caches idempotent outcomes.
- `services/wecom-service/src/wecom_service/ingress_runtime.py` defines `WeComRuntimeIngress`, a pure host-callable callback-to-runtime boundary with sanitized normalization, scope/request construction, and reference-first metadata handling.
- `services/wecom-service/src/wecom_service/__init__.py` exports `WeComRuntimeIngress`.
- `services/wecom-service/tests/test_session_interrupt_runtime.py` covers runtime create-run handoff, duplicate create-run idempotency, interrupt resume preservation, and active-task no-run behavior.
- `services/wecom-service/tests/test_ingress_runtime.py` covers sanitized callback ingress wiring, start-new create-run, clarification resume, and context metadata refs.

## Automated Checks

- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:services/wecom-service/src python -m pytest services/wecom-service/tests/test_session_interrupt_runtime.py services/wecom-service/tests/test_ingress_runtime.py` - passed, 14 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src:services/wecom-service/src python -m pytest services/wecom-service/tests` - passed, 51 tests.
- `python -m py_compile services/wecom-service/src/wecom_service/session_runtime.py services/wecom-service/src/wecom_service/ingress_runtime.py services/wecom-service/tests/test_session_interrupt_runtime.py services/wecom-service/tests/test_ingress_runtime.py` - passed.

## Notes

- This is fixture-backed service-level E2E closure, not live WeCom UAT or the five-workday lawyer trial.
- No server, database, queue, live WeCom call, Hermes core change, raw legal payload store, or runtime secret was added.
- Feedback-to-memory-to-next-context service wiring remains outside this critical audit-gap closure.

## Result

Phase 19 passed. CTX-01, CTX-02, CTX-03, INT-02, STM-01, and STM-02 are satisfied at the WeCom service/runtime integration boundary: ordinary WeCom turns now have a concrete path from sanitized callback to session decision to backend run submission with bounded-context metadata refs.
