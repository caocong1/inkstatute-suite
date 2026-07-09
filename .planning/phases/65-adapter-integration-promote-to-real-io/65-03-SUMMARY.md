---
phase: 65-adapter-integration-promote-to-real-io
plan: 03
subsystem: qqbot-adapter
tags: [qqbot, safety, adapter-04, no-wecom, privacy]

requires:
  - phase: 65-01
    provides: two-tier ACK + put_json + _live_io_ready
  - phase: 65-02
    provides: honest live metadata across six Protocol methods
provides:
  - "ADAPTER-03 AST no-wecom coverage across all qqbot production modules"
  - "ADAPTER-03 channel-core allowlist (no new modules)"
  - "ADAPTER-04 freeze: 6-method Protocol + deps=[] + flag default OFF"
  - "T-65-08 privacy gates on live ACK/Delivery metadata"
affects:
  - 66-feedback-interaction-recall
  - 67-live-smoke

tech-stack:
  added: []
  patterns:
    - "channel-core top-level .py allowlist in v1.8 safety baseline"
    - "Package-wide wecom_service AST+substring scan for all qqbot production modules"
    - "Negative privacy helper asserts _assert_no_secrets fails on forbidden keys"

key-files:
  created: []
  modified:
    - packages/channels/qqbot/tests/test_no_wecom_import.py
    - packages/channels/qqbot/tests/test_v1_8_safety_baseline.py
    - packages/channels/qqbot/tests/test_contract_freeze_not_violated.py
    - packages/channels/qqbot/tests/test_adapter_real_io.py

key-decisions:
  - "Enforce channel-core reuse via explicit allowlist of 6 known modules (not mtime/newer baseline)"
  - "Privacy hardened on live Fake ACK (INTERACTION_CREATE) and deliver paths; negative test for helper"
  - "pyproject.toml dependencies=[] confirmed unchanged — no dep adds in Phase 65"

patterns-established:
  - "Pattern: CHANNEL_CORE_ALLOWED_MODULES frozenset in test_v1_8_safety_baseline"
  - "Pattern: live ACK/deliver privacy + assertRaises guard for secret-key leakage"

requirements-completed: [ADAPTER-03, ADAPTER-01]

duration: 2min
completed: 2026-07-09
---

# Phase 65 Plan 03: Safety Freeze + Privacy Summary

**ADAPTER-03/04 safety locked after real-IO promotion: no wecom, channel-core allowlist, Protocol/deps freeze, and T-65-08 metadata privacy**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-09T11:19:11Z
- **Completed:** 2026-07-09T11:20:42Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Extended no-wecom AST suite with package-wide production-module scan (adapter+sender still covered)
- Added channel-core allowlist assertion — Phase 65 created no new channel-core modules
- Hardened freeze (`dependencies=[]`) and live ACK/deliver metadata privacy (T-65-08); full qqbot suite green (283 tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Enforce no-wecom + no new channel-core modules** - `448a477` (test)
2. **Task 2: Freeze Protocol, deps=[], privacy metadata gates** - `21fb5a1` (test)
3. **Task 3: Full qqbot suite regression gate** - verification-only (no code changes; suite OK)

**Plan metadata:** `0c61839` (docs: complete plan)

## Files Created/Modified

- `packages/channels/qqbot/tests/test_no_wecom_import.py` - package-wide wecom_service ban
- `packages/channels/qqbot/tests/test_v1_8_safety_baseline.py` - channel-core allowlist
- `packages/channels/qqbot/tests/test_contract_freeze_not_violated.py` - deps=[] freeze assertion
- `packages/channels/qqbot/tests/test_adapter_real_io.py` - live ACK/deliver privacy + negative helper

## Decisions Made

- Channel-core invariant uses a known-module allowlist (6 `.py` files) rather than filesystem mtime
- Privacy acceptance covers live Fake INTERACTION_CREATE ACK and text deliver metadata dumps
- Confirmed `packages/channels/qqbot/pyproject.toml` still has `dependencies = []`

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

- `test_no_wecom_import` + `test_v1_8_safety_baseline`: OK
- `test_contract_freeze_not_violated` + `test_adapter_real_io` + safety baseline: OK
- Full `unittest discover -s packages/channels/qqbot/tests`: **283 tests OK**
- Quick trio (`two_tier_ack` + `real_io` + `feature_flag`): OK
- `grep wecom_service` under qqbot src: no matches
- No edits under `packages/channel-core/` or `packages/platform-contract/` in this plan

## Known Stubs

None.

## Threat Flags

None — no new trust-boundary surface beyond plan threat model (AST no-wecom, allowlist freeze, metadata privacy).

## Self-Check: PASSED

- FOUND: `packages/channels/qqbot/tests/test_no_wecom_import.py`
- FOUND: `packages/channels/qqbot/tests/test_v1_8_safety_baseline.py`
- FOUND: `packages/channels/qqbot/tests/test_contract_freeze_not_violated.py`
- FOUND: `packages/channels/qqbot/tests/test_adapter_real_io.py`
- FOUND: `448a477`
- FOUND: `21fb5a1`
- FOUND: `dependencies = []` in pyproject.toml
