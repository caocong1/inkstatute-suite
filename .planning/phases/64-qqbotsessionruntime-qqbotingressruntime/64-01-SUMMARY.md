---
phase: 64-qqbotsessionruntime-qqbotingressruntime
plan: 01
subsystem: qqbot-session-runtime
tags: [qqbot, session-runtime, interrupt, scene-aware]

requires:
  - phase: 60-qq-event-normalization
    provides: scene-aware conversation_id qqbot:{scene}:{scene_id}:{user_openid}
  - phase: platform-runtime
    provides: RunRuntime, resolve_session_turn, InMemoryInterruptStore, SessionScope
provides:
  - QQBotSessionRuntime composing platform_runtime for CONTINUE/START/RESUME/ACTIVE_TASK
  - Scene-isolated interrupt resume (C2C vs group)
  - AST no-wecom gate for session_runtime.py
affects: [64-02 ingress runtime, 64-03 memory fail-open]

tech-stack:
  added: []
  patterns:
    - "Channel-local session runtime mirrors WeCom decision graph without importing wecom_service"
    - "ACTIVE_TASK_FOLLOW_UP returns evidence only (no notice router)"
    - "source=qqbot_session_runtime metadata on create_run requests"

key-files:
  created:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/session_runtime.py
    - packages/channels/qqbot/tests/test_session_runtime.py
  modified:
    - packages/channels/qqbot/tests/test_no_wecom_import.py

key-decisions:
  - "Compose platform_runtime only; never import wecom_service"
  - "ACTIVE_TASK path is outcome/evidence only — no active_task_router"
  - "Memory/MemoryOrchestrator constructor hooks stored unused until Plan 03"
  - "RunRequest metadata source=qqbot_session_runtime"

patterns-established:
  - "RecordingRuntime local fake for create_run vs resume_interrupt assertions"
  - "SceneIsolationTests prove conversation_id partitions interrupt resume"

requirements-completed: [SESS-01, SESS-02]

duration: 12min
completed: 2026-07-09
---

# Phase 64 Plan 01: QQBotSessionRuntime Summary

**Injectable QQBotSessionRuntime orchestrates create_run / resume_interrupt via platform_runtime with scene-aware interrupt isolation and zero wecom_service coupling.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-09T10:48:33Z
- **Completed:** 2026-07-09T11:00:00Z
- **Tasks:** 2/2
- **Files modified:** 3

## Accomplishments

- Wave 0 RED tests cover continue, start, resume, duplicate, expiry, active-task outcome-only, scope mismatch, and C2C/group scene isolation
- `QQBotSessionRuntime.handle_turn` implements the WeCom-analog decision graph using only `platform_runtime`
- AST + substring gates ensure `session_runtime.py` never references wecom_service; `dependencies = []` unchanged

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 RED session runtime + no-wecom AST gate** - `53277a2` (test)
2. **Task 2: Implement QQBotSessionRuntime core orchestration** - `baa2d90` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `packages/channels/qqbot/src/inkstatute_channels_qqbot/session_runtime.py` — QQBotSessionRuntime + Action/Outcome
- `packages/channels/qqbot/tests/test_session_runtime.py` — RecordingRuntime + SceneIsolationTests
- `packages/channels/qqbot/tests/test_no_wecom_import.py` — AST coverage for session_runtime.py

## Decisions Made

- Followed plan: compose `platform_runtime` only; skip WeCom active_task_router and memory_integration
- Memory constructor fields accepted and stored for Plan 03; unused on create path in this plan
- ACTIVE_TASK_FOLLOW_UP returns decision evidence without create_run/resume_interrupt

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Start-session fixture text matched new_task_signal**
- **Found during:** Task 2 (GREEN verification)
- **Issue:** Test used `"新任务：起草一个通知"` while asserting `session_resolution_reason == "no_recent_session"`; resolver correctly classified as `new_task_signal`
- **Fix:** Changed turn text to a non-new-task phrase so the no-recent-session path is exercised
- **Files modified:** `packages/channels/qqbot/tests/test_session_runtime.py`
- **Verification:** Full unittest suite green (27 tests)
- **Committed in:** `baa2d90` (part of task commit)

---

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** Correctness-only test fixture fix; no scope creep

## Issues Encountered

None beyond the fixture text mismatch above.

## User Setup Required

None — pure in-package orchestration; no secrets or external services.

## Known Stubs

None — memory hooks are intentionally unused until Plan 03 (constructor stores fields; no placeholder UI/data paths).

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary schemas beyond the planned injectable orchestration seam.

## Verification Results

```text
PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src
python3 -m unittest packages.channels.qqbot.tests.test_session_runtime packages.channels.qqbot.tests.test_no_wecom_import -v
→ 27 tests OK
grep wecom_service session_runtime.py → no matches
dependencies = [] unchanged
```

## Next Plan Notes

- Plan 02: `ingress_runtime.py` + public `__init__.py` exports (D-02)
- Plan 03: fail-open MemoryOrchestrator recall + `finalize_memory`

## Self-Check: PASSED

- FOUND: `packages/channels/qqbot/src/inkstatute_channels_qqbot/session_runtime.py`
- FOUND: `packages/channels/qqbot/tests/test_session_runtime.py`
- FOUND: `packages/channels/qqbot/tests/test_no_wecom_import.py` (AST methods)
- FOUND: commit `53277a2`
- FOUND: commit `baa2d90`
