---
phase: 62-qq-egress-sender-text-markdown-keyboard
verified: 2026-07-09T09:56:03Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
gaps: []
---

# Phase 62: QQ Egress Sender — Text + Markdown + Keyboard Verification Report

**Phase Goal:** QQ Bot text messages (`msg_type=0`) delivered with `msg_id`+`msg_seq` dedupe and retry; markdown+keyboard feedback cards; markdown replies; passive-reply window tracking with window-expiry delivery failure + interim service notice; output boundary enforced; `adapter.deliver()` wired.
**Verified:** 2026-07-09T09:56:03Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | ------- | ---------- | -------------- |
| 1 | `sender.py` delivers text messages (`msg_type=0`) with `msg_id`+`msg_seq` passive-reply dedupe and retry on transient failure | ✓ VERIFIED | `build_text_envelope` sets int `msg_type=0` + `content`/`msg_id`/`msg_seq` (`sender.py:67-79`); `send_message` retries transients with backoff and 401→`invalidate`+refresh (`sender.py:454-549`); covered by `SenderEnvelopeTests` + `SendRetryTests` |
| 2 | `sender.py` delivers markdown+keyboard feedback cards (`msg_type=2` + `keyboard`) with callbacks up/down/needs_fix/route_wrong; `delivery_type=="card"` maps to QQ keyboard (not WeCom `template_card`) | ✓ VERIFIED | `build_feedback_keyboard_envelope` builds `keyboard.content.rows` with `FEEDBACK_ACTIONS` (`sender.py:21,104-147`); adapter routes `card`/`template_card`→keyboard (`adapter.py:276-282,437`); adapter/loop tests assert int `msg_type=2`, keyboard present, no `template_card` |
| 3 | `sender.py` delivers markdown replies (`msg_type=2`) for structured legal answers with output boundary enforcement | ✓ VERIFIED | `build_markdown_envelope` applies `apply_output_policy` then attaches `markdown.content` (`sender.py:82-101`); adapter markdown path + `test_markdown_delivery_builds_markdown_envelope` |
| 4 | Passive-reply window (C2C 60min/4, group 5min/5 per `msg_id`) tracked; expiry → delivery failure + interim InkStatute-owned notice | ✓ VERIFIED | `check_passive_reply_window` enforces limits and fail-closed missing/`received_at` (`sender.py:32-36,184-231`); interim via `build_owned_notice("long_processing")`; adapter returns `accepted=False` + `issue_code=qqbot_passive_reply_window_expired` + `interim_notice` (`adapter.py:254-273`); `PassiveReplyWindowTests` + adapter window tests green |
| 5 | `adapter.py` `deliver()` is modified to use the new sender | ✓ VERIFIED | Imports and calls `build_*_envelope`, `check_passive_reply_window`, optional `send_message` (`adapter.py:24-30,223-345`); stub `_build_text_envelope`/`_build_card_envelope` removed; default `network_io=False` unless transport+token_manager injected |
| 6 | Output boundary enforcement prevents backend gateway/system notices from leaking to users | ✓ VERIFIED | All builders call `apply_output_policy` before content attach; blocked envelopes omit user-visible content; `strip_for_wire` drops `policy`/`inkstatute`; adapter + sender tests block `ADMIN_NOTICE`/`token=secret` patterns |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | ----------- | ------ | ------- |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py` | Envelope builders, window gate, MessageTransport, `send_message` | ✓ VERIFIED | 566 lines; exports builders, `strip_for_wire`, window, transport, retry; `gsd-tools verify.artifacts` passed (plans 01–02) |
| `packages/channels/qqbot/tests/test_sender.py` | Envelope/window/retry unit tests | ✓ VERIFIED | 373 lines; `SenderEnvelopeTests`, `PassiveReplyWindowTests`, `SendRetryTests` |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` | `deliver()` wired to sender | ✓ VERIFIED | `from .sender import …`; card/markdown/text routing + window gate + optional live send |
| `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py` | Integer `msg_type` + keyboard + window failure | ✓ VERIFIED | Text/card/markdown/window/block assertions updated |
| `packages/channels/qqbot/tests/test_no_wecom_import.py` | AST isolation includes `sender.py` | ✓ VERIFIED | `test_sender_does_not_import_wecom_service` present and passing |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `sender.py` | `channel_core.output_policy.apply_output_policy` | each `build_*_envelope` | ✓ WIRED | Three call sites at lines 75, 90, 113 (gsd-tools regex false-negative from double-escape; manual grep confirmed) |
| `test_sender.py` | `sender.py` | imports builders/`FEEDBACK_ACTIONS` | ✓ WIRED | `from inkstatute_channels_qqbot.sender import (` |
| `sender.py` | `token_manager.get_token` / `invalidate` | `send_message` auth path | ✓ WIRED | lines 477, 494–495 |
| `sender.py` | `build_owned_notice` | window expiry interim | ✓ WIRED | line 205, kind `long_processing` |
| `sender.py` | `MessageTransport.post_message` | POST `strip_for_wire(envelope)` | ✓ WIRED | line 485; Authorization `QQBot {token}` |
| `adapter.py` | `sender.py` builders + window | `deliver()` | ✓ WIRED | gsd-tools plan 03 links verified |
| `adapter.py` | `DeliveryResult.metadata` | `issue_code` / `interim_notice` / `network_io` | ✓ WIRED | gsd-tools plan 03 links verified |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `adapter.deliver` envelope | `envelope` | `build_*_envelope(content/title, msg_id, msg_seq)` from `ChannelDelivery` | Policy-filtered content + OpenAPI fields (not hardcoded empty) | ✓ FLOWING |
| Window failure metadata | `issue_code` / `interim_notice` | `check_passive_reply_window` → `build_owned_notice` | Non-empty owned notice string on expiry | ✓ FLOWING |
| Optional live send | `network_io` | `send_message` only when transport+token_manager+enabled | Default fixture path keeps `network_io=False` (intentional; Phase 65 promotes real IO) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full qqbot unittest suite | `PYTHONPATH=packages/channels/qqbot/src:packages/channel-core/src python3 -m unittest discover -s packages/channels/qqbot/tests -v` | 189 tests OK | ✓ PASS |
| WeCom isolation (incl. sender) | `python3 -m unittest packages.channels.qqbot.tests.test_no_wecom_import -v` | 10 tests OK | ✓ PASS |
| Envelope/window spot script | Inline asserts on builders + window fail-closed | `SPOT_CHECKS_OK` | ✓ PASS |
| `dependencies=[]` preserved | `tomllib` read of `pyproject.toml` | `deps []` | ✓ PASS |

