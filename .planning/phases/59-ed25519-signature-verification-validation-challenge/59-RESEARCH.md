# Phase 59: Ed25519 Signature Verification + Validation Challenge — Technical Research

**Phase:** 59 — Ed25519 Signature Verification + Validation Challenge
**Requirements:** INGRESS-01, INGRESS-02
**Depends on:** Phase 58 (complete)
**Researched:** 2026-07-07
**Status:** Complete

## User Constraints

### Decisions (from CONTEXT.md)

Discuss phase was skipped per user setting (`workflow.skip_discuss`). All implementation choices are at Claude's discretion. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

### Claude's Discretion

All implementation choices are at Claude's discretion — use ROADMAP phase goal, success criteria, and codebase conventions.

### Deferred Ideas

None — discuss phase skipped.

## Project Constraints (from AGENTS.md)

- Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads.
- WeCom keys, callback token, encoding AES keys, runtime message payloads, and media files must not be committed.
- Keep changes scoped to the active GSD phase and its plan.
- Do not introduce a new service, database, queue, or runtime dependency unless the V2 PRD or the active GSD plan requires it.
- `dependencies = []` invariant must hold for QQBot channel package — use Python stdlib only. `[VERIFIED: codebase — packages/channels/qqbot/pyproject.toml]`
- All 24 existing V2 gates must remain green throughout v1.8 (ADAPTER-04 cross-cutting safety).
- Frozen ChannelAdapter Protocol, BackendAdapter Protocol, platform-contract enums/schemas, and channel-core modules must not be modified.

## Critical Finding: Ed25519 Dependency Conflict

### The Problem

QQ Bot webhook callbacks use **Ed25519** signature verification `[CITED: bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/sign.html]`. Python's standard library (verified on Python 3.14.6, the project runtime) has **NO Ed25519 support**:

- `hashlib` provides: SHA-1/2/3, SHAKE, BLAKE2, MD5, SM3 — **no Ed25519** `[VERIFIED: runtime introspection — hashlib.algorithms_available]`
- `ssl` module: no Ed25519 key operations exposed `[VERIFIED: runtime introspection]`
- `cryptography` package: **NOT installed** `[VERIFIED: runtime — ModuleNotFoundError]`
- `pynacl` (PyNaCl) package: **NOT installed** `[VERIFIED: runtime — ModuleNotFoundError]`
- No crypto library is used anywhere in the project — RBAC tokens use stdlib `hashlib` + `hmac` (HMAC-SHA) `[VERIFIED: codebase — packages/rbac/src/rbac/token.py]`

### The Invariant Conflict

Phase 58 Success Criterion 5 requires `dependencies = []` in `packages/channels/qqbot/pyproject.toml`. This is **actively tested** by:

```python
# packages/channels/qqbot/tests/test_v1_8_safety_baseline.py:58-61
def test_qqbot_pyproject_has_empty_dependencies(self) -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    self.assertIn("dependencies = []", content)
```

`[VERIFIED: codebase — packages/channels/qqbot/tests/test_v1_8_safety_baseline.py]`

Adding `cryptography` or `pynacl` to `dependencies` would **break this test** and violate the Phase 58 safety baseline.

### Recommended Solution: Vendor Pure-Python Ed25519

**Vendor the RFC 8032 Section 6.1 reference Ed25519 implementation** as an internal module `_ed25519.py` inside the qqbot package. This preserves `dependencies = []` (stdlib `hashlib` only) and requires no external packages.

**Why this is safe and appropriate:**

1. **RFC 8032 Section 6.1** provides a complete, public-domain reference Ed25519 implementation in pure Python (~80 lines) using only `hashlib.sha512` `[CITED: datatracker.ietf.org/doc/html/rfc8032#section-6]`
2. The reference code is **well-tested** — it is the canonical illustration of the Ed25519 algorithm
3. **Performance is acceptable**: ~10ms per verify, ~3ms per sign (pure Python) `[CITED: github.com/warner/python-pure25519]`. QQ Bot webhook callbacks are low-RPS; this is not a bottleneck
4. **No new runtime dependency** — `dependencies = []` invariant holds
5. **Vendoring crypto code** is a security-sensitive decision, but the RFC 8032 reference is the most audited pure-Python Ed25519 available, and the alternative (adding a dependency) violates a frozen safety invariant

