---
phase: 63-qq-rich-media-inbound-egress-p2
verified: 2026-07-09T10:32:57Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 63: QQ Rich Media Inbound + Egress (P2) Verification Report

**Phase Goal:** QQ Bot rich media inbound (image/voice/video/file `attachments[]`) is parsed into `AttachmentRef` records with reference-only policy; rich media egress uses two-step upload for DOCX/PDF legal document delivery with retry and evidence collection.
**Verified:** 2026-07-09T10:32:57Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `attachments[]` (image/voice/video/file) parse into `AttachmentRef` with reference-only policy (`raw_payload_ref`, no raw payload storage) | ✓ VERIFIED | `_attachments_from_event` / `_attachment_ref_from_qq` in `normalization.py`; URI `qqbot-media://{id}`; metadata `source_status=media_reference_only`, `bytes_stored=False`; live `url` hashed for id only. Fixtures cover image/voice/file/video. `AttachmentRefTests` green. |
| 2 | Two-step upload (`POST /v2/.../files` → `file_info` → `msg_type=7`) for DOCX/PDF delivery | ✓ VERIFIED | `wire_files_url_for_scene` → `/v2/users\|groups/{id}/files`; `upload_rich_media` default `file_type=4`; `build_media_envelope` emits `msg_type=7` + `media.file_info`; `send_rich_media` composes upload→send. Adapter live path calls `send_rich_media`. |
| 3 | Retry and evidence collection for rich media egress failures | ✓ VERIFIED | `_TRANSIENT_QQ_CODES` includes 304082/304083; shared `_post_with_retry` with Phase 62 backoff + 401 invalidate-once; `_rich_media_evidence` keys only (`rich_media_stage`, `attempts`, `send_status_code`, `send_qq_code`, `file_uuid_hash`, `ttl`, `issue_code`). `RichMediaRetryTests` green. |
| 4 | `adapter.deliver` routes `file`/`image` through passive-window gate then upload→`msg_type=7` when transport+token injected | ✓ VERIFIED | Window gate runs before `_deliver_rich_media`; missing/invalid URL → `qqbot_rich_media_upload_failed`; window expiry → `interim_notice` with `call_count==0`; image defaults `file_type=1`. Adapter deliver tests green. |
| 5 | Capabilities advertise `supports_files=True` / `supports_images=True`; default `fixture_only`/`network_io` semantics preserved | ✓ VERIFIED | `capabilities()` sets both True; `supports_voice=False`; defaults `fixture_only=True`, `network_io=False` until live send. |
| 6 | No `wecom_service` imports; `dependencies=[]`; frozen protocols/schemas/channel-core untouched | ✓ VERIFIED | `test_no_wecom_import`, `test_v1_8_safety_baseline`, `test_contract_freeze_not_violated` all green; pyproject `dependencies = []`. |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py` | attachments[] → AttachmentRef reference-only | ✓ VERIFIED | `_attachments_from_event` present; wired into `normalize_message_event`; 418 lines |
| `packages/channels/qqbot/fixtures/qqbot_c2c_message_with_attachments.json` | C2C fixture with image/voice/file/video | ✓ VERIFIED | 4 attachments: image/jpeg, voice, file, video/mp4 |
| `packages/channels/qqbot/fixtures/qqbot_group_at_message_with_attachments.json` | GROUP_AT fixture with attachment | ✓ VERIFIED | 1 image/png attachment |
| `packages/channels/qqbot/tests/test_normalization.py` | `AttachmentRefTests` | ✓ VERIFIED | 6 tests covering URI, privacy, message_type, ASR, schema, skip |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py` | upload + media envelope + send_rich_media | ✓ VERIFIED | All exports present; 304082/304083 in transient set; 870 lines |
| `packages/channels/qqbot/tests/test_sender.py` | RichMediaUploadTests / RichMediaRetryTests | ✓ VERIFIED | Classes + `test_build_media_envelope_msg_type_7` present |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` | deliver file/image + capability flags | ✓ VERIFIED | `send_rich_media` import; `_deliver_rich_media`; supports_files/images True |
| `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py` | File/image deliver + evidence + window tests | ✓ VERIFIED | capabilities, two-step, missing URL, window expiry, image file_type=1 |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `normalize_message_event` | `_attachments_from_event` | builds attachments + message_type | ✓ WIRED | Lines 299–300 call helper then derive type / ASR |
| `AttachmentRef.uri` | `qqbot-media://` | opaque URI | ✓ WIRED | `uri=f"qqbot-media://{attachment_id}"`; never stores https URL |
| `upload_rich_media` | `TokenManager.get_token` | `Authorization: QQBot {token}` | ✓ WIRED | `_post_with_retry` → `_bearer` → `get_token()` |
| `upload_rich_media` | `MessageTransport.post_message` | POST /files body | ✓ WIRED | Same transport interface as text send |
| `send_rich_media` | `upload_rich_media` + `send_message` | two-step | ✓ WIRED | upload → `build_media_envelope` → `send_message` |
| `QQBotChannelAdapter.deliver` | `send_rich_media` | file/image after window gate | ✓ WIRED | Branch at delivery_type in {file,image}; live path awaits `send_rich_media` |
| `capabilities` | `supports_files` / `supports_images` | ChannelCapabilitySet | ✓ WIRED | Both set True |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `normalize_message_event` | `attachments` | `d.attachments` → `_attachment_ref_from_qq` | Yes — fixture-driven AttachmentRef list | ✓ FLOWING |
| `upload_rich_media` | `file_info` / evidence | QQ `/files` response via transport | Yes — Fake transport returns file_info/uuid/ttl | ✓ FLOWING |
| `adapter._deliver_rich_media` | `DeliveryResult.metadata` | `send_rich_media` evidence allowlist | Yes — merges sanitized evidence keys only | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full qqbot unittest suite | `PYTHONPATH=... python3 -m unittest discover -s packages/channels/qqbot/tests -v` | Ran 217 tests in 0.216s — OK | ✓ PASS |
| AttachmentRefTests | included in discover | all 6 methods ok | ✓ PASS |
| RichMediaUpload/Retry + envelope | included in discover | all ok | ✓ PASS |
| Adapter file/image + safety gates | included in discover | adapter + no_wecom + freeze + v1.8 ok | ✓ PASS |

### Probe Execution

| Probe | Command | Result | Status |
| ----- | ------- | ------ | ------ |
| — | — | No phase-declared or conventional `scripts/*/tests/probe-*.sh` for this phase | SKIPPED |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| EGRESS-05 | 63-01, 63-03 | attachments[] → AttachmentRef reference-only | ✓ SATISFIED | normalization mapping + AttachmentRefTests + fixtures |
| EGRESS-06 | 63-02, 63-03 | two-step upload → msg_type=7 + retry/evidence | ✓ SATISFIED | sender upload/send + adapter deliver wiring + RichMedia* tests |

No orphaned requirements for Phase 63 (REQUIREMENTS.md maps only EGRESS-05/EGRESS-06 to this phase).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | No TBD/FIXME/XXX/TODO debt markers in phase-modified sources | — | None |

### Human Verification Required

None. Plans contain no deferred `<human-check>` blocks. Behavior is covered by Fake-transport unit tests; live QQ OpenAPI IO is intentionally fixture-gated until Phase 65/67.

### Gaps Summary

No gaps. All roadmap success criteria and plan must-haves are present, substantive, wired, and covered by the green qqbot test suite (217/217).

---

_Verified: 2026-07-09T10:32:57Z_
_Verifier: Claude (gsd-verifier)_
