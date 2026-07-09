---
phase: 63-qq-rich-media-inbound-egress-p2
plan: 03
subsystem: api
tags: [qqbot, rich-media, egress-06, adapter-deliver, capabilities, tdd]

requires:
  - phase: 63-02
    provides: send_rich_media, upload_rich_media, build_media_envelope, sanitized evidence
  - phase: 62-qq-egress-sender-text-markdown-keyboard
    provides: passive-window gate, FakeMessageTransport, send_message failure metadata style

provides:
  - "adapter.deliver routes file|image after window gate via send_rich_media"
  - "capabilities supports_files=True and supports_images=True (OQ-2)"
  - "Fail-closed missing/invalid file_url with qqbot_rich_media_upload_failed"
  - "Sanitized rich_media evidence merged into DeliveryResult.metadata"

affects:
  - phase-65-live-io
  - phase-67-smoke-evidence

tech-stack:
  added: []
  patterns:
    - "Metadata-only EGRESS-06 routing on frozen ChannelAdapter surface"
    - "Fixture-only rich media requires precomputed file_info when transport not injected"
    - "Evidence allowlist: rich_media_stage, attempts, send_status_code, send_qq_code, file_uuid_hash, ttl, issue_code"

key-files:
  created: []
  modified:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py
    - packages/channels/qqbot/tests/test_qqbot_channel_adapter.py
    - packages/channels/qqbot/tests/test_qqbot_channel_loop.py

key-decisions:
  - "Prefer send_rich_media for live path; fixture-only path fails closed unless metadata supplies precomputed file_info"
  - "Live success envelope in DeliveryResult omits media.file_info (msg_type=7 marker only) to avoid echoing upload tokens"
  - "OQ-2: supports_files/images True now; fixture_only=True / network_io=False until Phase 65"

patterns-established:
  - "Pattern 3: adapter.deliver file/image branch after passive-window gate"
  - "T-63-06: merge only _rich_media_evidence keys into DeliveryResult.metadata"

requirements-completed: [EGRESS-06, EGRESS-05]

duration: 2min
completed: 2026-07-09
---

# Phase 63 Plan 03: Adapter Rich-Media Deliver Summary

**EGRESS-06 reachable via `QQBotChannelAdapter.deliver` for `file`/`image`: window gate → `send_rich_media` → msg_type=7, with capability flags and ADAPTER-04 safety gates green**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-09T10:29:26Z
- **Completed:** 2026-07-09T10:31:29Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- RED adapter tests for capabilities, two-step file deliver, missing URL fail-closed, window-expiry skip upload, image `file_type=1`, and evidence sanitization
- Wired `_deliver_rich_media` after the existing passive-window gate; live path calls `send_rich_media` and merges sanitized evidence
- Set `supports_files=True` / `supports_images=True` while keeping default `fixture_only=True` / `network_io=False`; no WeCom imports; `dependencies=[]`; frozen protocols untouched

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend adapter tests for file/image deliver, evidence, window gate, capabilities** - `6bfe3a8` (test)
2. **Task 2: Wire adapter.deliver file/image path + capabilities; run safety gates** - `d1913fb` (feat)

## Files Created/Modified

- `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py` - EGRESS-06 adapter deliver + capabilities RED/GREEN coverage
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` - file/image deliver branch, capability flags, sanitized evidence merge
- `packages/channels/qqbot/tests/test_qqbot_channel_loop.py` - capabilities fixture expectation aligned with OQ-2

## Decisions Made

- **Fixture-only without transport:** Fail closed unless metadata supplies precomputed `file_info` — do not invent upload tokens for inspection-only paths.
- **Live success metadata:** Include `msg_type=7` envelope marker without embedding live `file_info` / URLs / tokens (T-63-06).
- **Capability advertising:** Files/images supported now; voice remains false; live network still opt-in via injected transport (Phase 65).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Loop capabilities fixture still asserted supports_files=False**
- **Found during:** Task 2 (GREEN)
- **Issue:** `test_qqbot_channel_loop.py` expected pre-OQ-2 capability flags and would fail the full discover suite
- **Fix:** Assert `supports_files`/`supports_images` True and `supports_voice` False
- **Files modified:** `packages/channels/qqbot/tests/test_qqbot_channel_loop.py`
- **Verification:** Full `unittest discover -s packages/channels/qqbot/tests` exit 0
- **Committed in:** `d1913fb` (part of task commit)

---

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** Necessary for OQ-2 consistency; no scope creep.

## Issues Encountered

None beyond the loop-test capability assertion update above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 63 plans 01–03 complete for inbound AttachmentRef + rich-media upload + adapter wiring
- Ready for phase verification / Phase 65 live IO when smoke evidence is needed
- STATE.md / ROADMAP.md intentionally not updated per executor instructions for this run

## TDD Gate Compliance

- RED: `6bfe3a8` — failing adapter file/image deliver tests
- GREEN: `d1913fb` — adapter wiring + capability flags

## Self-Check: PASSED

- FOUND: `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py`
- FOUND: `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py`
- FOUND: `6bfe3a8`
- FOUND: `d1913fb`
- FOUND: `.planning/phases/63-qq-rich-media-inbound-egress-p2/63-03-SUMMARY.md`

---
*Phase: 63-qq-rich-media-inbound-egress-p2*
*Completed: 2026-07-09*
