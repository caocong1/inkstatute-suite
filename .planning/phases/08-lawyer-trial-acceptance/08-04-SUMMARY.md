---
phase: 08-lawyer-trial-acceptance
plan: 08-04
subsystem: wecom-runtime
tags: [wecom, task-flow, active-task-router, progress, output-boundary, live-uat]
requires:
  - phase: 08-lawyer-trial-acceptance
    provides: Phase 8 UAT/report identified long-task task-flow readiness gap
provides:
  - backend-neutral WeCom task-flow stage primitives
  - active-task control-plane router with adapter capability flags
  - live bridge background execution path with service-owned ACK/progress/final/timeout states
  - Phase 8 docs updated with local readiness and live UAT blocker status
affects: [lawyer-trial-acceptance, wecom-service, hermes-agent-adapter, output-boundary, live-uat]
tech-stack:
  added: []
  patterns:
    - service-owned progress notices separate from model reasoning
    - backend-neutral active-task capability routing
    - minimized task event records using hashes, refs, lengths, and counts
key-files:
  created:
    - services/wecom-service/src/wecom_service/task_flow.py
    - services/wecom-service/src/wecom_service/active_task_router.py
    - services/wecom-service/tests/test_task_flow.py
    - services/wecom-service/tests/test_active_task_router.py
    - scripts/inkstatute_wecom_live_bridge.py
  modified:
    - services/wecom-service/src/wecom_service/__init__.py
    - services/wecom-service/src/wecom_service/owned_notices.py
    - services/wecom-service/src/wecom_service/output_policy.py
    - services/wecom-service/tests/test_output_policy.py
    - .planning/phases/08-lawyer-trial-acceptance/08-UAT.md
    - .planning/phases/08-lawyer-trial-acceptance/08-TRIAL-ACCEPTANCE.md
    - .planning/phases/08-lawyer-trial-acceptance/08-LAWYER-TRIAL-RUNBOOK.md
    - .planning/phases/08-lawyer-trial-acceptance/08-REVIEW.md
key-decisions:
  - "Long-running WeCom work now enters an InkStatute-owned task-flow runtime instead of blocking the user acknowledgement path."
  - "Hermes one-shot remains the first backend execution mode, but live update, cancel, streaming progress, and parallel task support are capability-gated and false for this bridge."
  - "Mid-task follow-up messages receive service-owned control-plane responses and are not claimed as applied unless an adapter supports and accepts live task updates."
  - "Task-flow runtime records minimized hashes, lengths, counts, refs, states, and policy metadata, not raw legal payload text."
patterns-established:
  - "Task-flow stages map to platform AsyncTaskState where possible and use ExecutionTrace metadata for service-only stages."
  - "Active-task routing separates status, cancel, update, unsupported update acknowledgement, and future parallel task decisions."
  - "Live readiness docs can record local repair and service restart evidence while keeping live UAT and trial clock blocked."
requirements-completed:
  - REQ-lawyer-trial-acceptance
  - REQ-inkstatute-wecom-service
  - REQ-agent-backend-adapter-contract
  - REQ-assistant-output-boundary
  - REQ-wecom-daily-test-loop
  - REQ-observability-and-replay
duration: 35 min
completed: 2026-06-28
---

# Phase 08 Plan 08-04: WeCom Task Flow And Progress Event Runtime Summary

**Backend-neutral WeCom task-flow runtime with service-owned progress, timeout states, and fast active-task follow-up routing for the live 155 bridge**

## Performance

- **Duration:** 35 min
- **Started:** 2026-06-28T22:21:26+08:00
- **Completed:** 2026-06-28T22:48:44+08:00
- **Tasks:** 4
- **Files modified:** 13

## Accomplishments

- Added `task_flow.py` with the required stages: `received`, `turn_ready`, `queued`, `running`, `progress_notice_due`, `artifact_ready`, `completed`, `failed`, `timeout`, and `cancelled`.
- Added `active_task_router.py` with backend-neutral status, cancel, live update, unsupported update acknowledgement, and future parallel task decisions based on adapter capabilities.
- Refactored the live WeCom bridge so merged turns create background tasks, send one service-owned ACK, emit service-owned progress notices, classify timeout/failure/completion, and route follow-up messages through the fast control plane.
- Updated service-owned notices, output-policy tests, Phase 8 UAT/report/runbook docs, and code review evidence.
- Restarted `inkstatute-wecom-live-bridge.service` for chat `155`; service status was active and connected after restart.

## Task Commits

1. **Task 08-04-01/02: Task-flow contract and active-task routing primitives** - `698b5a4` (feat)
2. **Task 08-04-03: Live bridge background task flow** - `58fba93` (feat)
3. **Task 08-04-04: Verification and Phase 8 docs** - recorded in this plan metadata commit.

## Files Created/Modified

