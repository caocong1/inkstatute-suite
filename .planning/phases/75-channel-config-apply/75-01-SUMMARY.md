---
phase: 75-channel-config-apply
plan: 01
subsystem: channel-config
tags: [wecom_channel_enabled, feature-flags, contract-freeze, wave0-scaffolds, dual-knob]

requires:
  - phase: 74-admin-config-api-rbac
    provides: "/config/* API + RBAC + operator_config_src on admin gates"
provides:
  - "RuntimeFeatureFlags.wecom_channel_enabled default OFF (CHAN-03 WeCom platform knob)"
  - "Contract freeze exact-set includes wecom_channel_enabled"
  - "qqbot-service + wecom-service gate PYTHONPATH includes operator_config_src"
  - "Wave 0 failing scaffolds for Plans 02–05"
affects: [75-02, 75-03, 75-04, 75-05]

tech-stack:
  added: []
  patterns:
    - "WeCom platform dual-knob mirrors qqbot_channel_enabled (not channel_delivery_enabled)"
    - "Wave 0 scaffolds fail with clear Plan N messages until later waves green them"
    - "Host service gates gain operator_config_src without adding package dependencies"

key-files:
  created:
    - services/admin-console-api/tests/test_config_channels_effective.py
    - services/qqbot-service/tests/test_store_apply.py
    - packages/channels/wecom/tests/test_from_operator_doc.py
    - services/wecom-service/tests/test_channel_wiring_dual_knob.py
    - services/admin-web-ui/tests/test_channels_form.py
  modified:
    - packages/platform-runtime/src/platform_runtime/feature_flags.py
    - packages/platform-runtime/tests/test_feature_flags.py
    - services/admin-console-api/tests/test_contract_freeze.py
    - scripts/run_v2_gates.py

key-decisions:
  - "wecom_channel_enabled placed next to qqbot_channel_enabled; never reuse channel_delivery_enabled"
  - "Wave 0 scaffolds intentionally fail under discover until Plans 02–05 implement production code"
  - "operator_config_src added only to qqbot-service and wecom-service gates (admin gates already covered in Phase 74)"

patterns-established:
  - "WeComChannelFeatureFlagTests mirrors OperatorConfigFeatureFlagTests for new platform knobs"
  - "Scaffold tests use self.fail with Plan N messages on missing symbols"

requirements-completed: [CHAN-03]

duration: 4min
completed: 2026-07-10
---

# Phase 75 Plan 01: Channel Config Wave 0 Foundation Summary

**Default-OFF `wecom_channel_enabled` with freeze + host-gate PYTHONPATH, plus five failing Wave 0 scaffolds for Plans 02–05.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-07-10T08:20:24Z
- **Completed:** 2026-07-10T08:23:31Z
- **Tasks:** 2/2
- **Files modified:** 9

## Accomplishments

- Added `wecom_channel_enabled: bool = False` on `RuntimeFeatureFlags` (CHAN-03 WeCom platform knob parity with QQ)
- Updated contract freeze exact-set allowlist and bumped `operator_config_src` gate count assertion to ≥7
- Extended qqbot-service and wecom-service V2 gate PYTHONPATHs with `operator_config_src` for store-backed apply tests
- Landed five Wave 0 scaffold modules documenting effective API, QQ store apply, WeCom dual-knob, and SSR form expectations

## Task Commits

Each task was committed atomically:

1. **Task 1: Add wecom_channel_enabled + freeze + host gate PYTHONPATH**
   - `adc103f` (test) — RED: WeComChannelFeatureFlagTests + freeze expect wecom + operator_config_src ≥7
   - `cf2430b` (feat) — GREEN: flag field + qqbot/wecom gate PYTHONPATH
2. **Task 2: Wave 0 test scaffolds** — `5d0067b` (test)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `packages/platform-runtime/src/platform_runtime/feature_flags.py` — `wecom_channel_enabled` default False
- `packages/platform-runtime/tests/test_feature_flags.py` — WeComChannelFeatureFlagTests
- `services/admin-console-api/tests/test_contract_freeze.py` — exact-set + gate count ≥7
- `scripts/run_v2_gates.py` — operator_config_src on qqbot-service and wecom-service
- `services/admin-console-api/tests/test_config_channels_effective.py` — Plan 02 scaffold (effective + restart_required)
- `services/qqbot-service/tests/test_store_apply.py` — Plan 03 scaffold (store-wins / env fallback)
- `packages/channels/wecom/tests/test_from_operator_doc.py` — Plan 04 scaffold (from_operator_doc)
- `services/wecom-service/tests/test_channel_wiring_dual_knob.py` — Plan 04 scaffold (AND matrix)
- `services/admin-web-ui/tests/test_channels_form.py` — Plan 05 scaffold (SSR form + proxy_put)

## Decisions Made

- Platform WeCom knob is `wecom_channel_enabled`, not `channel_delivery_enabled` (RESEARCH / threat T-75-01)
- Scaffolds fail loudly with Plan N messages so Wave 2+ TDD turns them green; no production apply/API/UI code in this plan
- Carried human gates must not be auto-closed — scaffold includes an explicit non-claim assertion

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Preview

Plans 02–05 (same phase): channels effective API, QQ store apply, WeCom dual-knob wiring, SSR channels form — turn Wave 0 scaffolds green.

## Self-Check: PASSED

- FOUND: all 9 key files
- FOUND: adc103f, cf2430b, 5d0067b
