---
phase: 22-recall-orchestrator-context-injection
status: passed
verified_at: 2026-07-02
score: 5/5
human_verification: []
review_status: local_self_review
---

# Phase 22 Verification

## Goal

WeCom and runtime flows can automatically retrieve approved memory refs and rolling summaries before backend submission, then attach a bounded `ContextBundle` without exposing session commands to ordinary users.

## Must-Haves

1. A memory orchestration layer runs before backend submission and retrieves approved memory refs for the resolved session scope (REC-01).
2. Retrieved memory refs, rolling summary refs, recent turn refs, feedback correction refs, artifact refs, and output-policy refs are passed into `ContextAssembler` (REC-02).
3. Tenant/workspace/user/session isolation is enforced, with fail-closed behavior on ambiguous or cross-scope retrieval (REC-03).
4. `MemoryUse` evidence records selected memories and context-bundle association without raw legal/customer text (REC-04).
5. Ordinary WeCom continue/start flows can use the orchestrator while preserving interrupt resume and active-task behavior (REC-05).

## Evidence

- `packages/platform-runtime/src/platform_runtime/memory_orchestrator.py` implements `MemoryOrchestrator` with `recall_and_assemble` and `MemoryUse` evidence policy.
- `packages/platform-runtime/tests/test_memory_orchestrator.py` covers recall, isolation, ContextBundle assembly, and MemoryUse evidence failure modes.
- `services/wecom-service/src/wecom_service/session_runtime.py` injects `MemoryOrchestrator` before `RunRuntime.create_run` for `CONTINUE_SESSION` and `START_NEW_SESSION` decisions.
- `services/wecom-service/src/wecom_service/ingress_runtime.py` passes optional memory and feedback-correction-ref providers into `WeComSessionRuntime`.
- `services/wecom-service/tests/test_session_memory_runtime.py` covers memory recall, bypass for interrupt/active-task paths, metadata refs, and fail-closed behavior.
- `services/wecom-service/tests/test_ingress_memory_runtime.py` covers ingress dependency pass-through and refs-only context metadata.
- `packages/contract-test-suite/fixtures/phase22_recall_orchestrator_context_injection.json` provides a synthetic fixture with recalled memory records, MemoryUse records, and context-bundle refs.
- `packages/contract-test-suite/tests/test_phase22_recall_orchestrator_context_injection.py` validates fixture schema and relationship checks.
- Phase 25.1 Plan 01 added the runtime wiring evidence needed to close the v1.3 audit gap.

## Automated Checks

- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src python -m unittest packages/platform-runtime/tests/test_memory_orchestrator.py` — passed, 17 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/platform-runtime/src:services/wecom-service/src python -m pytest services/wecom-service/tests/test_session_memory_runtime.py services/wecom-service/tests/test_ingress_memory_runtime.py -q` — passed, 9 tests.
- `PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_phase22_recall_orchestrator_context_injection.py' && PYTHONPATH=packages/platform-contract/src:packages/contract-test-suite/src python -m unittest discover -s packages/contract-test-suite/tests -p 'test_schema_validation.py'` — passed.

## Notes

- This is fixture-backed service-level verification, not live WeCom UAT or the five-workday lawyer trial.
- Interrupt resume and active-task follow-up paths bypass memory recall and preserve their existing behavior.
- No external service, database, queue, provider SDK, Hermes core change, raw legal payload store, or runtime secret was added.

## Result

Phase 22 passed. REC-01, REC-02, REC-04, and REC-05 are satisfied at the WeCom/runtime recall boundary; REC-03 isolation is enforced by the orchestrator and store layers.