- `services/wecom-service/src/wecom_service/task_flow.py` - task-flow stages, async-state mapping, progress/timeout/idempotency helpers, minimized event records.
- `services/wecom-service/src/wecom_service/active_task_router.py` - fast control-plane routing for follow-up turns during active tasks.
- `services/wecom-service/tests/test_task_flow.py` - task-flow creation, transition, progress, timeout, idempotency, and privacy tests.
- `services/wecom-service/tests/test_active_task_router.py` - active-task status/cancel/update/parallel/privacy tests.
- `services/wecom-service/src/wecom_service/owned_notices.py` - service-owned status/cancel/update/timeout/parallel notices.
- `services/wecom-service/src/wecom_service/__init__.py` - public exports for task-flow and router primitives.
- `services/wecom-service/src/wecom_service/output_policy.py` and `services/wecom-service/tests/test_output_policy.py` - owned lifecycle notice behavior and tests.
- `scripts/inkstatute_wecom_live_bridge.py` - live 155 bridge background execution, progress, timeout, idempotent notices, and active-task follow-up routing.
- `.planning/phases/08-lawyer-trial-acceptance/08-UAT.md` - local repair complete, live task-flow UAT still pending.
- `.planning/phases/08-lawyer-trial-acceptance/08-TRIAL-ACCEPTANCE.md` - readiness gate updated with local evidence and live UAT blocker.
- `.planning/phases/08-lawyer-trial-acceptance/08-LAWYER-TRIAL-RUNBOOK.md` - latest local status and live UAT requirement.
- `.planning/phases/08-lawyer-trial-acceptance/08-REVIEW.md` - code review scope updated for 08-04.

## Verification

- `python -m py_compile scripts/inkstatute_wecom_live_bridge.py services/wecom-service/src/wecom_service/task_flow.py services/wecom-service/src/wecom_service/active_task_router.py` - passed.
- `PYTHONPATH=services/wecom-service/src:packages/platform-contract/src python -m pytest services/wecom-service/tests/test_task_flow.py services/wecom-service/tests/test_active_task_router.py services/wecom-service/tests/test_output_policy.py -q` - 20 tests and 4 subtests passed.
- `PYTHONPATH=services/wecom-service/src:packages/platform-contract/src:packages/contract-test-suite/src python -m pytest services/wecom-service/tests -q` - 31 tests and 7 subtests passed.
- `python scripts/run_v2_gates.py --json-summary` - passed all gates:
  - platform-contract: 15 tests
  - wecom-service: 31 tests
  - hermes-contract-layer: 30 tests
  - conversation-read-view: 18 tests
  - feedback-service: 19 tests
  - phase7-privacy-boundary: 12 tests
  - contract-test-suite: 85 tests
  - compileall: passed
- `systemctl --user restart inkstatute-wecom-live-bridge.service` then status check - service active and connected for chat `155`.

## Decisions Made

- Keep Hermes one-shot as a background adapter execution lane for now; do not turn Hermes gateway into the ordinary-user channel boundary.
- Treat service-owned progress as operational status only; never forward model reasoning as progress.
- Record follow-up input during active tasks as minimized control-plane events and give honest user wording when Hermes cannot accept live updates or cancellation.
- Keep the five-workday trial clock blocked until a fresh live WeCom UAT proves the task-flow behavior.

## Deviations from Plan

None - plan executed exactly as written for local implementation, tests, bridge restart, and docs.

---

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change. Live acceptance remains a human gate.

## Issues Encountered

Live document+instruction UAT was not run by the agent because it requires the operator to send a real WeCom document/instruction and a follow-up message while the task is running. This remains the current human action before the trial clock can start.

## User Setup Required

Operator action required in WeCom:

1. Send a document plus instruction to chat `155`.
2. While the task is still running, send a harmless follow-up such as a status question or supplemental instruction.
3. Confirm one ACK, recurring service-owned progress, explicit final/timeout/failure state, no empty-message answer, no Hermes meta leak, and a fast service-owned follow-up response.

Do not commit runtime logs, callback payloads, media files, generated legal documents, or raw legal text from this UAT.

## Next Phase Readiness

08-04 local repair is complete, but Phase 8 remains `human_needed`. Next step is live WeCom task-flow UAT and then the five-workday lawyer trial evidence collection.

## Self-Check: PASSED

- Task-flow and active-task router files exist and are exported.
- Focused tests, service tests, py_compile, full V2 gates, and code review passed.
- Live bridge was restarted and active after restart.
- `08-UAT.md` and `08-TRIAL-ACCEPTANCE.md` keep trial clock blocked until live evidence passes.
- No runtime logs, callback payloads, media files, customer documents, generated confidential documents, secrets, tokens, or raw legal payloads were committed.

---
*Phase: 08-lawyer-trial-acceptance*
*Completed: 2026-06-28*
