---
phase: 75-channel-config-apply
plan: 04
subsystem: channels
tags: [wecom, dual-knob, operator-config, from_operator_doc, channel_wiring]

requires:
  - phase: 75-01
    provides: wecom_channel_enabled flag + Wave 0 RED scaffolds for from_operator_doc / dual-knob
provides:
  - WeComChannelConfig.from_operator_doc (host/doc materializer, flag-free)
  - wecom_service.channel_wiring build_wecom_channel_config dual-knob AND
  - load_wecom_channel_config store-wins-if-exists with env fallback
  - README restart-to-apply semantics
affects: [75-05 admin channels SSR, wecom host startup apply]

tech-stack:
  added: []
  patterns:
    - "Adapter from_operator_doc maps host knob only; host wiring ANDs platform flag"
    - "Store path.exists → store doc; else from_env (OQ-1)"

key-files:
  created:
    - services/wecom-service/src/wecom_service/channel_wiring.py
  modified:
    - packages/channels/wecom/src/inkstatute_channels_wecom/config.py
    - services/wecom-service/src/wecom_service/__init__.py
    - services/wecom-service/tests/test_channel_wiring_dual_knob.py
    - services/wecom-service/README.md

key-decisions:
  - "Dual-knob AND lives in wecom-service channel_wiring; channel package stays flag-free"
  - "enabled = wecom_channel_enabled AND doc.enabled (never channel_delivery_enabled)"
  - "Store wins when OperatorConfigStore.path.exists; env is bootstrap fallback only"

patterns-established:
  - "WeCom mirror of QQ build_*_channel_config dual-knob in thin channel_wiring module"
  - "from_operator_doc accepts Mapping or doc object to avoid operator-config dep in channel package"

requirements-completed: [CHAN-02, CHAN-03]

duration: 2min
completed: 2026-07-10
---

# Phase 75 Plan 04: WeCom from_operator_doc + channel_wiring Summary

**WeCom host/doc materializer plus dual-knob AND wiring with store-wins-if-exists load, matching QQ apply parity.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-10T08:25:03Z
- **Completed:** 2026-07-10T08:27:00Z
- **Tasks:** 2/2
- **Files modified:** 5

## Accomplishments

- Added `WeComChannelConfig.from_operator_doc` mapping enabled + token/aes/corp refs without importing feature flags
- Added `build_wecom_channel_config` / `load_wecom_channel_config` with fail-closed dual-knob AND and store-first load
- Documented restart-to-apply and deploy-owned platform flag in wecom-service README

## Task Commits

Each task was committed atomically:

1. **Task 1: WeComChannelConfig.from_operator_doc (channel package)** - `a6245bc` (feat)
2. **Task 2: wecom-service channel_wiring dual-knob + load helper** - `6145e86` (feat)

**Plan metadata:** `a7722c9` (docs: complete plan)

_Note: Wave 0 RED scaffolds landed in 75-01; this plan greened them (TDD GREEN commits)._

## Files Created/Modified

- `packages/channels/wecom/src/inkstatute_channels_wecom/config.py` — `from_operator_doc` materializer
- `services/wecom-service/src/wecom_service/channel_wiring.py` — dual-knob build + store/env load
- `services/wecom-service/src/wecom_service/__init__.py` — export public wiring helpers
- `services/wecom-service/tests/test_channel_wiring_dual_knob.py` — AND matrix + store/env load proofs
- `services/wecom-service/README.md` — restart-to-apply + dual-knob notes

## Decisions Made

- Dual-knob composition stays in wecom-service (resolved OQ-2); adapter package remains flag-free
- Platform knob is exclusively `wecom_channel_enabled` (not `channel_delivery_enabled`)
- Load precedence: store file exists → store wecom doc; else env `from_env` then AND

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Added store/env load proofs to dual-knob tests**
- **Found during:** Task 2 (channel_wiring)
- **Issue:** Wave 0 scaffold covered build matrix only; must_haves required store/env load proofs
- **Fix:** Added `test_load_wecom_channel_config_store_wins_when_path_exists` and env-fallback case
- **Files modified:** `services/wecom-service/tests/test_channel_wiring_dual_knob.py`
- **Verification:** `python -m unittest services.wecom-service.tests.test_channel_wiring_dual_knob -q` (5 OK)
- **Committed in:** `6145e86` (part of task commit)

---

**Total deviations:** 1 auto-fixed (Rule 2)
**Impact on plan:** Strengthened verification for OQ-1 load precedence; no scope creep beyond plan must_haves.

## Issues Encountered

- Transient `.git/index.lock` from parallel Phase 75 plans; retried commit after lock cleared
- Left parallel-plan edits (`config_api.py`, qqbot wiring) untouched per executor scope

## User Setup Required

None — no external services or secrets required for this plan.

## Next Phase Readiness

- WeCom apply helpers ready for host startup callers and 75-05 SSR effective display
- Do not claim live WeCom UAT or carried Phase 5/8 / QQ `--live` gates

## Known Stubs

None — helpers materialize real refs/enabled; no placeholder enablement paths.

## Threat Flags

None — no new network endpoints or auth surfaces; refs-only materialize (T-75-08/09 mitigated as planned).

## Self-Check: PASSED

- `packages/channels/wecom/src/inkstatute_channels_wecom/config.py` — FOUND
- `services/wecom-service/src/wecom_service/channel_wiring.py` — FOUND
- `services/wecom-service/tests/test_channel_wiring_dual_knob.py` — FOUND
- `75-04-SUMMARY.md` — FOUND
- Commits `a6245bc`, `6145e86` — FOUND