**Confidence: HIGH** — verified by running the RFC 8032 reference code against official QQ demo vectors (see below).

**Alternative considered and rejected:** Adding `cryptography` or `pynacl` as a dependency. Rejected because it breaks the `dependencies = []` invariant (Phase 58 SC-5) and the `test_v1_8_safety_baseline.py` test.

## QQ Bot Ed25519 Algorithm (Verified Against Official Demo Vectors)

### Source

Official QQ Bot documentation: `bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/sign.html` `[CITED]`

### Step 1: Keypair Derivation from BotSecret

The BotSecret is transformed into a 32-byte Ed25519 seed by **repeating** the secret string until it reaches 32 bytes, then truncating to 32 bytes:

```python
seed = bot_secret.encode("utf-8")
while len(seed) < 32:
    seed = seed * 2
seed = seed[:32]  # Ed25519 seed (32 bytes)
```

Then standard Ed25519 key derivation from seed (SHA-512 of seed, clamp first 32 bytes as scalar):

```python
public_key = secret_to_public(seed)   # 32 bytes
private_key = seed                     # seed IS the private key in Ed25519
```

`[CITED: bot.q.qq.com — sign.html, Go demo code]`

**Official demo vector (VERIFIED):**
```
Input:
  demo-secret-value (redacted)  (28 bytes)
  seed:   naOC0ocQE3shWLAfffVLB1rhYPG7naOC  (32 bytes, repeated+truncated)

Output:
  publicKey: [215, 195, 98, 254, 120, 174, 248, 31, 242, 50, 135, 180,
              147, 98, 139, 93, 176, 42, 60, 79, 227, 11, 33, 94, 77,
              25, 96, 155, 93, 118, 103, 58]
```

**Verification result:** The RFC 8032 reference code produces EXACTLY this public key from the demo seed. `[VERIFIED: runtime — executed RFC 8032 reference against QQ demo vector, public key bytes match exactly]`

### Step 2: Signature Verification (INGRESS-01)

For each webhook callback, verify the signature over `timestamp + request_body`:

```python
# Headers
signature_hex = headers["X-Signature-Ed25519"]      # 128 hex chars = 64 bytes
timestamp     = headers["X-Signature-Timestamp"]     # e.g. "1725442341"

# Decode signature
sig = bytes.fromhex(signature_hex)                   # 64 bytes

# Build message: timestamp string bytes + raw HTTP body bytes (concatenated)
msg = timestamp.encode("utf-8") + request_body_bytes

# Verify
valid = ed25519_verify(public_key, msg, sig)
```

`[CITED: bot.q.qq.com — sign.html]`

**Official demo vector (VERIFIED):**
```
Input:
  demo-secret-value (redacted)
  body:      {\n  "op": 0,\n  "d": {},\n  "t": "GATEWAY_EVENT_NAME"\n}
             (pretty-printed JSON — HTML docs render newlines as spaces)
  timestamp: 1725442341

Output:
  sig: 865ad13a61752ca65e26bde6676459cd36cf1be609375b37bd62af366e1dc25a
       8dc789ba7f14e017ada3d554c671a911bfdf075ba54835b23391d509579ed002
```

**Verification result:** The RFC 8032 reference code produces EXACTLY this signature when the body is the pretty-printed JSON (with `\n` newlines — the HTML docs collapsed newlines to spaces in rendering). `[VERIFIED: runtime — executed RFC 8032 reference against QQ demo vector, signature matches with newline-formatted JSON body]`

**Important pitfall:** The raw body must be the **exact bytes** received in the HTTP request body. Do not re-serialize or normalize the JSON — use the raw bytes as received. The demo vector confirms that QQ signs the exact raw body bytes (including whitespace/newlines).

### Step 3: Validation Challenge — op=13 (INGRESS-02)

When QQ sends an op=13 payload to validate the callback URL, sign `event_ts + plain_token` and return `{plain_token, signature}`:

```python
# Incoming payload (op=13):
# {"d": {"plain_token": "...", "event_ts": "..."}, "op": 13}
plain_token = payload["d"]["plain_token"]
event_ts    = payload["d"]["event_ts"]

# Build message: event_ts + plain_token (string concatenation, UTF-8 encoded)
msg = (event_ts + plain_token).encode("utf-8")

# Sign with private key (seed)
signature = ed25519_sign(seed, msg)
signature_hex = signature.hex()

# Response body
response = {"plain_token": plain_token, "signature": signature_hex}
```

`[CITED: bot.q.qq.com — event-emit.html, Go demo code]`

**Official demo vector:**
```
Input:
  body: {"d":{"plain_token":"Arq0D5A61EgUu4OxUvOp","event_ts":"1725442341"},"op":13}

Expected response:
  {"plain_token": "Arq0D5A61EgUu4OxUvOp",
   "signature": "87befc99c42c651b3aac0278e71ada338433ae26fcb24307bdc5ad38c1adc2d0
                 1bcfcadc0842edac85e85205028a1132afe09280305f13aa6909ffc2d652c706"}
```

**Note:** The challenge demo does not specify which BotSecret was used. The algorithm is standard Ed25519 signing (`sign(seed, event_ts + plain_token)`) and is confirmed correct by the signature verification demo (same algorithm, same key derivation). The plan should generate a self-consistent challenge test vector by signing with the known demo secret and verifying the round-trip. `[VERIFIED: algorithm confirmed via signature demo; challenge demo secret not published]`

### Signature Validation Checks (from QQ Go demo code)

The QQ official Go demo includes additional signature sanity checks:

```go
if len(sig) != ed25519.SignatureSize || sig[63]&224 != 0 {
    return false
}
```

- `len(sig) != 64` → reject (64-byte Ed25519 signature)
- `sig[63] & 224 != 0` → reject (top 3 bits of S must be zero — this is a Go ed25519 library internal check, NOT a standard Ed25519 requirement)

**Recommendation:** The `sig[63] & 224` check is a Go-specific implementation detail, not a standard Ed25519 requirement. The RFC 8032 reference `verify()` already checks `s >= q` (S must be in range 0..L-1), which is the standard validity check. Do NOT replicate the Go-specific `sig[63] & 224` check — it would reject valid signatures from other Ed25519 implementations. `[ASSUMED — based on RFC 8032 analysis; the Go check is stricter than the standard]`

## Standard Stack

### Vendored Ed25519 Module

- **`packages/channels/qqbot/src/inkstatute_channels_qqbot/_ed25519.py`** — vendored RFC 8032 Section 6.1 reference implementation (pure Python, `hashlib.sha512` only). Internal module (underscore prefix). Public functions: `secret_to_public(seed) -> bytes`, `sign(seed, msg) -> bytes`, `verify(public, msg, signature) -> bool`. `[CITED: datatracker.ietf.org/doc/html/rfc8032#section-6]`

### Signature Module

- **`packages/channels/qqbot/src/inkstatute_channels_qqbot/signature.py`** — QQ Bot signature verification and validation challenge handling. Public API:
  - `derive_keypair(bot_secret: str) -> tuple[bytes, bytes]` — returns `(public_key, seed/private_key)` using the repeat-to-32-bytes algorithm
  - `verify_callback_signature(public_key, signature_hex, timestamp, request_body) -> bool` — verifies `X-Signature-Ed25519` over `timestamp + request_body`
  - `handle_validation_challenge(bot_secret, plain_token, event_ts) -> dict` — signs `event_ts + plain_token` and returns `{"plain_token": ..., "signature": ...}`

### Configuration

- **`packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py`** — existing `QQBotChannelConfig` already has `token_secret_ref` field. The BotSecret reference should be added as a new field `bot_secret_ref: str | None = None` (reference only, no raw secret). `[VERIFIED: codebase — packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py]`

### Test Framework

- **`unittest`** (stdlib) — matches all existing qqbot tests `[VERIFIED: codebase — packages/channels/qqbot/tests/]`
- No pytest-specific features used; all tests are `unittest.TestCase` subclasses

## Architecture Patterns

### Module Layout

```
packages/channels/qqbot/src/inkstatute_channels_qqbot/
├── __init__.py          # exports QQBotChannelAdapter, QQBotChannelConfig
├── _ed25519.py          # NEW: vendored RFC 8032 Ed25519 (internal, ~80 lines)
├── signature.py         # NEW: QQ Bot signature verify + validation challenge
├── config.py            # MODIFIED: add bot_secret_ref field
└── adapter.py           # MODIFIED: verify_and_ack uses signature.py (SC-2)
```

