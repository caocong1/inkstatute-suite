---
phase: 59-ed25519-signature-verification-validation-challenge
reviewed: 2026-07-07T09:28:07Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/_ed25519.py
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/signature.py
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py
  - packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py
  - packages/channels/qqbot/tests/test_ed25519_vectors.py
  - packages/channels/qqbot/tests/test_signature.py
  - packages/channels/qqbot/tests/test_no_wecom_import.py
findings:
  critical: 2
  warning: 4
  info: 2
  total: 8
status: issues_found
---

# Phase 59: Code Review Report

**Reviewed:** 2026-07-07T09:28:07Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Phase 59 implements Ed25519 signature verification for QQ Bot callbacks — a
security-critical ingress gate. The vendored RFC 8032 reference implementation
in `_ed25519.py` is copied verbatim and is cryptographically correct (verified
against the official QQ demo vectors). The `config.py` change correctly stores
only a reference (`bot_secret_ref`), never the raw secret. Import isolation is
clean — no `wecom_service` imports anywhere.

However, the signature-service wrapper (`signature.py`) and the adapter wiring
(`adapter.py`) contain two **BLOCKER** defects that must be fixed before ship:

1. **Infinite loop** in `derive_seed` when the BotSecret resolves to an empty
   string — a denial-of-service vector reachable via runtime misconfiguration.
2. **Unhandled `AttributeError`** in `verify_and_ack` when `bot_secret` is not
   injected into `raw.metadata` — violates the method's contract to always
   return an `AckResponse` and crashes the request handler instead of
   returning a clean 401.

Additionally, the stub-accept path (bot_secret_ref unset but channel enabled)
accepts all callbacks without signature verification — a
misconfiguration-to-bypass risk. Several input-type validation gaps mean
non-`bytes`/non-`str` metadata values crash rather than producing a clean 401.

The 401 rejection logic itself (when inputs are well-typed) is sound: there is
no path to `normalize_inbound` without a verified signature when
`bot_secret_ref` is configured, and the op=13 challenge signing is correct.

## Critical Issues

### CR-01: Infinite loop in `derive_seed` on empty BotSecret

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/signature.py:28-31`
**Issue:** `derive_seed("")` enters an infinite loop. The algorithm repeats
the seed bytes until reaching 32 bytes, but an empty byte string doubles to
itself forever (`b"" * 2 == b""`), so `while len(seed) < 32:` never exits.

This is reachable from `verify_and_ack` when the runtime secret resolver
returns an empty string for `bot_secret` (e.g. the referenced secret is
misconfigured to `""`). The adapter checks `bot_secret is None` is **not**
checked at all (see CR-02), and does not check for empty string, so an empty
`bot_secret` in `raw.metadata` hangs the callback handler indefinitely — a
denial-of-service via misconfiguration.

Confirmed by reproduction: `timeout 3 python3 -c "derive_seed('')"` exits with
code 124 (timeout killed).

**Fix:**
```python
def derive_seed(bot_secret: str) -> bytes:
    """Derive a 32-byte Ed25519 seed from a BotSecret string."""
    if not bot_secret:
        raise ValueError("bot_secret must be a non-empty string")
    seed = bot_secret.encode("utf-8")
    while len(seed) < 32:
        seed = seed * 2
    return seed[:32]
```
Then in `verify_and_ack`, treat a missing-or-empty `bot_secret` as a 401 (or
500) rejection rather than calling `derive_keypair`.

### CR-02: Unhandled `AttributeError` when `bot_secret` is None in `verify_and_ack`

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:96-114`
**Issue:** The None-check on line 102 validates `sig_hex`, `timestamp`, and
`request_body`, but **not** `bot_secret`:

```python
sig_hex = raw.metadata.get("x_signature_ed25519")
timestamp = raw.metadata.get("x_signature_timestamp")
request_body = raw.metadata.get("request_body")
bot_secret = raw.metadata.get("bot_secret")

if sig_hex is None or timestamp is None or request_body is None:
    return AckResponse(... 401, "missing" ...)
```

If `bot_secret_ref` is configured (so the stub path is skipped) but the runtime
fails to inject `bot_secret` into `raw.metadata`, execution proceeds to
`derive_keypair(bot_secret)` → `derive_seed(None)` → `None.encode("utf-8")` →
`AttributeError`. The method contract (`async def verify_and_ack(...) ->
AckResponse`) is violated — the caller receives an exception instead of an
`AckResponse`, crashing the ingress handler.

Confirmed by reproduction: `derive_seed(None)` raises
`AttributeError: 'NoneType' object has no attribute 'encode'`.

**Fix:**
```python
if (
    sig_hex is None
    or timestamp is None
    or request_body is None
    or bot_secret is None
):
    return AckResponse(
        accepted=False,
        status_code=401,
        idempotency_key=idem_key,
        metadata={**base_meta, "signature_status": "missing"},
    )
```
Also guard against empty string (`not bot_secret`) to prevent the CR-01
infinite loop at this boundary.

## Warnings

### WR-01: Stub path accepts unverified callbacks when `bot_secret_ref` is None

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:87-93`
**Issue:** When the channel is enabled (`enabled=True`) but `bot_secret_ref`
is not configured, `verify_and_ack` returns `accepted=True, status_code=200,
signature_status="secret_ref_required"` — accepting the callback **without**
any signature verification. This is documented as "preserved stub behavior",
but it is a misconfiguration-to-security-bypass: an operator who enables the
channel but forgets to set `bot_secret_ref` silently disables the entire
signature verification gate. The threat model (T-59-09) claims "no path to
normalize_inbound without verified signature" — this stub path violates that
claim when `bot_secret_ref` is unset.

**Fix:** Reject with 401 (or 503) when the channel is enabled but
`bot_secret_ref` is not configured, rather than accepting. If the stub is
required for fixture/test compatibility, gate it behind an explicit
`allow_unsigned_stubs` flag that defaults to `False`:
```python
if self._config.bot_secret_ref is None:
    return AckResponse(
        accepted=False,
        status_code=401,
        idempotency_key=idem_key,
        metadata={**base_meta, "signature_status": "secret_ref_required"},
    )
