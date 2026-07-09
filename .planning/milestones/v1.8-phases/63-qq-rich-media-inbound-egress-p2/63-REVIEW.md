---
phase: 63-qq-rich-media-inbound-egress-p2
reviewed: 2026-07-09T10:33:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/normalization.py
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py
  - packages/channels/qqbot/tests/test_normalization.py
  - packages/channels/qqbot/tests/test_sender.py
  - packages/channels/qqbot/tests/test_qqbot_channel_adapter.py
findings:
  critical: 0
  warning: 3
  info: 1
  total: 4
status: fixed
fixed_at: 2026-07-09T10:39:15Z
fix_report: .planning/phases/63-qq-rich-media-inbound-egress-p2/63-REVIEW-FIX.md
---

# Phase 63: Code Review Report

**Reviewed:** 2026-07-09T10:33:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** fixed
**Fixed at:** 2026-07-09T10:39:15Z
**Fix report:** `.planning/phases/63-qq-rich-media-inbound-egress-p2/63-REVIEW-FIX.md`

## Summary

Phase 63 EGRESS-05/06 rich-media work was reviewed for reference-only inbound privacy, sanitized egress evidence, upload retry (304082/304083), `msg_type=7` payload shape, `dependencies=[]`, and no WeCom coupling.

Focus invariants hold: inbound attachments use opaque `qqbot-media://` URIs with no live URLs/bytes; live deliver metadata omits `file_info`/tokens/URLs; upload retries share `_post_with_retry`; media envelopes are `msg_type=7` with `media.file_info` + empty `content`; `pyproject.toml` keeps `dependencies = []`; no `wecom_service` imports in qqbot source.

No critical/blocker defects. Three warnings concern inaccurate or incomplete rich-media failure/success evidence (attempt counts and missing-`file_info` classification). One info note on fixture-path envelope sanitization inconsistency.

## Warnings

### WR-01: Upload/send failure evidence always reports `attempts=max_attempts`

**Status:** fixed (473cac8)
**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py:740-746`
**Issue:** On `SendError` from `_post_with_retry`, `upload_rich_media` attaches evidence with `attempts=max_attempts` rather than the attempts actually consumed. Terminal first-attempt failures (and early exits) are therefore recorded as if all retries ran. The same pattern appears on the send failure path in `send_rich_media` (lines 824-833). Operators diagnosing upload/send failures will see inflated attempt counts.
**Fix:** Have `_post_with_retry` attach the attempt counter to the raised `SendError` (or return it via a dedicated attribute), then pass that value into `_rich_media_evidence`:

```python
except SendError as exc:
    attempts_used = getattr(exc, "attempts", max_attempts)
    evidence = _rich_media_evidence(
        stage="upload",
        attempts=attempts_used,
        status_code=exc.status_code,
        qq_code=exc.qq_code,
        issue_code=_ISSUE_RICH_MEDIA_UPLOAD_FAILED,
    )
    exc.evidence = evidence  # type: ignore[attr-defined]
    raise
```

### WR-02: Successful `send_rich_media` evidence hardcodes send `attempts=1` and overwrites upload attempts

**Status:** fixed (af87917)
**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py:836-848`
**Issue:** After a successful send, evidence is built with `attempts=1` regardless of retries inside `send_message`. The merge `{**upload_evidence, **send_evidence}` then overwrites the upload stage's accurate `attempts` with `1`. DeliveryResult metadata therefore loses upload retry count on the happy path and under-reports send retries.
**Fix:** Propagate attempt counts from both steps and keep them distinct (or nest stages):

```python
send_result, send_attempts = await send_message_with_attempts(...)  # or unpack from _post_with_retry
send_evidence = _rich_media_evidence(
    stage="send",
    attempts=send_attempts,
    file_uuid=upload.get("file_uuid"),
    ttl=upload.get("ttl"),
)
result["evidence"] = {
    "rich_media_stage": "send",
    "upload_attempts": upload.get("evidence", {}).get("attempts"),
    "send_attempts": send_attempts,
    "file_uuid_hash": send_evidence.get("file_uuid_hash"),
    "ttl": send_evidence.get("ttl"),
}
```

### WR-03: Missing `file_info` after upload HTTP success raises without evidence / misclassified issue_code

**Status:** fixed (e2a69e1)
**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py:751-753`
**Issue:** When the upload transport returns a dict without a usable `file_info` string, `upload_rich_media` raises a bare `SendError` with no `.evidence`. In `adapter._deliver_rich_media` (lines 490-500), `stage` is then `None`, so `issue_code` defaults to `qqbot_send_failed` even though the failure is still in the upload stage. Failure classification and evidence allowlist merge are wrong for this edge case.
**Fix:** Attach upload-stage evidence before raising:

```python
file_info = result.get("file_info")
if not isinstance(file_info, str) or not file_info:
    err = SendError("QQ Bot rich media upload missing file_info")
    err.evidence = _rich_media_evidence(  # type: ignore[attr-defined]
        stage="upload",
        attempts=attempts,
        issue_code=_ISSUE_RICH_MEDIA_UPLOAD_FAILED,
    )
    raise err
```

## Info

### IN-01: Fixture-only deliver path embeds live `media.file_info` in DeliveryResult.metadata

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:565-570`
**Issue:** Live success deliberately stores a `msg_type=7` marker envelope without `media.file_info` (lines 534-540). The fixture-only path stores the full `build_media_envelope(...)` including `file_info`. This is consistent with Plan 03's fixture decision, but it is a sanitization asymmetry: any caller that supplies `file_info` without an injected transport gets `accepted=True` and persists the upload token in metadata.
**Fix:** Optionally mirror the live marker-only envelope on the fixture path (keep `file_info` only in test assertions against the wire builder), or document that fixture metadata may contain caller-supplied `file_info` and must not be written to contract logs.

## Focus checklist

| Focus | Result |
| --- | --- |
| Reference-only inbound (no live URLs/bytes) | Pass — `qqbot-media://` URI; URL hashed into id only; `bytes_stored=False` |
| Token leakage in evidence | Pass — allowlisted keys; hashed `file_uuid`; no Authorization/access_token/URL/`file_data` |
| Upload retry (304082/304083) | Pass — in `_TRANSIENT_QQ_CODES`; shared `_post_with_retry` |
| `msg_type=7` payload | Pass — `media.file_info` + `content=""`; wire strip keeps media |
| `dependencies = []` | Pass — `packages/channels/qqbot/pyproject.toml` |
| No WeCom | Pass — no `wecom_service` imports under qqbot `src/` |

---

_Reviewed: 2026-07-09T10:33:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