### Signature Verification Flow (verify_and_ack integration)

The existing `verify_and_ack` method in `adapter.py` (line 60-75) currently returns `signature_status: "secret_ref_required"` with no actual verification `[VERIFIED: codebase — packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py:60-75]`. Phase 59 should:

1. Accept signature headers via `RawInbound.metadata` (e.g., `metadata["x_signature_ed25519"]`, `metadata["x_signature_timestamp"]`, `metadata["request_body"]`)
2. If signature headers are present, verify using `signature.verify_callback_signature()`
3. If verification fails → return `AckResponse(accepted=False, status_code=401, ...)` (SC-2)
4. If op=13 validation challenge → return `AckResponse` with validation response body in metadata (SC-3)
5. If signature headers absent → reject with 401 (SC-2)

**Key constraint:** `verify_and_ack` is one of the 6 frozen Protocol methods — its **signature must not change**. QQ-specific data flows through `RawInbound.metadata` (input) and `AckResponse.metadata` (output). `[VERIFIED: codebase — RawInbound and AckResponse both have `metadata: JsonObject` fields]`

### Raw Body Handling

The signature is computed over `timestamp + request_body` where `request_body` is the **exact HTTP request body bytes**. The raw body must be passed through `RawInbound.metadata["request_body"]` as `bytes` (not re-serialized JSON). This is critical — any re-serialization breaks signature verification (confirmed by the demo vector requiring pretty-printed JSON with newlines). `[VERIFIED: runtime — demo vector only matches with exact body bytes including newlines]`

## Don't Hand-Roll

- **Ed25519 algorithm**: Use the RFC 8032 Section 6.1 reference implementation verbatim. Do NOT modify the curve math, scalar clamping, or point operations. The reference is the canonical algorithm illustration. `[CITED: datatracker.ietf.org/doc/html/rfc8032#section-6]`
- **SHA-512**: Use `hashlib.sha512` (stdlib). The RFC 8032 reference uses this directly.
- **Hex encoding/decoding**: Use stdlib `bytes.fromhex()` and `bytes.hex()`.
- **Constant-time comparison**: For signature verification result, use `hmac.compare_digest` if comparing hex strings, though the RFC 8032 `verify()` returns a bool directly.

## Common Pitfalls

1. **Raw body re-serialization**: The signature is over the EXACT raw HTTP body bytes. If the webhook handler parses JSON and re-serializes it, the signature will fail. The raw body must be captured before any JSON parsing and passed through as `bytes`. `[VERIFIED: runtime — demo vector requires exact newline-formatted JSON body]`

2. **Seed derivation edge cases**: If `len(bot_secret) >= 32`, the repeat loop doesn't execute and the seed is `bot_secret[:32]`. If `len(bot_secret) < 32`, repeat the secret string until `>= 32` bytes, then truncate to 32. The demo secret is 28 bytes → repeated once → 56 bytes → truncated to 32. `[VERIFIED: runtime — matches official demo]`

3. **HTML doc rendering of demo bodies**: The QQ official docs render JSON bodies with spaces instead of newlines. The actual demo body for the signature vector is pretty-printed JSON with `\n` newlines: `{\n  "op": 0,\n  "d": {},\n  "t": "GATEWAY_EVENT_NAME"\n}`. Tests must use the newline-formatted body, not the space-rendered version. `[VERIFIED: runtime — only newline-formatted body produces the expected signature]`

4. **Go-specific `sig[63] & 224` check**: The QQ Go demo includes `sig[63]&224 != 0` as a rejection check. This is a Go `crypto/ed25519` internal detail, NOT a standard Ed25519 requirement. Do NOT replicate this in Python — it would reject valid signatures. Use the RFC 8032 standard check (`s >= q`). `[ASSUMED — based on RFC 8032 vs Go source analysis]`

5. **`dependencies = []` invariant**: Do NOT add `cryptography`, `pynacl`, or any other package to `pyproject.toml` dependencies. The `test_v1_8_safety_baseline.py` test checks for the literal string `dependencies = []` in the file. `[VERIFIED: codebase — packages/channels/qqbot/tests/test_v1_8_safety_baseline.py:58-61]`