```

### WR-02: Missing type validation for signature inputs causes crashes instead of clean 401

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:96-114` and `packages/channels/qqbot/src/inkstatute_channels_qqbot/signature.py:57-64`
**Issue:** The adapter checks for `None` but not for wrong types:
- `request_body` as `str` (not `bytes`) → `timestamp.encode("utf-8") + request_body` raises `TypeError: can't concat str to bytes` (confirmed by reproduction).
- `timestamp` as `int` (not `str`) → `timestamp.encode("utf-8")` raises `AttributeError: 'int' object has no attribute 'encode'` (confirmed by reproduction).

`verify_callback_signature`'s docstring claims it "Never raises on malformed
input", but this is only true for `ValueError` from `bytes.fromhex`; type
errors from non-`str` `timestamp` or non-`bytes` `request_body` propagate
uncaught. The adapter does not validate types before calling, so a malformed
`raw.metadata` (e.g. an ingress layer that passes the body as a decoded
`str`) crashes `verify_and_ack` instead of returning 401.

**Fix:** Validate types in `verify_and_ack` before calling
`verify_callback_signature`, and/or broaden the `try/except` in
`verify_callback_signature` to catch `TypeError`/`AttributeError`:
```python
# adapter.py
if not isinstance(timestamp, str) or not isinstance(request_body, (bytes, bytearray)):
    return AckResponse(
        accepted=False, status_code=401, idempotency_key=idem_key,
        metadata={**base_meta, "signature_status": "missing"},
    )
```
```python
# signature.py
try:
    sig = bytes.fromhex(signature_hex)
    msg = timestamp.encode("utf-8") + request_body
except (ValueError, TypeError, AttributeError):
    return False
```

### WR-03: op=13 payload with malformed `d` silently accepted as normal verified callback

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:123-148`
**Issue:** When `payload.get("op") == 13` but `d` is not a `Mapping` (missing,
`None`, or a scalar), the `isinstance(challenge_data, Mapping)` branch is
skipped and execution falls through to the final `return AckResponse(...,
"verified")` on line 143. The callback is accepted as a normal verified
message even though it declared `op=13` (a validation challenge) with
malformed payload data. This silently swallows a protocol-level anomaly
rather than rejecting or flagging it.

**Fix:** When `op == 13` is present, require well-formed challenge data or
reject explicitly:
```python
if payload.get("op") == 13:
    challenge_data = payload.get("d")
    if not isinstance(challenge_data, Mapping):
        return AckResponse(
            accepted=False, status_code=400, idempotency_key=idem_key,
            metadata={**base_meta, "signature_status": "verified",
                      "error": "op13_missing_challenge_data"},
        )
    ...
```

### WR-04: op=13 challenge signs empty values when `plain_token`/`event_ts` missing

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:127-131`
**Issue:** `_optional_string(...) or ""` defaults missing `plain_token` or
`event_ts` to the empty string, then signs `event_ts + plain_token` (which
becomes `""`). The resulting signature is over degenerate input and the QQ
platform will reject the challenge response, but the adapter returns
`accepted=True, 200` as if the challenge was handled successfully. Required
fields should be validated before signing.

**Fix:**
```python
plain_token = _optional_string(challenge_data.get("plain_token"))
event_ts = _optional_string(challenge_data.get("event_ts"))
if not plain_token or not event_ts:
    return AckResponse(
        accepted=False, status_code=400, idempotency_key=idem_key,
        metadata={**base_meta, "signature_status": "verified",
                  "error": "op13_missing_fields"},
    )
challenge_response = handle_validation_challenge(
    bot_secret, plain_token, event_ts
)
```

## Info

### IN-01: Non-constant-time signing (RFC 8032 reference limitation)

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/_ed25519.py:86-94`
**Issue:** The vendored RFC 8032 reference `sign` uses non-constant-time
scalar multiplication (`point_mul`) with the private scalar `a`. This is a
known property of the reference implementation and is acceptable for
verification (which handles no secret material) and for the fixture-grade
adapter scope. However, the op=13 challenge signing path does use the private
key. If this code is ever promoted to production signing, a constant-time
implementation (e.g. `pynacl`/`cryptography`) should replace the vendored
reference. No change needed for the current fixture-grade scope.

### IN-02: `payload` and `request_body` trust boundary not enforced

**File:** `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:67, 96-98, 124`
**Issue:** The adapter verifies the signature over `request_body` (raw bytes
from `raw.metadata["request_body"]`) but makes the `op == 13` decision from
`payload` (parsed dict from `raw.metadata["payload"]`). These are independent
metadata entries; the adapter trusts that the ingress layer keeps them
consistent (i.e. `payload` is the JSON parse of `request_body`). If they
diverge — e.g. a verified signature over a benign body paired with a crafted
`payload` dict declaring `op=13` — the adapter would issue a challenge
response for a payload that was not the one signed. This is a runtime contract
issue rather than an adapter bug, but documenting the invariant (or re-parsing
`request_body` to derive `payload` inside the adapter) would harden the
boundary.

---

_Reviewed: 2026-07-07T09:28:07Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
