---
phase: 64-qqbotsessionruntime-qqbotingressruntime
plan: 02
subsystem: qqbot-ingress-runtime
tags: [qqbot, ingress-runtime, normalization, session-runtime]

requires:
  - phase: 64-01
    provides: QQBotSessionRuntime handle_turn + RecordingRuntime patterns
  - phase: 60-qq-event-normalization
    provides: parse_envelope / normalize_message_event / QQBotEventCategory
provides:
  - QQBotRuntimeIngress callback → turn → session runtime wiring
  - SKIPPED_NON_MESSAGE for interaction/validation/unknown
  - Public __init__.py exports for session + ingress (D-02)
  - AST no-wecom gate for ingress_runtime.py
affects: [64-03 memory fail-open, 65 adapter IO, 66 feedback routing]

tech-stack:
  added: []
  patterns:
    - "Ingress composes Phase 60 normalization then Plan 01 session runtime"
    - "Non-message gateway categories return SKIPPED_NON_MESSAGE without create_run/resume"
    - "source=qqbot_ingress_runtime preserved through create_run metadata"

key-files:
  created:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/ingress_runtime.py
    - packages/channels/qqbot/tests/test_ingress_runtime.py
  modified:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/__init__.py
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/session_runtime.py
    - packages/channels/qqbot/tests/test_no_wecom_import.py

key-decisions:
  - "Skip INTERACTION/VALIDATION/UNKNOWN with SKIPPED_NON_MESSAGE (A3); Phase 66 owns feedback"
  - "Export QQBotSessionRuntime + QQBotRuntimeIngress from __init__.py (D-02 / OQ-2)"
  - "Preserve RunRequest.metadata.source from ingress when session runtime merges decision metadata"

patterns-established:
  - "Fixture-driven ingress tests load packages/channels/qqbot/fixtures envelopes"
  - "RecordingRuntime.resumed list mirrors WeCom ingress test shape locally"

requirements-completed: [SESS-01, SESS-02]

duration: 15min
completed: 2026-07-09
---

# Phase 64 Plan 02: QQBotRuntimeIngress Summary

**Host-callable QQBotRuntimeIngress maps sanitized C2C/GROUP_AT envelopes through Phase 60 normalization into QQBotSessionRuntime, skips non-message categories, and exports public session/ingress surfaces without wecom_service coupling.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-09T10:51:58Z
- **Completed:** 2026-07-09T11:06:00Z
- **Tasks:** 2/2
- **Files modified:** 5

## Accomplishments

- Wave 0 RED ingress tests cover C2C/GROUP wiring, resume-via-ingress, interaction/validation skip, and privacy metadata
- `QQBotRuntimeIngress.handle_callback` wires parse/normalize → SessionScope/RunRequest → `handle_turn`
- Additive `SKIPPED_NON_MESSAGE` action; `__init__.py` exports session + ingress (D-02); AST gate covers `ingress_runtime.py`

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 RED ingress tests + AST gate** - `2e3aa88` (test)
2. **Task 2: Implement QQBotRuntimeIngress + public exports** - `6239caa` (feat)

**Plan metadata:** (pending docs commit for SUMMARY only; STATE/ROADMAP intentionally not updated)

## Files Created/Modified

- `packages/channels/qqbot/src/inkstatute_channels_qqbot/ingress_runtime.py` — QQBotRuntimeIngress
- `packages/channels/qqbot/tests/test_ingress_runtime.py` — callback wiring + skip + resume + privacy
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/__init__.py` — D-02 public exports
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/session_runtime.py` — SKIPPED_NON_MESSAGE + preserve ingress source
- `packages/channels/qqbot/tests/test_no_wecom_import.py` — AST coverage for ingress_runtime.py

## Decisions Made

- Non-message categories return skip outcome with `ingress_status=skipped_non_message` and never call create_run/resume
- Session runtime `_run_metadata_for_decision` keeps existing `source` (ingress) instead of always overwriting to `qqbot_session_runtime`
- No adapter Protocol IO, no FeedbackEvent session turns, no new pyproject dependencies

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — pure in-package orchestration; no secrets or external services.

## Known Stubs

None — memory constructor hooks remain unused until Plan 03 (intentional).

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary schemas beyond the planned injectable ingress seam.

## Verification Results

```text
PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src
python3 -m unittest packages.channels.qqbot.tests.test_ingress_runtime packages.channels.qqbot.tests.test_session_runtime packages.channels.qqbot.tests.test_no_wecom_import -v
→ 35 tests OK
grep wecom_service ingress_runtime.py __init__.py → no matches
```

## Next Plan Notes

- Plan 03: fail-open MemoryOrchestrator recall + `finalize_memory` (SESS-03)

## Self-Check: PASSED

- FOUND: `packages/channels/qqbot/src/inkstatute_channels_qqbot/ingress_runtime.py`
- FOUND: `packages/channels/qqbot/tests/test_ingress_runtime.py`
- FOUND: `packages/channels/qqbot/src/inkstatute_channels_qqbot/__init__.py` (exports QQBotRuntimeIngress)
- FOUND: commit `2e3aa88`
- FOUND: commit `6239caa`
- FOUND: `.planning/phases/64-qqbotsessionruntime-qqbotingressruntime/64-02-SUMMARY.md`
