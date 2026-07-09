---
phase: 64-qqbotsessionruntime-qqbotingressruntime
plan: 03
subsystem: qqbot-session-memory
tags: [qqbot, memory, fail-open, memory-orchestrator]

requires:
  - phase: 64-01
    provides: QQBotSessionRuntime CONTINUE/START create_run path
  - phase: 64-02
    provides: ingress + public exports; memory constructor hooks unused until this plan
  - phase: platform-runtime
    provides: MemoryOrchestrator.recall_and_assemble + Memory arecall/aretain
provides:
  - Fail-open MemoryOrchestrator merge into RunRequest.metadata on CONTINUE/START
  - Optional Memory recall summary refs + finalize_memory retain (fail-open)
  - Local QQBotMemoryIntegrationPolicy (D-01 FAIL_OPEN default; FAIL_CLOSED tests-only)
affects: [65 adapter IO, 66 feedback routing, host reply finalization]

tech-stack:
  added: []
  patterns:
    - "QQ wraps MemoryOrchestrator.recall_and_assemble in try/except fail-open (unlike WeCom)"
    - "Local memory policy helpers inside session_runtime.py — no wecom_service import"
    - "finalize_memory is a separate post-reply API; evidence stays refs-only"

key-files:
  created:
    - packages/channels/qqbot/tests/test_session_memory_runtime.py
  modified:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/session_runtime.py

key-decisions:
  - "D-01: default FAIL_OPEN for both Memory and MemoryOrchestrator; FAIL_CLOSED opt-in for tests"
  - "memory_orchestrator_status=degraded on orchestrator exception; create_run still proceeds"
  - "Resume/duplicate/expired/active paths never call MemoryOrchestrator or Memory.arecall"
  - "dependencies=[] unchanged; no wecom_service substring in session_runtime.py"

patterns-established:
  - "RecordingMemoryOrchestrator / FailingMemoryOrchestrator local doubles for SESS-03"
  - "memory_recall_summary uses recalled_count + synthetic memory://recall/{i} refs only"

requirements-completed: [SESS-03]

duration: 10min
completed: 2026-07-09
---

# Phase 64 Plan 03: Session Memory Fail-Open Summary

**QQBotSessionRuntime merges MemoryOrchestrator context refs on CONTINUE/START with D-01 fail-open degradation, optional Memory recall summaries, and post-reply finalize_memory retain — without wecom_service imports or new package dependencies.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-07-09T10:54:46Z
- **Completed:** 2026-07-09T11:05:00Z
- **Tasks:** 2/2
- **Files modified:** 2

## Accomplishments

- Wave 0 RED SESS-03 suite covers orchestrator merge, bypass paths, fail-open, fail_closed opt-in, finalize_memory, and privacy metadata
- CONTINUE/START wires optional Memory recall then `_with_memory_context_fail_open` before `create_run`
- `finalize_memory` retains via optional Memory port (BOTH scope counts); failures return 0 under FAIL_OPEN

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 RED memory runtime tests** - `ef10cd7` (test)
2. **Task 2: Implement fail-open memory + finalize_memory** - `f4ab413` (feat)

**Plan metadata:** (docs SUMMARY commit only; STATE/ROADMAP intentionally not updated per executor instructions)

## Files Created/Modified

- `packages/channels/qqbot/tests/test_session_memory_runtime.py` — SESS-03 orchestrator/Memory/finalize coverage
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/session_runtime.py` — QQBotMemory* policy + fail-open helpers + finalize_memory

## Decisions Made

- Default `QQBotMemoryFailureMode.FAIL_OPEN` for orchestrator and Memory paths; `FAIL_CLOSED` raises for tests only
- On orchestrator exception: set `memory_orchestrator_status=degraded` and proceed to `create_run`
- Memory recall texts never enter metadata — only `recalled_count` and synthetic `memory://recall/{i}` refs
- `finalize_memory` does not write raw reply/turn text into `outcome.evidence`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Finalize success fixture used classifiable English text**
- **Found during:** Task 2 GREEN (test_finalize_memory_success_counts)
- **Issue:** Chinese fixtures without English classifier keywords would be discarded by `MemoryContentClassifier` / default retention categories, yielding retained=0 instead of BOTH-scope count 2
- **Fix:** Use English contract/preference-classifiable turn+reply strings in the success retain test
- **Files modified:** `packages/channels/qqbot/tests/test_session_memory_runtime.py`
- **Commit:** `f4ab413`

## Issues Encountered

None blocking.

## User Setup Required

None — pure in-package orchestration; hosts inject MemoryOrchestrator / Memory and call `finalize_memory` after reply approval.

## Known Stubs

None — memory paths are wired and gated; no TODO/FIXME placeholders.

## Threat Flags

None beyond planned mitigations (T-64-03 fail-open DoS, T-64-05 refs-only metadata, T-64-07 no wecom coupling).

## TDD Gate Compliance

- RED: `ef10cd7` — `test(64-03): add failing test for session memory runtime`
- GREEN: `f4ab413` — `feat(64-03): implement fail-open memory and finalize_memory`

## Verification Results

```text
PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src
python3 -m unittest \
  packages.channels.qqbot.tests.test_session_memory_runtime \
  packages.channels.qqbot.tests.test_session_runtime \
  packages.channels.qqbot.tests.test_ingress_runtime \
  packages.channels.qqbot.tests.test_no_wecom_import \
  packages.channels.qqbot.tests.test_v1_8_safety_baseline \
  packages.channels.qqbot.tests.test_contract_freeze_not_violated -v
→ 56 tests OK
grep wecom_service session_runtime.py → no matches
packages/channels/qqbot/pyproject.toml dependencies = []
```

## Next Plan Notes

- Phase 64 plans complete (01–03). Hosts should call `finalize_memory` after output-policy-approved replies.
- STATE/ROADMAP not updated in this executor run (orchestrator instruction).

## Self-Check: PASSED

- FOUND: `packages/channels/qqbot/tests/test_session_memory_runtime.py`
- FOUND: `packages/channels/qqbot/src/inkstatute_channels_qqbot/session_runtime.py` (`finalize_memory`, `_with_memory_context_fail_open`)
- FOUND: commit `ef10cd7`
- FOUND: commit `f4ab413`
