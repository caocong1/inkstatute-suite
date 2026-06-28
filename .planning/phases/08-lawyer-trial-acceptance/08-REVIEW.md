---
phase: 08-lawyer-trial-acceptance
status: clean
reviewed_at: 2026-06-28T23:53:52+08:00
reviewer: codex-inline
depth: standard
files:
  - packages/contract-test-suite/src/contract_test_suite/trial_acceptance.py
  - packages/contract-test-suite/tests/test_trial_acceptance.py
  - scripts/inkstatute_wecom_live_bridge.py
  - services/wecom-service/src/wecom_service/__init__.py
  - services/wecom-service/src/wecom_service/active_task_router.py
  - services/wecom-service/src/wecom_service/delivery_guard.py
  - services/wecom-service/src/wecom_service/owned_notices.py
  - services/wecom-service/src/wecom_service/runtime_audit.py
  - services/wecom-service/src/wecom_service/task_flow.py
  - services/wecom-service/tests/test_active_task_router.py
  - services/wecom-service/tests/test_delivery_guard.py
  - services/wecom-service/tests/test_runtime_audit.py
  - services/wecom-service/tests/test_task_flow.py
finding_counts:
  critical: 0
  warning: 0
  info: 0
  total: 0
files_reviewed: 13
---

# Phase 08 Code Review

## Result

No code findings.

## Scope

- `packages/contract-test-suite/src/contract_test_suite/trial_acceptance.py`
- `packages/contract-test-suite/tests/test_trial_acceptance.py`
- `scripts/inkstatute_wecom_live_bridge.py`
- `services/wecom-service/src/wecom_service/__init__.py`
- `services/wecom-service/src/wecom_service/active_task_router.py`
- `services/wecom-service/src/wecom_service/delivery_guard.py`
- `services/wecom-service/src/wecom_service/owned_notices.py`
- `services/wecom-service/src/wecom_service/runtime_audit.py`
- `services/wecom-service/src/wecom_service/task_flow.py`
- `services/wecom-service/tests/test_active_task_router.py`
- `services/wecom-service/tests/test_delivery_guard.py`
- `services/wecom-service/tests/test_runtime_audit.py`
- `services/wecom-service/tests/test_task_flow.py`

## Checks

- Verified fixture evidence cannot count as live trial evidence.
- Verified readiness gates block otherwise qualifying live rows.
- Verified PRD thresholds for workdays, task count, clear business output, categories, success rates, feedback capture, positive feedback, negative feedback response timing, route mismatch candidate evidence, output-boundary checks, and Hermes meta leaks.
- Verified formatted summaries expose status/counts/issue codes without task rows.
- Verified the evidence template test keeps placeholder data blocked.
- Verified task-flow events map service stages to platform async states while keeping `received` and `turn_ready` as service-only metadata.
- Verified task-flow and active-task route records hash user text and avoid raw legal payload storage.
- Verified active-task routing does not claim Hermes one-shot live updates, cancellation, streaming progress, or parallel tasks are supported.
- Verified live bridge now creates one background task after turn aggregation, sends an immediate service-owned ACK, emits service-owned progress, records timeout/failure/completion states, and routes follow-up turns through the fast control plane.
- Verified delivery guard rejects progress-only DOCX generation text as `agent_backend_incomplete_output` when the user requested file delivery and no artifact is present.
- Verified runtime audit JSONL can record bot/Hermes boundary payloads and newly written Hermes `state.db` transcript messages outside the repo with secret-key redaction and mode `0600`.
- Verified focused tests, py_compile, full WeCom service tests, and full V2 gates passed after the 08-04 changes.

## Residual Risk

The checker, task-flow primitives, delivery guard, runtime audit, and restarted bridge are readiness tooling only until fresh live WeCom UAT proves document+instruction handling, progress, explicit final/timeout/failure/incomplete state, no false completion without artifact, no empty-message answer, fast mid-task follow-up response, and no Hermes meta exposure. Phase 8 acceptance still depends on external five-workday live lawyer trial evidence and human approval.