6. **BotSecret is a reference, not raw**: Per AGENTS.md, never commit secrets. The config should store `bot_secret_ref` (a reference/name), not the raw BotSecret value. Tests use the official demo secret `naOC0ocQE3shWLAfffVLB1rhYPG7` which is a public documentation demo value, not a production secret. `[VERIFIED: AGENTS.md — "Never commit secrets, tokens..."]`

7. **Protocol method signature freeze**: `verify_and_ack(self, raw: RawInbound) -> AckResponse` — do NOT change this signature. QQ-specific signature data flows through `RawInbound.metadata`. The `test_contract_freeze_not_violated.py` test asserts ChannelAdapter has exactly 6 methods. `[VERIFIED: codebase — packages/channels/qqbot/tests/test_contract_freeze_not_violated.py]`

8. **No wecom_service import**: The `test_no_wecom_import.py` test uses AST inspection to verify no `wecom_service` import in any qqbot source file. The new `signature.py` and `_ed25519.py` must not import from wecom_service. `[VERIFIED: codebase — packages/channels/qqbot/tests/test_no_wecom_import.py]`

## Code Examples

### Vendored _ed25519.py (RFC 8032 Section 6.1 — ~80 lines)

```python
"""Vendored Ed25519 implementation from RFC 8032 Section 6.1.

Pure Python, uses only hashlib.sha512. Internal module — not for direct
import outside the qqbot package.
"""
import hashlib

def sha512(s):
    return hashlib.sha512(s).digest()

p = 2**255 - 19
def modp_inv(x):
    return pow(x, p-2, p)
d = -121665 * modp_inv(121666) % p
q = 2**252 + 27742317777372353535851937790883648493
def sha512_modq(s):
    return int.from_bytes(sha512(s), "little") % q

def point_add(P, Q):
    A, B = (P[1]-P[0])*(Q[1]-Q[0]) % p, (P[1]+P[0])*(Q[1]+Q[0]) % p
    C, D = 2*P[3]*Q[3]*d % p, 2*P[2]*Q[2] % p
    E, F, G, H = B-A, D-C, D+C, B+A
    return (E*F, G*H, F*G, E*H)

def point_mul(s, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1: Q = point_add(Q, P)
        P = point_add(P, P)
        s >>= 1
    return Q

def point_equal(P, Q):
    if (P[0]*Q[2] - Q[0]*P[2]) % p != 0: return False
    if (P[1]*Q[2] - Q[1]*P[2]) % p != 0: return False
    return True

modp_sqrt_m1 = pow(2, (p-1)//4, p)
def recover_x(y, sign):
    if y >= p: return None
    x2 = (y*y-1) * modp_inv(d*y*y+1)
    if x2 == 0: return 0 if not sign else None
    x = pow(x2, (p+3)//8, p)
    if (x*x - x2) % p != 0: x = x * modp_sqrt_m1 % p
    if (x*x - x2) % p != 0: return None
    if (x & 1) != sign: x = p - x
    return x

g_y = 4 * modp_inv(5) % p
g_x = recover_x(g_y, 0)
G = (g_x, g_y, 1, g_x * g_y % p)

def point_compress(P):
    zinv = modp_inv(P[2])
    x = P[0] * zinv % p
    y = P[1] * zinv % p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")

def point_decompress(s):
    if len(s) != 32: raise ValueError("Invalid input length")
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = recover_x(y, sign)
    return (x, y, 1, x*y % p) if x is not None else None

def secret_expand(secret):
    if len(secret) != 32: raise ValueError("Bad seed size")
    h = sha512(secret)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= (1 << 254)
    return (a, h[32:])

def secret_to_public(secret):
    a, _ = secret_expand(secret)
    return point_compress(point_mul(a, G))

def sign(secret, msg):
    a, prefix = secret_expand(secret)
    A = point_compress(point_mul(a, G))
    r = sha512_modq(prefix + msg)
    R = point_mul(r, G)
    Rs = point_compress(R)
    h = sha512_modq(Rs + A + msg)
    s = (r + h * a) % q
    return Rs + int.to_bytes(s, 32, "little")

def verify(public, msg, signature):
    if len(public) != 32: return False
    if len(signature) != 64: return False
    A = point_decompress(public)
    if not A: return False
    Rs = signature[:32]
    R = point_decompress(Rs)
    if not R: return False
    s = int.from_bytes(signature[32:], "little")
    if s >= q: return False
    h = sha512_modq(Rs + public + msg)
    sB = point_mul(s, G)
    hA = point_mul(h, A)
    return point_equal(sB, point_add(R, hA))
```

