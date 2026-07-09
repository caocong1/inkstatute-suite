---
phase: 63
slug: qq-rich-media-inbound-egress-p2
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-09
---

# Phase 63 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | unittest (stdlib, IsolatedAsyncioTestCase for async upload/send/retry) |
| **Config file** | `packages/channels/qqbot/pyproject.toml` (existing) |
| **Quick run command** | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src" python3 -m unittest packages.channels.qqbot.tests.test_normalization packages.channels.qqbot.tests.test_sender -v` |
| **Full suite command** | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src" python3 -m unittest discover -s packages/channels/qqbot/tests -v` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command (normalization + sender)
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 63-W0-01 | 01 | 1 | EGRESS-05 | T-63-01 | Wave 0: attachment fixtures + AttachmentRefTests stubs (RED before normalize) | unit | `test -f packages/channels/qqbot/fixtures/qqbot_c2c_message_with_attachments.json && grep -n 'AttachmentRefTests\|qqbot-media://' packages/channels/qqbot/tests/test_normalization.py \| head` | ❌ W0 | ⬜ pending |
| 63-01-01 | 01 | 1 | EGRESS-05 | T-63-01 | attachments[] → AttachmentRef; uri qqbot-media://; no live URL/bytes in asdict | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src:packages/contract-test-suite/src" python3 -m unittest packages.channels.qqbot.tests.test_normalization.AttachmentRefTests -v` | ❌ W0 | ⬜ pending |
| 63-01-02 | 01 | 1 | EGRESS-05 | T-63-02 | message_type image/voice/file; video kind→message_type file; schema validate_event | unit | same as 63-01-01 | ❌ W0 | ⬜ pending |
| 63-02-01 | 02 | 2 | EGRESS-06 | T-63-03 | build_media_envelope msg_type=7 + media.file_info + content="" | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_sender.SenderEnvelopeTests -v` | ✅ extend | ⬜ pending |
| 63-02-02 | 02 | 2 | EGRESS-06 | T-63-04 | upload POST /v2/.../files file_type=4; Fake transport; file_info returned | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_sender.RichMediaUploadTests -v` | ❌ W0 | ⬜ pending |
| 63-02-03 | 02 | 2 | EGRESS-06 | T-63-05 | retry 304082/304083; 401 invalidate once; evidence has no token/url/bytes | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_sender.RichMediaRetryTests -v` | ❌ W0 | ⬜ pending |
| 63-03-01 | 03 | 3 | EGRESS-06 | T-63-06 | adapter.deliver file path: window gate → upload → send; sanitized evidence metadata | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_qqbot_channel_adapter -v` | ✅ update | ⬜ pending |
| 63-03-02 | 03 | 3 | (invariant) | T-63-07 | no wecom_service; dependencies=[]; contract freeze; safety baseline | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_no_wecom_import packages.channels.qqbot.tests.test_v1_8_safety_baseline packages.channels.qqbot.tests.test_contract_freeze_not_violated -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/channels/qqbot/fixtures/qqbot_c2c_message_with_attachments.json` — synthetic image/voice/file attachments (URLs present in fixture envelope only; never expected on AttachmentRef.uri)
- [ ] `AttachmentRefTests` in `test_normalization.py` — RED before `_attachments_from_event` implementation (**Plan 01 Task 1**)
- [ ] `RichMediaUploadTests` + `RichMediaRetryTests` in `test_sender.py` — RED before upload/send_rich_media (**Plan 02 Task 1**)
- [ ] Adapter deliver file/image + evidence assertions (**Plan 03**)
- [ ] Privacy assertions: `qqbot-media://` URI; no `https://` in AttachmentRef fields; evidence excludes tokens/`file_data`/attachment URLs

*Existing unittest infrastructure in `packages/channels/qqbot/` covers framework setup (197 tests baseline green).*

---

## Manual-Only Verifications

*No live QQ network required for Phase 63 CI. Live OpenAPI upload/send is deferred to smoke toolkit (Phase 67) / flag-on path (Phase 65). All phase behaviors have automated verification via Fake transports.*

Optional human gate (not blocking phase verify): send a fixture DOCX/PDF URL through sandbox bot after Phase 65 enablement.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 20s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending planner review
