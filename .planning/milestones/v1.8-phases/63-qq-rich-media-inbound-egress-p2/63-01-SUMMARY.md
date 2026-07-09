---
phase: 63-qq-rich-media-inbound-egress-p2
plan: 01
subsystem: api
tags: [qqbot, attachment-ref, normalization, egress-05, reference-only, tdd]

requires:
  - phase: 60-qqbot-channel-foundation
    provides: text-only normalize_message_event + C2C/GROUP_AT fixtures
  - phase: platform-contract
    provides: frozen AttachmentRef + MessageType (no video)

provides:
  - "_attachments_from_event → AttachmentRef with qqbot-media:// URIs"
  - "message_type derivation (image/voice/file; video kind → file)"
  - "voice ASR passthrough when content empty"
  - "C2C/GROUP_AT attachment fixtures + AttachmentRefTests"

affects:
  - 63-02-rich-media-egress-upload
  - 63-03-adapter-deliver-capabilities

tech-stack:
  added: []
  patterns:
    - "Reference-only AttachmentRef: opaque qqbot-media://{id}, never live URL/bytes"
    - "content_type → kind mapping; video kind preserved, message_type maps to file"

key-files:
  created:
    - packages/channels/qqbot/fixtures/qqbot_c2c_message_with_attachments.json
    - packages/channels/qqbot/fixtures/qqbot_group_at_message_with_attachments.json
  modified:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py
    - packages/channels/qqbot/tests/test_normalization.py

key-decisions:
  - "Video AttachmentRef.kind stays video; AgentTurn.message_type maps to file (OQ-1)"
  - "Empty content + voice asr_refer_text copies ASR into AgentTurn.content"
  - "Live QQ url hashed into attachment_id only; never stored on uri/metadata"

patterns-established:
  - "Pattern 1: _attachments_from_event skips non-Mapping items; metadata.source_status=media_reference_only"
  - "TDD Wave 0: fixtures + AttachmentRefTests RED before normalization GREEN"

requirements-completed: [EGRESS-05]

duration: 1min
completed: 2026-07-09
---

# Phase 63 Plan 01: Inbound AttachmentRef Mapping Summary

**EGRESS-05 inbound rich-media normalization: QQ `attachments[]` → frozen `AttachmentRef` with opaque `qqbot-media://` URIs, no live URLs/bytes, message_type derivation, and ASR passthrough**

## Performance

- **Duration:** 1 min
- **Started:** 2026-07-09T10:21:47Z
- **Completed:** 2026-07-09T10:23:07Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Synthetic C2C (image/voice/file/video) and GROUP_AT (image + @-strip) attachment fixtures with sanitized markers
- `AttachmentRefTests` lock reference-only privacy, message_type mapping (video→file), ASR passthrough, schema validation, and malformed-item skip
- `_attachments_from_event` / `_attachment_ref_from_qq` wired into `normalize_message_event`; empty attachments remain `message_type=text`

## Task Commits

Each task was committed atomically:

1. **Task 1: Add attachment fixtures + AttachmentRefTests (Wave 0 RED)** - `9f490dd` (test)
2. **Task 2: Implement AttachmentRef mapping in normalization.py** - `667f0a2` (feat)

## Files Created/Modified

- `packages/channels/qqbot/fixtures/qqbot_c2c_message_with_attachments.json` - C2C envelope with four synthetic attachments
- `packages/channels/qqbot/fixtures/qqbot_group_at_message_with_attachments.json` - GROUP_AT envelope with image + @-prefix
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py` - AttachmentRef helpers + normalize wiring
- `packages/channels/qqbot/tests/test_normalization.py` - `AttachmentRefTests` class

## Decisions Made

- Followed OQ-1: video kind on AttachmentRef, message_type `file`
- ASR text fills `content` only when inbound content is empty
- No wecom imports; no platform-contract / channel-core edits; `dependencies=[]` unchanged

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 can implement rich-media upload/send in `sender.py` against reference-only inbound AttachmentRefs
- Plan 03 wires `adapter.deliver` file/image path and capabilities flags
- STATE.md / ROADMAP.md intentionally not updated per executor instructions

## TDD Gate Compliance

- RED: `9f490dd` — `test(63-01): add failing AttachmentRefTests for EGRESS-05`
- GREEN: `667f0a2` — `feat(63-01): map QQ attachments to reference-only AttachmentRef`

## Self-Check: PASSED

- FOUND: fixtures, normalization.py, test_normalization.py
- FOUND: commits `9f490dd`, `667f0a2`
- AttachmentRefTests + NormalizeMessageEventTests: 15 OK
- `wecom_service` absent from normalization.py; platform-contract unmodified

---
*Phase: 63-qq-rich-media-inbound-egress-p2*
*Completed: 2026-07-09*