`[CITED: datatracker.ietf.org/doc/html/rfc8032#section-6 — RFC 8032 Section 6.1 reference code]`

### signature.py — Key Derivation

```python
from ._ed25519 import secret_to_public, sign, verify

def derive_seed(bot_secret: str) -> bytes:
    """Derive 32-byte Ed25519 seed from BotSecret via repeat-to-32 algorithm."""
    seed = bot_secret.encode("utf-8")
    while len(seed) < 32:
        seed = seed * 2
    return seed[:32]

def derive_keypair(bot_secret: str) -> tuple[bytes, bytes]:
    """Returns (public_key, seed) where seed is the Ed25519 private key."""
    seed = derive_seed(bot_secret)
    public_key = secret_to_public(seed)
    return (public_key, seed)
```

### signature.py — Callback Verification

```python
def verify_callback_signature(
    public_key: bytes,
    signature_hex: str,
    timestamp: str,
    request_body: bytes,
) -> bool:
    """Verify X-Signature-Ed25519 over timestamp + request_body."""
    try:
        sig = bytes.fromhex(signature_hex)
    except ValueError:
        return False
    if len(sig) != 64:
        return False
    msg = timestamp.encode("utf-8") + request_body
    return verify(public_key, msg, sig)
```

### signature.py — Validation Challenge (op=13)

```python
def handle_validation_challenge(
    bot_secret: str,
    plain_token: str,
    event_ts: str,
) -> dict[str, str]:
    """Sign event_ts + plain_token and return {plain_token, signature}."""
    _, seed = derive_keypair(bot_secret)
    msg = (event_ts + plain_token).encode("utf-8")
    sig = sign(seed, msg)
    return {"plain_token": plain_token, "signature": sig.hex()}
```

### Test Vector Constants

```python
# Official QQ demo vectors (public documentation values, NOT production secrets)
DEMO_BOT_SECRET = "naOC0ocQE3shWLAfffVLB1rhYPG7"
DEMO_SEED = b"naOC0ocQE3shWLAfffVLB1rhYPG7naOC"  # 32 bytes
DEMO_PUBLIC_KEY = bytes([
    215, 195, 98, 254, 120, 174, 248, 31, 242, 50, 135, 180,
    147, 98, 139, 93, 176, 42, 60, 79, 227, 11, 33, 94, 77,
    25, 96, 155, 93, 118, 103, 58,
])

# Signature verification demo (body is pretty-printed JSON with \n newlines)
DEMO_SIG_BODY = b'{\n  "op": 0,\n  "d": {},\n  "t": "GATEWAY_EVENT_NAME"\n}'
DEMO_SIG_TIMESTAMP = "1725442341"
DEMO_SIGNATURE_HEX = (
    "865ad13a61752ca65e26bde6676459cd36cf1be609375b37bd62af366e1dc25a"
    "8dc789ba7f14e017ada3d554c671a911bfdf075ba54835b23391d509579ed002"
)

# Validation challenge demo
DEMO_CHALLENGE_PLAIN_TOKEN = "Arq0D5A61EgUu4OxUvOp"
DEMO_CHALLENGE_EVENT_TS = "1725442341"
DEMO_CHALLENGE_SIGNATURE_HEX = (
    "87befc99c42c651b3aac0278e71ada338433ae26fcb24307bdc5ad38c1adc2d0"
    "1bcfcadc0842edac85e85205028a1132afe09280305f13aa6909ffc2d652c706"
)
# NOTE: Challenge demo does not publish which BotSecret was used.
# Generate a self-consistent vector: sign with DEMO_BOT_SECRET and verify round-trip.
```

`[VERIFIED: runtime — public key and signature vectors confirmed against RFC 8032 reference code]`

## Test Strategy

