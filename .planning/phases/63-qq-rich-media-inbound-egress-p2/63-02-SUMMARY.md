---
phase: 63-qq-rich-media-inbound-egress-p2
plan: 02
subsystem: api
tags: [qqbot, rich-media, egress-06, upload, msg-type-7, tdd]

requires:
  - phase: 62-qq-egress-sender-text-markdown-keyboard
    provides: MessageTransport twin, send_message retry/auth, TokenManager reuse
  - phase: 63-01
    provides: inbound AttachmentRef mapping (EGRESS-05)

provides:
  - "wire_files_url_for_scene → /v2/users|groups/{id}/files"
  - "upload_rich_media → file_info + ttl + sanitized evidence"
  - "build_media_envelope msg_type=7 + media.file_info + content=\"\""
  - "send_rich_media two-step upload → send"
  - "Transient QQ codes 304082/304083 in retry map"

affects:
  - 63-03-adapter-deliver-capabilities

tech-stack:
  added: []
  patterns:
    - "Two-step rich media: POST /files → file_info → msg_type=7"
    - "Shared _post_with_retry for send_message and upload_rich_media"
    - "OQ-3 evidence keys: rich_media_stage, attempts, send_status_code, send_qq_code, file_uuid_hash, ttl, issue_code"

key-files:
  created: []
  modified:
    - packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py
    - packages/channels/qqbot/tests/test_sender.py

key-decisions:
  - "Prefer https file_url; file_data only when explicitly passed (fixtures)"
  - "Factor _post_with_retry so upload and send share Phase 62 retry/401 semantics"
  - "Evidence hashes file_uuid to sha256 hex[:16]; never tokens/URLs/file_data"

patterns-established:
  - "Pattern 2: upload_rich_media + build_media_envelope + send_rich_media"
  - "TDD Wave 0: RichMediaUploadTests/RichMediaRetryTests RED before GREEN"

requirements-completed: [EGRESS-06]

duration: 5min
completed: 2026-07-09
---

# Phase 63 Plan 02: Rich Media Egress Upload Summary

**EGRESS-06 two-step rich-media egress: scene-scoped `/files` upload → `file_info` → `msg_type=7` media send, with 304082/304083 retry and sanitized evidence**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-09T10:23:50Z
- **Completed:** 2026-07-09T10:28:50Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Wave 0 RED coverage for media envelope, `/files` URL builder, upload body shape, https fail-closed, 304082/304083 retry, 401 invalidate-once, and sanitized evidence
- `upload_rich_media` / `send_rich_media` / `build_media_envelope` / `wire_files_url_for_scene` / `_rich_media_evidence` implemented on Fake/Urllib `MessageTransport`
- Shared `_post_with_retry` keeps send and upload retry/auth aligned; `dependencies=[]` and no WeCom imports preserved

## Task Commits

Each task was committed atomically:

1. **Task 1: Add RichMediaUploadTests + RichMediaRetryTests + media envelope cases (Wave 0 RED)** - `fab6785` (test)
2. **Task 2: Implement upload, media envelope, retry codes, and send_rich_media** - `d6b1c91` (feat)

## Files Created/Modified

- `packages/channels/qqbot/tests/test_sender.py` - RichMediaUploadTests, RichMediaRetryTests, media envelope assertions
- `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py` - EGRESS-06 upload/send path, transient codes, evidence helper

## Decisions Made

- Prefer host-provided HTTPS `file_url` for DOCX/PDF; accept `file_data` only when explicitly passed for fixtures
- Factor shared `_post_with_retry` so `send_message` and `upload_rich_media` cannot diverge on 401/transient handling
- Evidence keys follow OQ-3: stage/attempts/status/qq_code/`file_uuid_hash`/ttl/issue_code — never Authorization, tokens, URLs, or `file_data`

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

- RED gate: `fab6785` — `test(63-02): add failing rich-media sender tests for EGRESS-06`
- GREEN gate: `d6b1c91` — `feat(63-02): implement EGRESS-06 rich-media upload and msg_type=7 send`

## Known Stubs

None.

## Threat Flags

None — mitigations T-63-03 (sanitized evidence), T-63-04 (https URL + openid validation), T-63-05 (bounded retry) applied as planned; T-63-SC accepted (`dependencies=[]`).

## Verification

```text
PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" \
  python3 -m unittest \
  packages.channels.qqbot.tests.test_sender.SenderEnvelopeTests \
  packages.channels.qqbot.tests.test_sender.RichMediaUploadTests \
  packages.channels.qqbot.tests.test_sender.RichMediaRetryTests \
  packages.channels.qqbot.tests.test_sender.SendRetryTests -v
# → 24 tests OK
```

## Next Plan

Plan 03: adapter `deliver()` file/image path consumes `send_rich_media` / upload helpers; capabilities `supports_files` / `supports_images`.

## Self-Check: PASSED

- FOUND: `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py` (`build_media_envelope`, `upload_rich_media`, `send_rich_media`, `wire_files_url_for_scene`)
- FOUND: `packages/channels/qqbot/tests/test_sender.py` (`RichMediaUploadTests`, `RichMediaRetryTests`)
- FOUND: commit `fab6785`
- FOUND: commit `d6b1c91`
