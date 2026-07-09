---
phase: 62
slug: qq-egress-sender-text-markdown-keyboard
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-09
---

# Phase 62 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | unittest (stdlib, IsolatedAsyncioTestCase for async send/retry) |
| **Config file** | `packages/channels/qqbot/pyproject.toml` (existing) |
| **Quick run command** | `python3 -m unittest packages.channels.qqbot.tests.test_sender -v` |
| **Full suite command** | `python3 -m unittest discover -s packages/channels/qqbot/tests -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m unittest packages.channels.qqbot.tests.test_sender -v`
- **After every plan wave:** Run `python3 -m unittest discover -s packages/channels/qqbot/tests -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 62-W0-01 | 01 | 1 | EGRESS-02/03/07 | — | Wave 0: Plan 01 Task 1 creates `test_sender.py` envelope/keyboard/policy stubs (RED before builders) | unit | `test -f packages/channels/qqbot/tests/test_sender.py && grep -n 'SenderEnvelopeTests\|build_text_envelope' packages/channels/qqbot/tests/test_sender.py \| head` | ❌ W0 | ⬜ pending |
| 62-01-01 | 01 | 1 | EGRESS-02 | T-62-01 | Text msg_type=0 + msg_id/msg_seq; policy before content attach | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_sender.SenderEnvelopeTests -v` | ❌ W0 | ⬜ pending |
| 62-01-02 | 01 | 1 | EGRESS-07 | T-62-02 | Markdown msg_type=2 + content="" companion; output policy on content | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_sender.SenderEnvelopeTests -v` | ❌ W0 | ⬜ pending |
| 62-01-03 | 01 | 1 | EGRESS-03 | T-62-03 | Card → keyboard.content.rows; actions up/down/needs_fix/route_wrong; no template_card | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_sender.SenderEnvelopeTests -v` | ❌ W0 | ⬜ pending |
| 62-02-01 | 02 | 2 | EGRESS-04 | T-62-04 | Window expiry / missing received_at → issue_code + interim owned notice | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_sender.PassiveReplyWindowTests -v` | ❌ W0 | ⬜ pending |
| 62-02-02 | 02 | 2 | EGRESS-02 | T-62-05 | Transient retry via FakeMessageTransport; 401 invalidate once; terminal 304026 | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_sender.SendRetryTests -v` | ❌ W0 | ⬜ pending |
| 62-03-01 | 03 | 3 | EGRESS-02/03/04/07 | T-62-08/T-62-10 | adapter.deliver() uses sender builders + window gate (msg_id present always gates; missing received_at fail-closed); fixture network_io=False | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_qqbot_channel_adapter -v` | ✅ update | ⬜ pending |
| 62-03-02 | 03 | 3 | (invariant) | T-62-11 | sender.py no wecom_service; dependencies=[]; loop assertions for integer msg_type | unit | `PYTHONPATH="packages/channels/qqbot/src:packages/channel-core/src:packages/platform-contract/src:packages/platform-runtime/src" python3 -m unittest packages.channels.qqbot.tests.test_no_wecom_import packages.channels.qqbot.tests.test_qqbot_channel_loop packages.channels.qqbot.tests.test_v1_8_safety_baseline -v` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/channels/qqbot/tests/test_sender.py` — created in **Plan 01 Task 1** (Wave 0 / RED) covering EGRESS-02/03/07 envelope, keyboard, and policy stubs; Plan 02 extends with window/retry classes
- [ ] Extend `test_no_wecom_import.py` with `sender.py` AST scan (**Plan 03 Task 2**)
- [ ] Update adapter/loop delivery assertions for integer `msg_type` + keyboard (**Plan 03 Tasks 1–2**)

*Existing unittest infrastructure in `packages/channels/qqbot/` covers framework setup.*

---

## Manual-Only Verifications

*No live QQ network required for Phase 62 CI. Live OpenAPI send is deferred to smoke toolkit / Phase 65 flag-on path. All phase behaviors have automated verification via FakeMessageTransport.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending planner review
