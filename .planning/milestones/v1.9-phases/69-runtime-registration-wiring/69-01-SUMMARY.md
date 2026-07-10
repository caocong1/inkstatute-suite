---
phase: 69-runtime-registration-wiring
plan: 01
subsystem: qqbot-host
tags: [qqbot, host, wiring, registration, feature-flags]

requires:
  - phase: 68-host-skeleton-safety-baseline
    provides: QQBotHostConfig, resolve_secret_ref, host package skeleton
  - phase: platform-runtime / channels-qqbot
    provides: RuntimeFeatureFlags, QQBotChannelAdapter, DefaultRunRuntime, Fake transports
provides:
  - QQBotWiredRuntime host composition bundle
  - build_qqbot_channel_config flag→enabled mapping
  - build_qqbot_wired_runtime live-injection factory with explicit channels DI
affects:
  - 69-02 runtime registration proofs
  - 69-03 disabled refuse proofs
  - 70 webhook composition

tech-stack:
  added: []
  patterns:
    - "Host-only flag→config mapping (adapter never imports RuntimeFeatureFlags)"
    - "Live transports injected only when flag ON and both deps present; stripped when OFF"

key-files:
  created:
    - services/qqbot-service/src/qqbot_service/wiring.py
    - services/qqbot-service/tests/test_wiring_flag_config.py
  modified:
    - services/qqbot-service/src/qqbot_service/__init__.py
    - services/qqbot-service/README.md

key-decisions:
  - "Channel enabled is driven solely by flags.qqbot_channel_enabled; host_config.enabled cannot override flag False"
  - "When flag OFF, caller-supplied token_manager/transport are stripped before adapter construction"
  - "DefaultRunRuntime already receives channels=(adapter,) so Plan 02 can prove REG-02 without rewrite"

patterns-established:
  - "Pattern: build_qqbot_wired_runtime is the composition root for QQBot host DI"
  - "Pattern: live_io_ready mirrors adapter._live_io_ready() on the frozen bundle"

requirements-completed: [REG-01]

duration: 12min
completed: 2026-07-10
---

# Phase 69 Plan 01: Flag→Config Wiring Factory Summary

**Host factory maps `RuntimeFeatureFlags.qqbot_channel_enabled` onto `QQBotChannelConfig.enabled` and injects Fake/live transports only when the composed path is live-ready**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-10T04:37:49Z
- **Completed:** 2026-07-10T04:40:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- REG-01 dual-knob mapping proven with seven unit tests (True/False/default + live injection rules)
- `QQBotWiredRuntime` bundle exposes flags, host/channel config, adapter, runtime, and `live_io_ready`
- README documents Phase 69 wiring rules; webhook deferred to Phase 70

## Task Commits

1. **Task 1: RED — flag→config mapping and live-injection tests** - `925ac89` (test)
2. **Task 2: GREEN — implement wiring factory and exports** - `91d5235` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified
- `services/qqbot-service/src/qqbot_service/wiring.py` - Composition factory
- `services/qqbot-service/tests/test_wiring_flag_config.py` - REG-01 proofs
- `services/qqbot-service/src/qqbot_service/__init__.py` - Export wiring symbols
- `services/qqbot-service/README.md` - Runtime wiring section

## Decisions Made
- Flag alone drives `channel_config.enabled` (W-03); do not AND with `host_config.enabled` for the minimum REG-01 contract (host.enabled remains available for later env-load AND if operators want it).
- Incomplete live deps (flag ON, missing transport or token_manager) leave both injections `None` so `_live_io_ready()` stays False.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Ready for Plan 02 (REG-02 explicit channels registration) and Plan 03 (HOST-03 disabled refuse) in Wave 2.
- Do not start Phase 70 webhook.

---
*Phase: 69-runtime-registration-wiring*
*Completed: 2026-07-10*

## Self-Check: PASSED
