---
phase: 62-qq-egress-sender-text-markdown-keyboard
reviewed: 2026-07-09T10:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py
  - packages/channels/qqbot/tests/test_sender.py
  - packages/channels/qqbot/tests/test_no_wecom_import.py
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: fixed
fixed_at: 2026-07-09T10:05:20Z
fix_report: .planning/phases/62-qq-egress-sender-text-markdown-keyboard/62-REVIEW-FIX.md
---

# Phase 62: Code Review Report

**Reviewed:** 2026-07-09T10:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** fixed
**Fix report:** `.planning/phases/62-qq-egress-sender-text-markdown-keyboard/62-REVIEW-FIX.md`

## Summary

Phase 62 sender/adapter work is largely aligned with EGRESS-02/03/04/07: envelope builders enforce `apply_output_policy`, keyboard nesting and four callbacks look correct, `strip_for_wire` drops audit keys, `dependencies = []` holds, and `test_no_wecom_import` covers `sender.py`. Passive-window helpers fail closed for missing/unparseable `received_at` and unknown scenes when called directly.

Two Critical defects remain on the live deliver/send path: (1) `TokenError` from `TokenManager.get_token` is not mapped to `SendError` and escapes `adapter.deliver`, and (2) missing `scene` is defaulted to `"c2c"` before the window gate, bypassing fail-closed unknown-scene handling and applying the more permissive C2C limits to group traffic. Additional Warnings cover openid path injection into wire URLs, empty-content deliveries marked accepted, and dead `window_ok` state.

## Critical Issues

### CR-01: `TokenError` escapes `send_message` / `adapter.deliver`

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py:477-495`
**Also:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:319-337`
**Issue:** `send_message` awaits `token_manager.get_token()` outside any `SendError` mapping (initial fetch and the HTTP 401 invalidate→refresh path). `TokenManager` raises `TokenError`, which is not a subclass of `SendError`. `adapter.deliver` only catches `SendError`, so token acquisition failures propagate as uncaught exceptions instead of `DeliveryResult(accepted=False, …)`. Reproduced: initial `TokenError("boom")` and 401-then-refresh `TokenError("refresh-fail")` both escape.
**Fix:** Map token failures inside `send_message` (and/or broaden `deliver`):

```python
from .token_manager import TokenError

async def _bearer(token_manager: TokenManager) -> str:
    try:
        return await token_manager.get_token()
    except TokenError as exc:
        raise SendError(
            "QQ Bot token unavailable",
            status_code=getattr(exc, "status_code", None),
        ) from None

# In send_message:
token = await _bearer(token_manager)
# ... and on 401:
token_manager.invalidate()
token = await _bearer(token_manager)
```

Also catch `SendError` (already) and optionally `TokenError` in `deliver` as defense in depth so the host always gets a structured failure.

### CR-02: Missing `scene` defaults to C2C — window fail-open for group

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:235-261`
**Issue:** `check_passive_reply_window` correctly fail-closes unknown scenes (`else: return _expired()`). `deliver` never passes an unknown scene: `scene = … or "c2c"`. A group delivery missing `metadata.scene` is gated with C2C limits (60 min / 4 replies) instead of group (5 min / 5). That violates EGRESS-04 fail-closed intent and can accept sends that should expire under group rules.
**Fix:** Do not invent a permissive default before the gate. Require an explicit scene, or fail closed:

```python
scene = _optional_string(metadata.get("scene"))
if msg_id is not None:
    if scene is None:
        scene_for_window = ""  # unknown → expired inside check
    else:
        scene_for_window = scene
    window = check_passive_reply_window(
        scene=scene_for_window,
        received_at=received_at if isinstance(received_at, str) else None,
        reply_count=reply_count,
        msg_id=msg_id,
    )
    ...
# For send_message URL selection, still require a real scene:
if scene not in {"c2c", "group"}:
    # reject before live send
    ...
```

## Warnings

### WR-01: `user_openid` / `group_openid` interpolated into URL without validation

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py:379-386`
**Also:** `UrllibMessageTransport` host check at `313-314` only uses `startswith(_API_BASE + "/")`
**Issue:** Openids are path-interpolated raw. Values like `../evil`, `u?q=1`, or `u#frag` still produce URLs under `https://api.sgroup.qq.com/…`, so the host allowlist passes while the path/query is attacker-influenced (metadata-sourced). Confirmed `wire_url_for_scene("c2c", user_openid="../evil")` → `…/v2/users/../evil/messages`.
**Fix:** Reject non-safe openid characters before building the URL:

```python
import re
_OPENID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

def _require_openid(value: str, *, label: str) -> str:
    if not _OPENID_RE.fullmatch(value):
        raise SendError(f"invalid {label}")
    return value
```

Prefer `urllib.parse.quote(openid, safe="")` only if QQ documents percent-encoding; otherwise reject.

### WR-02: Empty content yields `accepted=True` with no wire body fields

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py:75-79`
**Also:** `adapter.py:300-304`
**Issue:** `apply_output_policy("")` returns `allow` with `visible_text=""`. Builders skip attaching `msg_type`/`content` when `visible_text` is falsy, but `deliver` still sets `accepted = policy_action != "block" …` → `True`. Callers observe a successful delivery whose wire envelope is only `msg_id`/`msg_seq` (after strip), which is not a valid QQ send body.
**Fix:** Treat missing user-visible payload as non-accepted (or as an explicit skip issue code):

```python
has_payload = "msg_type" in envelope
accepted = (
    policy_action != "block"
    and has_payload
    and self._config.enabled
)
```

### WR-03: Dead `window_ok = True` after early return

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:299-304`
**Issue:** Window failures return early (lines 262–273). The later `window_ok = True` is always true and never reflects a real gate outcome, which invites future regressions if someone removes the early return and relies on `window_ok`.
**Fix:** Remove the unused flag, or set `window_ok` from the gate result and use a single return path:

```python
accepted = policy_action != "block" and self._config.enabled
```

## Info

### IN-01: `dependencies = []` and no `wecom_service` imports — OK

**File:** `packages/channels/qqbot/pyproject.toml:15`
**Also:** `packages/channels/qqbot/tests/test_no_wecom_import.py:94-101`
**Issue:** None — invariants hold. `sender.py` imports only stdlib + `channel_core` + local `token_manager`; AST test covers `sender.py`.
**Fix:** N/A

### IN-02: Output boundary + keyboard shape — OK for reviewed paths

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/sender.py:67-147,150-153`
**Issue:** None for the happy path — text/markdown/keyboard builders call `apply_output_policy`; blocked notices omit content/keyboard; `strip_for_wire` removes `policy`/`inkstatute`; feedback buttons use canonical `FEEDBACK_ACTIONS` with `action.type=1` and `keyboard.content.rows` nesting. `feedback_target` staying audit-only (stripped from wire) matches Plan 01 / RESEARCH.
**Fix:** N/A

---

_Reviewed: 2026-07-09T10:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