### Test Files

1. **`tests/test_ed25519_vectors.py`** (NEW) — RFC 8032 known-answer tests for the vendored `_ed25519.py`:
   - Public key derivation from demo seed matches official demo public key bytes
   - Signature verification: `verify(public_key, timestamp+body, demo_sig)` returns True
   - Signature signing: `sign(seed, timestamp+body)` produces demo_sig hex
   - Round-trip: sign → verify → True; tampered message → verify → False
   - Rejection: wrong key, wrong signature length, corrupted signature

2. **`tests/test_signature.py`** (NEW) — QQ Bot signature module tests:
   - `derive_keypair()` produces correct public key from demo BotSecret
   - `verify_callback_signature()` accepts valid demo signature, rejects invalid
   - `handle_validation_challenge()` returns `{plain_token, signature}` with correct structure
   - HTTP 401 path: missing/invalid signature → rejected
   - op=13 challenge: self-consistent sign→verify round-trip (since demo secret unpublished)
   - Edge cases: empty body, short BotSecret (< 32 bytes), long BotSecret (>= 32 bytes)

3. **Existing tests must remain green:**
   - `test_v1_8_safety_baseline.py` — `dependencies = []` still holds
   - `test_no_wecom_import.py` — new files don't import wecom_service
   - `test_contract_freeze_not_violated.py` — ChannelAdapter still 6 methods
   - `test_feature_flag.py` — flag still default-off
   - All other qqbot tests

### Test Vector Provenance

- **Public key derivation vector**: OFFICIAL, VERIFIED — exact match with QQ demo `[VERIFIED: runtime]`
- **Signature verification vector**: OFFICIAL, VERIFIED — exact match with newline-formatted body `[VERIFIED: runtime]`
- **Validation challenge vector**: OFFICIAL published, but secret unpublished. Use self-consistent round-trip test with the known demo secret. `[VERIFIED: algorithm confirmed via signature demo]`

## Summary of Key Decisions for the Planner

1. **Vendor RFC 8032 Ed25519** as `_ed25519.py` (internal module, ~80 lines, `hashlib.sha512` only). This preserves `dependencies = []`. HIGH confidence.

2. **Create `signature.py`** with `derive_keypair()`, `verify_callback_signature()`, `handle_validation_challenge()`. Uses `_ed25519.py` internally.

3. **Add `bot_secret_ref` field** to `QQBotChannelConfig` (reference only, no raw secret). Modify `config.py` and `from_env()`.

4. **Modify `verify_and_ack` in `adapter.py`** to perform actual signature verification when headers are present in `RawInbound.metadata`. Return 401 on failure. Handle op=13 challenge. Do NOT change the method signature (frozen Protocol).

5. **Tests use official QQ demo vectors** — public key derivation (verified match), signature verification (verified match with newline body), validation challenge (self-consistent round-trip since demo secret unpublished).

6. **All existing safety tests must remain green** — `dependencies = []`, no wecom_service import, 6 Protocol methods, feature flag default-off.

## Confidence Summary

| Claim | Confidence | Source |
|-------|------------|--------|
| Python stdlib has no Ed25519 | HIGH | Runtime introspection (Python 3.14.6) |
| `cryptography`/`pynacl` not installed | HIGH | Runtime — ModuleNotFoundError |
| `dependencies = []` invariant is tested | HIGH | Codebase — test_v1_8_safety_baseline.py |
| RFC 8032 reference produces correct QQ public key | HIGH | Runtime — exact byte match with demo |
| RFC 8032 reference produces correct QQ signature | HIGH | Runtime — exact match with newline body |
| Seed derivation = repeat-to-32 + truncate | HIGH | Official docs + runtime verification |
| Signature = verify(pub, timestamp+request_body, sig) | HIGH | Official docs + runtime verification |
| Challenge = sign(seed, event_ts+plain_token) | HIGH | Official docs; algorithm confirmed via sig demo |
| Challenge demo secret unpublished | MEDIUM | Docs don't specify secret for challenge demo |
| Go `sig[63]&224` check should NOT be replicated | MEDIUM | RFC 8032 analysis (ASSUMED, not runtime-verified) |
| Vendoring is the correct approach | HIGH | All alternatives break frozen invariant |
