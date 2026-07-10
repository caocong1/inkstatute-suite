---
phase: 70-webhook-composition-path
reviewed: 2026-07-10T05:00:00Z
depth: deep
files_reviewed: 7
files_reviewed_list:
  - services/qqbot-service/src/qqbot_service/webhook.py
  - services/qqbot-service/src/qqbot_service/http_server.py
  - services/qqbot-service/src/qqbot_service/__init__.py
  - services/qqbot-service/README.md
  - services/qqbot-service/tests/test_webhook_ack_first.py
  - services/qqbot-service/tests/test_webhook_composition.py
  - services/qqbot-service/tests/test_webhook_http_raw_body.py
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
fix_recommended: true
---

# Phase 70: Code Review Report

**Reviewed:** 2026-07-10T05:00:00Z
**Depth:** deep
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Phase 70 correctly ships ACK-first pure handling, raw-body identity for Ed25519 verify, Fake-only composition proofs, output-boundary gating before `adapter.deliver`, and a thin stdlib HTTP wrapper with no host crypto/normalize reimplementation. Cross-module review against `normalize_message_event` + `adapter.deliver`/`send_message` found a **group delivery metadata bug** (C2C-only tests mask it) and a **silent post-ACK failure swallow** that can drop work after QQ has already been ACKed. `--fix` recommended before Phase 71/72 harden this edge.

## Critical Issues

### CR-01: Group delivery metadata maps `scene_id` into `user_openid` and omits `group_openid`

**File:** `services/qqbot-service/src/qqbot_service/webhook.py:254-260`
**Issue:** `normalize_message_event` stores `scene` / `scene_id` / `message_id` but **not** `user_openid`. For group turns, `scene_id` is `group_openid` and the member openid lives on `normalized.message.user_id`. The host builds:

```python
"scene": turn_meta.get("scene") or "c2c",
"user_openid": turn_meta.get("user_openid")
    or turn_meta.get("scene_id")   # group: this is group_openid — wrong key
    or getattr(normalized.message, "user_id", None),  # never reached when scene_id set
```

and never sets `group_openid`. `adapter.deliver` → `send_message` requires `group_openid` for `scene=="group"` and `user_openid` for C2C. Group replies therefore cannot send correctly; the `or "c2c"` default also undoes the adapter’s intentional fail-closed on missing scene. Composition tests only exercise the C2C fixture (where `scene_id == user_openid`), so this stayed green.
**Fix:**

```python
turn_meta = {}
if normalized.message is not None:
    turn_meta = dict(getattr(normalized.message, "metadata", {}) or {})

scene = turn_meta.get("scene")  # do not default to "c2c"
user_openid = turn_meta.get("user_openid") or getattr(
    normalized.message, "user_id", None
)
group_openid = turn_meta.get("group_openid")
if scene == "group" and not group_openid:
    group_openid = turn_meta.get("scene_id")
elif scene == "c2c" and not user_openid:
    user_openid = turn_meta.get("scene_id")

delivery = ChannelDelivery(
    # ...
    metadata={
        "delivery_type": "text",
        "scene": scene,
        "user_openid": user_openid,
        "group_openid": group_openid,
        "msg_id": turn_meta.get("message_id") or turn_meta.get("msg_id"),
        "message_id": turn_meta.get("message_id"),
        # ...
    },
)
```

Add a signed group-at fixture composition test that asserts `delivery.metadata["scene"]=="group"`, `group_openid` equals fixture group openid, and `user_openid` equals member openid (not group openid).

### CR-02: Default post-ACK scheduler swallows all composition failures

**File:** `services/qqbot-service/src/qqbot_service/http_server.py:61-68`
**Issue:** After HTTP `{"op":12}` is returned, QQ treats the callback as accepted. `default_post_ack_scheduler` runs composition on a daemon thread and catches **all** `Exception`s with an empty body — no log, metric, or dead-letter. Ingress/deliver failures become silent message drops (data-loss / incorrect behavior at the production edge).
**Fix:** Keep the process from crashing, but record a sanitized failure signal:

```python
def _runner() -> None:
    try:
        result = thunk()
        if asyncio.iscoroutine(result):
            asyncio.run(result)
    except Exception as exc:
        # Never log secrets / raw legal text — issue code + exception type only.
        sys.stderr.write(
            f"qqbot-post-ack failed type={type(exc).__name__}\n"
        )
        # Optional: injectable on_error hook for operators / Phase 71 smoke.
```

Prefer an injectable `on_post_ack_error` callback (default stderr/structured logger) so unit tests can assert failure visibility without depending on stderr.

## Warnings

### WR-01: HTTP wrapper never supplies a reply source — production path ends `completed_no_reply`

**File:** `services/qqbot-service/src/qqbot_service/http_server.py:111-120` / `webhook.py:127-150`
**Issue:** `_resolve_reply_text` only returns injectable `reply_text` or a sync peek of `FakeBackend.runs[*].result.content`. `FakeBackendAdapter.submit_run` leaves `result=None` for normal succeeds, and `QQBotWebhookServer.do_POST` never passes `reply_text` or awaits `backend.get_run` / stream deltas. Operators using the stdlib server get ACK + ingress create_run but **no deliver** unless they call the pure handler with `reply_text=`. Phase 70 Fake proofs hide this via `reply_text=FIXTURE_REPLY`.
**Fix:** Wire a post-ingress reply resolver (await `get_run` / collect MESSAGE_DELTA / backend result) before boundary+deliver, or document and fail loudly with evidence `status=completed_no_reply` + issue_code when no reply source is configured. At minimum, plumb an optional server attribute `reply_text` / `reply_resolver` through `do_POST` for smoke (Phase 71) before live gate.

### WR-02: `read_request_body_once` does not require a full Content-Length read

**File:** `services/qqbot-service/src/qqbot_service/http_server.py:53-55`
**Issue:** A single `rfile.read(length)` may return fewer than `length` bytes on short/EOF reads. Truncated bodies fail signature verify (fail-closed) but surface as opaque 401s and break the “exact socket bytes” contract under partial reads.
**Fix:**

```python
chunks: list[bytes] = []
remaining = length
while remaining > 0:
    chunk = rfile.read(remaining)
    if not chunk:
        raise ValueError("incomplete_body")
    chunks.append(chunk)
    remaining -= len(chunk)
return b"".join(chunks)
```

### WR-03: Post-ACK `ensure_interaction_ack` reaches into private adapter attributes

**File:** `services/qqbot-service/src/qqbot_service/webhook.py:202-205`
**Issue:** `getattr(wired.adapter, "_transport", None)` / `"_token_manager"` couples the host to private adapter fields. Refactors of `QQBotChannelAdapter` can silently skip interaction PUT (`None` deps) while ACK already returned `pending_host`.
**Fix:** Expose read-only accessors on the wired bundle or adapter (e.g. `wired.message_transport`, `wired.token_manager`) from Phase 69 wiring, and pass those into `ensure_interaction_ack`.

## Info

### IN-01: Fragile `SolutionBinding.backend_id` resolution

**File:** `services/qqbot-service/src/qqbot_service/webhook.py:211-216`
**Issue:** Nested `getattr`/`callable` chain defaults to the literal `"fake-backend"` when `backend_id` is missing or non-callable — misleading for non-Fake backends and hard to read.
**Fix:** Prefer `wired.runtime.backend.backend_id()` behind a tiny helper with an explicit unknown fallback / required `solution=` from the operator.

### IN-02: `bot_secret` remains on `RawInbound.metadata` for the full post-ACK lifetime

**File:** `services/qqbot-service/src/qqbot_service/webhook.py:75-76,337-338`
**Issue:** Package verify requires `metadata["bot_secret"]` (established pattern). The same `raw` object is closed over into the post-ACK thunk, so the secret stays reachable for the entire composition. Delivery/feedback sinks are sanitized, but any future wholesale `raw.metadata` logging would leak it.
**Fix:** After `verify_and_ack`, copy metadata without `bot_secret` for the scheduled thunk (keep `request_body` only if normalize still needs it), or clear the key before scheduling.

---

_Reviewed: 2026-07-10T05:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
