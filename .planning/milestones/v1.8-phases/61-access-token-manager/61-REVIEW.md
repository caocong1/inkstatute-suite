---
phase: 61-access-token-manager
reviewed: 2026-07-09T09:11:09Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py
  - packages/channels/qqbot/tests/test_token_manager.py
  - packages/channels/qqbot/tests/test_no_wecom_import.py
findings:
  critical: 0
  warning: 5
  info: 3
  total: 8
status: warnings_fixed
fix_report: .planning/phases/61-access-token-manager/61-REVIEW-FIX.md
---

# Phase 61: Code Review Report

**Reviewed:** 2026-07-09T09:11:09Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** warnings_fixed (WR-01..WR-05 applied; IN-01..IN-03 remaining)

## Summary

`TokenManager` correctly implements transport injection, lock + re-check single-flight, injected credentials (no env/file reads), sanitized `TokenError` message text, lazy urllib (no top-level HTTP imports), and `dependencies = []`. Import isolation for `token_manager.py` is covered.

**Fix pass (2026-07-09):** All five warnings were fixed — atomic cache assign (WR-01), bool/non-finite `expires_in` rejection (WR-02/WR-03), short-TTL rejection vs refresh margin (WR-04), and sanitized decode/JSON/non-dict `TokenError` mapping with `from None` (WR-05). See `61-REVIEW-FIX.md`. Info findings IN-01..IN-03 remain open.

## Warnings

### WR-01: Non-atomic cache update on failed expiry extract

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py:146-148`
**Issue:** `get_token` assigns `_token` before `_expires_at`. If `_extract_token` succeeds and `_extract_expiry` raises, the cache is left inconsistent: new token stored, previous/zero expiry retained. Reproduced: after `{"access_token":"new-token","expires_in":"bad"}`, state is `_token="new-token"` with stale `_expires_at`. Callers see `TokenError`, but internal cache is corrupted until a later full success.
**Fix:** Extract both values, then assign atomically:

```python
token = self._extract_token(response)
ttl = self._extract_expiry(response)
self._token = token
self._expires_at = self._clock() + ttl
return self._token
```

### WR-02: Non-finite `expires_in` (NaN/Inf) accepted — token never refreshes

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py:162-166`
**Issue:** `_extract_expiry` only rejects non-`(int, float)` or `<= 0`. `float("nan")` and `float("inf")` pass (`nan <= 0` is False). Then `_expires_at` becomes NaN/Inf and `_is_near_expiry()` is always False (NaN comparisons are False; Inf never crosses the margin), so `get_token` never refreshes. Python `json.loads` accepts `NaN`/`Infinity` by default, so a malformed body can pin a dead token until `invalidate()`.
**Fix:**

```python
import math
# ...
expires_in = response.get("expires_in")
if isinstance(expires_in, bool) or not isinstance(expires_in, (int, float)):
    raise TokenError("QQ Bot token response missing or invalid expires_in")
value = float(expires_in)
if not math.isfinite(value) or value <= 0:
    raise TokenError("QQ Bot token response missing or invalid expires_in")
return value
```

### WR-03: `bool` is accepted as `expires_in` (int subclass)

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py:164`
**Issue:** `isinstance(True, int)` is True, so JSON/`True` becomes TTL `1.0`. With default `refresh_margin=60`, the token is immediately near-expiry and every `get_token` hits the network (refresh storm).
**Fix:** Reject bools explicitly before the numeric check (see WR-02 snippet).

### WR-04: `expires_in <= refresh_margin` causes perpetual refresh

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py:150-152`
**Issue:** For `expires_in=30` and `refresh_margin=60`, `_is_near_expiry()` is True immediately after cache write, so every subsequent `get_token` re-fetches. Confirmed: second call increments `call_count`. Unusual vs QQ’s ~7200s TTL, but any short TTL (or margin misconfig) DoS-es the token endpoint and defeats caching.
**Fix:** Reject or clamp when TTL cannot outlive the margin, e.g.:

```python
if value <= self._refresh_margin:
    raise TokenError("QQ Bot token expires_in too short for refresh margin")
```

(or `effective_margin = min(refresh_margin, max(0.0, value - 1.0))` at cache time).

### WR-05: Malformed HTTP body not mapped to `TokenError` (decode/JSON)

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py:89-92`
**Issue:** Only `HTTPError` / `URLError` are translated. `json.loads` failures raise `JSONDecodeError` (whose `.doc` can hold the raw body including `access_token`), and non-UTF-8 bodies raise `UnicodeDecodeError`. Non-dict JSON (e.g. a list) later crashes in `_extract_token` with `AttributeError: ... no attribute 'get'`. Callers expecting only `TokenError` get inconsistent types; logging `repr(exc)` / exception args can leak token material from `JSONDecodeError.doc`.
**Fix:**

```python
try:
    with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
        body = resp.read().decode("utf-8")
        parsed = json.loads(body)
except urllib.error.HTTPError as exc:
    raise TokenError("QQ Bot token request failed", status_code=exc.code) from None
except urllib.error.URLError:
    raise TokenError("QQ Bot token endpoint unreachable") from None
except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
    raise TokenError("QQ Bot token response invalid") from None
if not isinstance(parsed, dict):
    raise TokenError("QQ Bot token response invalid")
return parsed
```

Prefer `from None` (or omit cause) if traceback/cause chains must not retain URL or response fragments.

## Info

### IN-01: `invalidate()` races with in-flight refresh

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py:168-171`
**Issue:** `invalidate()` clears cache without the lock. An in-flight refresh can finish afterward and repopulate `_token` / `_expires_at`. Often acceptable (fresh token satisfies “force refresh”), but a 401-driven invalidate during refresh may briefly observe cleared then refilled state.
**Fix:** Optionally take the lock in `invalidate()`, or document that in-flight refresh wins.

### IN-02: Lock-free fast path can return a just-invalidated token

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py:135-136`
**Issue:** Between the unlocked validity check and `return`, another task may call `invalidate()`. Classic double-checked-locking TOCTOU; usually fine for token caches.
**Fix:** Accept as designed, or re-read under lock on sensitive paths.

### IN-03: Exception `__cause__` may still expose endpoint URL in tracebacks

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/token_manager.py:94-99`
**Issue:** `TokenError` messages are sanitized (no app id / secret / token / URL in `str(exc)`), which matches the plan. `raise ... from exc` still attaches `URLError`/`HTTPError` causes that often include the request URL in tracebacks.
**Fix:** Use `from None` if logs must never show the token URL; keep `from exc` only if debug causality is required.

## Focus-area checklist

| Focus | Result |
| --- | --- |
| Token leakage in errors/logs | Message text sanitized; residual risk via `JSONDecodeError.doc` / exception causes (WR-05, IN-03) |
| Single-flight race | Lock + re-check is correct; concurrent gather test matches design |
| Clock/TTL edge cases | NaN/Inf, bool, short TTL, non-atomic assign (WR-01–WR-04) |
| Credential handling | Injected only; no env/file/hardcoded secrets |
| Import safety / `dependencies=[]` | Lazy urllib; no wecom import; `pyproject.toml` still `dependencies = []` |

---

_Reviewed: 2026-07-09T09:11:09Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