### Probe Execution

| Probe | Command | Result | Status |
| ----- | ------- | ------ | ------ |
| — | — | No phase-declared or conventional `scripts/*/tests/probe-*.sh` for Phase 62 | SKIPPED |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| EGRESS-02 | 62-01, 62-02, 62-03 | Text `msg_type=0` + `msg_id`/`msg_seq` + retry + output boundary | ✓ SATISFIED | Builders + `send_message` retry/401 + policy + adapter text path |
| EGRESS-03 | 62-01, 62-03 | Markdown+keyboard feedback card; not `template_card` | ✓ SATISFIED | Keyboard nesting + four callbacks; adapter card mapping |
| EGRESS-04 | 62-02, 62-03 | Passive window C2C 60min/4, group 5min/5; expiry failure + interim notice | ✓ SATISFIED | Window gate + adapter fail-closed metadata |
| EGRESS-07 | 62-01, 62-03 | Markdown `msg_type=2` with policy on content | ✓ SATISFIED | `build_markdown_envelope` + adapter markdown delivery |

No orphaned Phase-62 requirements found outside the four EGRESS IDs above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | No `TBD`/`FIXME`/`XXX` in phase-modified sender/adapter sources | — | — |
| `adapter.py` | 437 | `template_card` alias → `card` | ℹ️ Info | Intentional mapping away from WeCom shape, not a stub |

### Human Verification Required

None. Plans contain no deferred `<human-check>` blocks; phase success is covered by unit/fixture tests without live QQ credentials. Live OpenAPI promotion is explicitly scoped to later Phase 65.

### Gaps Summary

No gaps. All six ROADMAP success criteria are observably true in code and tests. `gsd-tools verify.key-links` reported false negatives for plans 01–02 due to double-escaped regex patterns; manual wiring checks confirmed all links.

---

_Verified: 2026-07-09T09:56:03Z_
_Verifier: Claude (gsd-verifier)_
