---
phase: 66-feedback-loop-parity-interaction-recall
plan: 03
subsystem: api
tags: [qqbot, wakeup, recall, egress, unittest]

requires:
  - phase: 66-02
    provides: FEEDBACK-01/02 parity + ensure_interaction_ack; Wave 0 RED test_wakeup_recall scaffold
  - phase: 62
    provides: sender envelopes, check_passive_reply_window, FakeMessageTransport, send_message
provides:
  - C2C is_wakeup wakeup envelope builders with msg_id/event_id mutual exclusion
  - Injectable InMemoryWakeupPeriodStore + check_wakeup_quota (Asia/Shanghai P0–P3, 1/period)
  - adapter.deliver over-window wakeup branch with group fail-closed
  - ADAPTER-04 safety gates green (no wecom, deps=[], freeze intact)
affects:
  - Phase 67 live smoke / TZ confirmation
  - Host injection of durable WakeupPeriodStore

tech-stack:
  added: []
  patterns:
    - "Wakeup builders never call _base_envelope; is_wakeup=True omits msg_id/event_id/msg_seq"
    - "Period gate: Asia/Shanghai calendar days; half-open P0–P3; injectable store+clock+tz"
    - "deliver: passive window fail + allow_wakeup/is_wakeup → _deliver_wakeup (C2C only)"

key-files:
  created: []
  modified:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py
    - packages/channels/qqbot/tests/test_wakeup_recall.py

key-decisions:
  - "OQ-2: period calendar TZ defaults to Asia/Shanghai (injectable ZoneInfo)"
  - "Half-open periods: P0 day_delta==0; P1 1..3; P2 3<d<=7; P3 7<d<=30"
  - "Missing store basis on allow_wakeup defaults to note_user_message(now) so P0 applies"
  - "Adapter accepts optional wakeup_store ctor + metadata.wakeup_store / wakeup_clock / last_user_message_at"

patterns-established:
  - "Pattern: dedicated build_wakeup_* envelopes + strip_for_wire keeps mutual exclusion"
  - "Pattern: wakeup_scene_supported(scene)==c2c only; group → qqbot_wakeup_unsupported_scene"
  - "Pattern: DeliveryResult metadata records is_wakeup + wakeup_period_id; never Authorization/tokens"

requirements-completed: [RECALL-01, ADAPTER-04]

duration: 2min
completed: 2026-07-09
---

# Phase 66 Plan 03: Interaction Recall (is_wakeup) Summary

**C2C `is_wakeup` over-window recall with Asia/Shanghai 30-day period gating (1/period), group fail-closed, and ADAPTER-04 safety gates green**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-09T11:48:51Z
- **Completed:** 2026-07-09T11:51:17Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Wakeup text/markdown envelopes set `is_wakeup=True` and omit `msg_id`/`event_id`/`msg_seq`; `strip_for_wire` preserves mutual exclusion
- `InMemoryWakeupPeriodStore` + `check_wakeup_quota` enforce P0–P3 (1 send per openid/period); second same-period send → `qqbot_wakeup_quota_exhausted`
- `adapter.deliver` routes over-window `allow_wakeup`/`is_wakeup` to `_deliver_wakeup`; group → `qqbot_wakeup_unsupported_scene`; no-flag expiry still `qqbot_passive_reply_window_expired`
- Phase quick suite + no-wecom / contract-freeze / v1.8 baseline green; both pyprojects `dependencies = []`

## Task Commits

Each task was committed atomically:

1. **Task 1: Wakeup envelopes + period gate in sender (RECALL-01)** - `1f7510f` (feat)
2. **Task 2: adapter.deliver wakeup branch + scene fail-closed** - `0322a16` (feat)
3. **Task 3: ADAPTER-04 safety gates + phase quick suite** - verification only (no code changes)

**Plan metadata:** (docs commit after this file)

## Files Created/Modified
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py` - Wakeup builders, period enum/store/quota, `wakeup_scene_supported`
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` - `_deliver_wakeup` + injectable `wakeup_store`
- `packages/channels/qqbot/tests/test_wakeup_recall.py` - Green envelope/period/adapter deliver coverage (+ group + no-wakeup expiry)

## Decisions Made
- Period day labels use injectable `tz` defaulting to `Asia/Shanghai` (OQ-2 RESOLVED)
- Half-open day-delta mapping: P0 `==0`, P1 `1..3`, P2 `(3,7]`, P3 `(7,30]`; outside → `qqbot_wakeup_outside_window`
- When host sets `allow_wakeup` without a prior `note_user_message`, adapter seeds basis to `now` (P0) so long-task completion can send once
- Host may inject durable store via ctor `wakeup_store=` or per-delivery `metadata.wakeup_store`

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written.

**Note:** Task 2 extended `test_wakeup_recall.py` with explicit group-unsupported and no-wakeup-expiry adapter cases (acceptance criteria) beyond the single Wave 0 RED adapter test — still within Task 2 scope.

## Threat Flags

None — no new network endpoints, auth paths, or freeze-surface edits beyond planned wakeup send on existing C2C `/messages` path. Tokens remain out of `DeliveryResult.metadata`.

## Known Stubs

None — wakeup path is fully wired for Fake transport / live IO when enabled.

## Verification Results
- `TestWakeupEnvelope` + `TestWakeupPeriodGate` green (Task 1)
- Full `test_wakeup_recall` + `test_sender` green (Task 2)
- Quick suite: feedback pipeline/idempotency/wakeup + no-wecom + contract-freeze + v1.8 baseline → 53 tests OK
- `grep dependencies`: both packages `dependencies = []`
- No platform-contract / channel-core / Protocol files modified

## Self-Check: PASSED

- FOUND: `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py`
- FOUND: `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`
- FOUND: `packages/channels/qqbot/tests/test_wakeup_recall.py`
- FOUND: commit `1f7510f`
- FOUND: commit `0322a16`
