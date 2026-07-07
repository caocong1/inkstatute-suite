# Phase 59: Ed25519 Signature Verification + Validation Challenge - Pattern Map

**Mapped:** 2026-07-07
**Files analyzed:** 6 (4 new, 2 modified)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/_ed25519.py` (NEW) | utility | transform | `packages/rbac/src/rbac/token.py` | role-match (stdlib-only crypto sign/verify) |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/signature.py` (NEW) | service | transform | `packages/rbac/src/rbac/token.py` | role-match (sign/verify service, stdlib only) |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py` (MODIFIED) | config | request-response | itself (`config.py` lines 19-34) | exact (extending existing dataclass) |
| `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` (MODIFIED) | controller | request-response | itself (`adapter.py` lines 60-75 `verify_and_ack`) | exact (modifying existing method) |
| `packages/channels/qqbot/tests/test_ed25519_vectors.py` (NEW) | test | transform | `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py` | role-match (unittest, fixture/vector based) |
| `packages/channels/qqbot/tests/test_signature.py` (NEW) | test | transform | `packages/channels/qqbot/tests/test_qqbot_idempotency.py` | role-match (unittest, helper builders, round-trip) |

## Pattern Assignments

### `packages/channels/qqbot/src/inkstatute_channels_qqbot/_ed25519.py` (utility, transform)

**Analog:** `packages/rbac/src/rbac/token.py` — the codebase's only existing stdlib-only cryptographic sign/verify module.

**Rationale:** No Ed25519 or crypto library exists in the project. The RBAC token module is the closest analog: it implements sign + verify using only `hashlib`/`hmac`, defines a custom error type, and exposes pure functions with no external dependencies. The new `_ed25519.py` follows the same "stdlib-only crypto utility" philosophy but uses `hashlib.sha512` for Ed25519 curve math instead of HMAC.

**Imports pattern** — copy the stdlib-only convention from `packages/rbac/src/rbac/token.py` lines 8-15:
```python
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
```
For `_ed25519.py`, only `import hashlib` is needed (plus `from __future__ import annotations`).

**Module docstring pattern** — copy the docstring style from `token.py` lines 1-6 (purpose + dependency constraint stated upfront):
```python
"""Short-lived HMAC-SHA256 signed tokens with role+tenant claims.

Tokens are ``base64url(payload_json).base64url(hmac_sha256(secret, payload_b64))``.
Verification uses ``hmac.compare_digest`` for constant-time comparison and
rejects expired tokens.  No external dependencies — stdlib only.
"""
```

**Core pattern — vendored RFC 8032 reference code:** The full ~80-line implementation is provided verbatim in RESEARCH.md "Code Examples" section (lines 286-389 of RESEARCH.md). Copy it **exactly** — do not modify curve math, scalar clamping, or point operations. Public functions: `secret_to_public(seed) -> bytes`, `sign(seed, msg) -> bytes`, `verify(public, msg, signature) -> bool`.

**Error handling pattern** — from `token.py` lines 22-24 (custom exception) and lines 88-92 (try/except wrapping decode):
```python
class RbacTokenError(Exception):
    """Raised when an RBAC token is invalid, tampered, or expired."""
```
```python
    try:
        payload_json = _b64url_decode(payload_b64).decode("utf-8")
        provided_sig = _b64decode(sig_b64)
    except Exception as exc:
        raise RbacTokenError("invalid token encoding") from exc
```
The RFC 8032 `verify()` already returns `False` on bad input (no raise). The `point_decompress` and `secret_expand` functions raise `ValueError` on bad input length — keep these as-is.

**`__all__` pattern** — from `token.py` lines 114-120:
```python
__all__ = [
    "DEFAULT_TOKEN_TTL_SECONDS",
    "RbacTokenClaims",
    "RbacTokenError",
    "issue_token",
    "verify_token",
]
```
For `_ed25519.py`: `__all__ = ["secret_to_public", "sign", "verify"]`.

**Critical constraint:** This is an internal module (underscore prefix). It must NOT import from `wecom_service` (enforced by `test_no_wecom_import.py` AST inspection). It must use only `hashlib` from stdlib — no `cryptography`, no `pynacl` (enforced by `dependencies = []` invariant in `test_v1_8_safety_baseline.py:58-61`).

---

### `packages/channels/qqbot/src/inkstatute_channels_qqbot/signature.py` (service, transform)

**Analog:** `packages/rbac/src/rbac/token.py` — sign/verify service with key derivation, stdlib only.

**Rationale:** `signature.py` wraps the vendored `_ed25519.py` with QQ Bot-specific logic (seed derivation from BotSecret, callback signature verification, op=13 challenge signing). This mirrors how `token.py` wraps `hashlib`/`hmac` with RBAC-specific logic (token issuance, verification, claims extraction). Both are pure-function services with no class state.

**Imports pattern** — relative import from the vendored internal module:
```python
from ._ed25519 import secret_to_public, sign, verify
```
Follow the `from __future__ import annotations` convention (all qqbot source files use it — see `adapter.py` line 3, `config.py` line 3).

**Core pattern — key derivation** (from RESEARCH.md lines 396-410):
```python
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

**Core pattern — callback verification** (from RESEARCH.md lines 415-430):
```python
def verify_callback_signature(
    public_key: bytes,
    signature_hex: str,
    timestamp: str,
    raw_body: bytes,
) -> bool:
    """Verify X-Signature-Ed25519 over timestamp + raw_body."""
    try:
        sig = bytes.fromhex(signature_hex)
    except ValueError:
        return False
    if len(sig) != 64:
        return False
    msg = timestamp.encode("utf-8") + raw_body
    return verify(public_key, msg, sig)
```
This mirrors the defensive decode-then-verify pattern from `token.py` lines 88-97 (try/except around decode, then `hmac.compare_digest`).

**Core pattern — validation challenge** (from RESEARCH.md lines 435-445):
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

**`__all__` pattern** — follow `token.py` convention:
```python
__all__ = [
    "derive_seed",
    "derive_keypair",
    "verify_callback_signature",
    "handle_validation_challenge",
]
```

**Critical constraint:** Must NOT import from `wecom_service` (AST-enforced). Must use only stdlib + `._ed25519`. The `raw_body` parameter must be `bytes` (exact HTTP body bytes) — never re-serialized JSON.

---

### `packages/channels/qqbot/src/inkstatute_channels_qqbot/config.py` (config, request-response)

**Analog:** itself — `config.py` lines 11-34 (extending the existing frozen dataclass).

**Rationale:** The file already defines `QQBotChannelConfig` with `token_secret_ref` as a reference-only secret field. The new `bot_secret_ref` field follows the identical pattern.

**Existing pattern to copy** — `config.py` lines 19-24 (field declarations):
```python
    channel_id: str = "qqbot"
    enabled: bool = False
    app_id_ref: str | None = None
    app_secret_ref: str | None = None
    token_secret_ref: str | None = None
    metadata: JsonObject = field(default_factory=dict)
```
Add `bot_secret_ref: str | None = None` after `token_secret_ref` (line 23), following the same `str | None = None` type and default.

**`from_env` pattern to copy** — `config.py` lines 26-34:
```python
    @classmethod
    def from_env(cls, mapping: Mapping[str, str]) -> "QQBotChannelConfig":
        value = mapping.get("INKSTATUTE_QQBOT_CHANNEL_ENABLED", "")
        return cls(
            enabled=value.lower() in {"1", "true", "yes"},
            app_id_ref=mapping.get("INKSTATUTE_QQBOT_APP_ID_REF") or None,
            app_secret_ref=mapping.get("INKSTATUTE_QQBOT_APP_SECRET_REF") or None,
            token_secret_ref=mapping.get("INKSTATUTE_QQBOT_TOKEN_SECRET_REF") or None,
        )
```
Add `bot_secret_ref=mapping.get("INKSTATUTE_QQBOT_BOT_SECRET_REF") or None,` to the `cls(...)` call, following the same env-var-name → ref pattern.

**Test pattern to follow** — `test_qqbot_channel_adapter.py` lines 91-107 (`test_config_keeps_secret_refs_only`):
```python
    def test_config_keeps_secret_refs_only(self) -> None:
        config = QQBotChannelConfig.from_env(
            {
                "INKSTATUTE_QQBOT_CHANNEL_ENABLED": "1",
                "INKSTATUTE_QQBOT_APP_ID_REF": "secret://qqbot/app-id",
                "INKSTATUTE_QQBOT_APP_SECRET_REF": "secret://qqbot/app-secret",
                "INKSTATUTE_QQBOT_TOKEN_SECRET_REF": "secret://qqbot/token",
            }
        )
        self.assertEqual(config.app_id_ref, "secret://qqbot/app-id")
        ...
        rendered = str(asdict(config))
        self.assertNotIn("raw-token", rendered)
```
The new `bot_secret_ref` should be testable the same way — reference only, no raw secret in `asdict` output.

**Critical constraint:** Per AGENTS.md, store `bot_secret_ref` (a reference/name like `secret://qqbot/bot-secret`), NOT the raw BotSecret value. The frozen `@dataclass(frozen=True, slots=True)` decorator must remain unchanged.

---

### `packages/channels/qqbot/src/inkstatute_channels_qqbot/adapter.py` (controller, request-response)

**Analog:** itself — `adapter.py` lines 60-75 (`verify_and_ack` method).

**Rationale:** The existing `verify_and_ack` is the exact method being modified. It currently returns a stub `signature_status: "secret_ref_required"`. Phase 59 replaces this with actual Ed25519 verification + op=13 challenge handling. The method signature MUST NOT change (frozen Protocol — enforced by `test_contract_freeze_not_violated.py:31-42`).

**Existing method to modify** — `adapter.py` lines 60-75:
```python
    async def verify_and_ack(self, raw: RawInbound) -> AckResponse:
        payload = self._payload_from_raw(raw)
        idem_key = raw.idempotency_key or _stable_id("qqbot-ack", raw.payload_ref)
        return AckResponse(
            accepted=self._config.enabled,
            status_code=200 if self._config.enabled else 503,
            idempotency_key=idem_key,
            metadata={
                "channel_id": self._config.channel_id,
                "payload_ref": raw.payload_ref,
                "signature_status": "secret_ref_required",
                "fixture_only": True,
                "network_io": False,
                "payload_kind": payload.get("type") or payload.get("kind") or "message",
            },
        )
```

**Metadata extraction pattern** — from `adapter.py` lines 151-160 (`_payload_from_raw`):
```python
    def _payload_from_raw(self, raw: RawInbound) -> JsonObject:
        payload = raw.metadata.get("payload")
        if isinstance(payload, Mapping):
            values: JsonObject = dict(payload)
        else:
            values = dict(raw.metadata)
            values.pop("payload", None)
```
Signature headers flow through `raw.metadata` the same way — extract `raw.metadata.get("x_signature_ed25519")`, `raw.metadata.get("x_signature_timestamp")`, `raw.metadata.get("raw_body")`.

**AckResponse construction pattern** — from `adapter.py` lines 63-75 (the return statement above). The 401 rejection path follows the same shape:
```python
        return AckResponse(
            accepted=False,
            status_code=401,
            idempotency_key=idem_key,
            metadata={
                "channel_id": self._config.channel_id,
                "payload_ref": raw.payload_ref,
                "signature_status": "invalid",
                ...
            },
        )
```

**op=13 challenge response pattern** — when op=13 is detected in the payload, return `AckResponse` with the validation challenge response body in `metadata` (e.g., `metadata["validation_challenge_response"] = {"plain_token": ..., "signature": ...}`). The `AckResponse.metadata` field is `JsonObject = dict[str, Any]` (see `protocols.py` line 46), so nested dicts are allowed.

**Import addition** — add at top of `adapter.py` (after line 23 `from .config import QQBotChannelConfig`):
```python
from .signature import derive_keypair, verify_callback_signature, handle_validation_challenge
```

**Critical constraints:**
1. Method signature `async def verify_and_ack(self, raw: RawInbound) -> AckResponse` MUST NOT change — `test_contract_freeze_not_violated.py:31-42` asserts exactly 6 methods with these names.
2. Must NOT import from `wecom_service` — `test_no_wecom_import.py:31-38` AST-inspects `adapter.py`.
3. The `raw_body` from `raw.metadata["raw_body"]` must be passed as `bytes` to `verify_callback_signature()` — never re-serialize.
4. If `bot_secret_ref` is None (not configured), preserve existing behavior (reject or stub).

---

### `packages/channels/qqbot/tests/test_ed25519_vectors.py` (test, transform)

**Analog:** `packages/channels/qqbot/tests/test_qqbot_channel_adapter.py` — unittest TestCase with fixture-based assertions.

**Rationale:** All qqbot tests use `unittest.TestCase` (stdlib, no pytest). The adapter test file shows the project convention: top-level helper functions for fixtures, `setUp` for adapter instantiation, `self.assertX` assertions.

**Imports pattern** — from `test_qqbot_channel_adapter.py` lines 1-9:
```python
from __future__ import annotations

import asyncio
import unittest
from dataclasses import asdict

from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
from platform_contract.events import AgentTurn, FeedbackEvent
from platform_runtime.protocols import ChannelDelivery, RawInbound
```
For `test_ed25519_vectors.py`, import from the internal module:
```python
from __future__ import annotations

import unittest

from inkstatute_channels_qqbot._ed25519 import secret_to_public, sign, verify
```

**Test class structure** — from `test_qqbot_channel_adapter.py` lines 76-89 and 110-112:
```python
class QQBotChannelConfigTests(unittest.TestCase):
    def test_config_defaults_to_disabled(self) -> None:
        self.assertFalse(QQBotChannelConfig().enabled)

class QQBotChannelAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = QQBotChannelAdapter(QQBotChannelConfig(enabled=True))
```

**Test vector constants** — define as module-level constants (from RESEARCH.md lines 449-476):
```python
DEMO_BOT_SECRET = "naOC0ocQE3shWLAfffVLB1rhYPG7"
DEMO_SEED = b"naOC0ocQE3shWLAfffVLB1rhYPG7naOC"  # 32 bytes
DEMO_PUBLIC_KEY = bytes([215, 195, 98, 254, ...])  # 32 bytes
DEMO_SIG_BODY = b'{\n  "op": 0,\n  "d": {},\n  "t": "GATEWAY_EVENT_NAME"\n}'
DEMO_SIG_TIMESTAMP = "1725442341"
DEMO_SIGNATURE_HEX = (
    "865ad13a61752ca65e26bde6676459cd36cf1be609375b37bd62af366e1dc25a"
    "8dc789ba7f14e017ada3d554c671a911bfdf075ba54835b23391d509579ed002"
)
```

**Assertion pattern** — from `test_qqbot_channel_adapter.py` lines 179-186:
```python
    def test_ack_records_payload_ref_and_idempotency_key(self) -> None:
        ack = run(self.adapter.verify_and_ack(text_raw()))
        self.assertTrue(ack.accepted)
        self.assertEqual(ack.metadata["channel_id"], "qqbot")
```
Use `self.assertEqual`, `self.assertTrue`, `self.assertFalse`, `self.assertListEqual` for byte comparisons.

**Test cases to implement** (from RESEARCH.md lines 484-489):
- Public key derivation: `secret_to_public(DEMO_SEED)` == `DEMO_PUBLIC_KEY`
- Signature verification: `verify(DEMO_PUBLIC_KEY, timestamp+body, demo_sig)` returns True
- Signature signing: `sign(DEMO_SEED, timestamp+body)` produces `DEMO_SIGNATURE_HEX`
- Round-trip: sign → verify → True; tampered message → verify → False
- Rejection: wrong key, wrong signature length, corrupted signature

---

### `packages/channels/qqbot/tests/test_signature.py` (test, transform)

**Analog:** `packages/channels/qqbot/tests/test_qqbot_idempotency.py` — unittest with helper builder functions and round-trip verification.

**Rationale:** The idempotency test file shows the pattern for testing adapter behavior with constructed `RawInbound` fixtures and verifying round-trip properties. The signature test needs similar helper builders for signature metadata and round-trip sign→verify assertions.

**Imports pattern** — from `test_qqbot_idempotency.py` lines 1-14:
```python
from __future__ import annotations

import asyncio
import unittest

from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
from platform_runtime.protocols import RawInbound
```
For `test_signature.py`:
```python
from __future__ import annotations

import asyncio
import unittest

from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
from inkstatute_channels_qqbot.signature import (
    derive_keypair,
    verify_callback_signature,
    handle_validation_challenge,
)
from platform_runtime.protocols import RawInbound
```

**Helper builder pattern** — from `test_qqbot_idempotency.py` lines 21-44 (`make_text_raw`):
```python
def make_text_raw(
    *,
    turn_id: str = "turn-idem-001",
    conversation_id: str = "conv-idem-001",
    user_id: str = "user-idem-001",
    idempotency_key: str | None = None,
) -> RawInbound:
    return RawInbound(
        channel_id="qqbot",
        payload_ref=f"fixture://qqbot/idem/inbound/{turn_id}",
        received_at="2026-07-04T00:00:00Z",
        idempotency_key=idempotency_key,
        metadata={
            "payload": {
                "type": "message",
                ...
            }
        },
    )
```
Build a similar `make_signed_raw()` helper that includes `x_signature_ed25519`, `x_signature_timestamp`, and `raw_body` in `metadata`.

**Async test runner pattern** — from `test_qqbot_idempotency.py` lines 17-18 and 83-91:
```python
def run(coro):
    return asyncio.run(coro)

class QQBotIdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = QQBotChannelAdapter(QQBotChannelConfig(enabled=True))

    def test_verify_and_ack_idempotent_same_raw(self) -> None:
        raw = make_text_raw()
        ack1 = run(self.adapter.verify_and_ack(raw))
        ack2 = run(self.adapter.verify_and_ack(raw))
        self.assertTrue(ack1.accepted)
```

**401 rejection test pattern** — from `test_qqbot_channel_adapter.py` lines 188-194:
```python
    def test_ack_is_rejected_when_channel_disabled(self) -> None:
        disabled = QQBotChannelAdapter(QQBotChannelConfig(enabled=False))
        ack = run(disabled.verify_and_ack(text_raw()))
        self.assertFalse(ack.accepted)
        self.assertEqual(ack.status_code, 503)
```
The signature 401 test follows the same shape but asserts `status_code == 401` and `accepted == False`.

**Test cases to implement** (from RESEARCH.md lines 491-497):
- `derive_keypair()` produces correct public key from demo BotSecret
- `verify_callback_signature()` accepts valid demo signature, rejects invalid
- `handle_validation_challenge()` returns `{plain_token, signature}` with correct structure
- HTTP 401 path: missing/invalid signature → `AckResponse(accepted=False, status_code=401)`
- op=13 challenge: self-consistent sign→verify round-trip
- Edge cases: empty body, short BotSecret (< 32 bytes), long BotSecret (>= 32 bytes)

## Shared Patterns

### Stdlib-Only Crypto Convention (applies to `_ed25519.py` and `signature.py`)

All cryptographic code in this project uses Python stdlib only — no external crypto packages. This is enforced by the `dependencies = []` invariant in `packages/channels/qqbot/pyproject.toml` (line 15), tested by `test_v1_8_safety_baseline.py:58-61`:
```python
def test_qqbot_pyproject_has_empty_dependencies(self) -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    self.assertIn("dependencies = []", content)
```
**Do NOT add `cryptography`, `pynacl`, or any other package to dependencies.**

The existing analog is `packages/rbac/src/rbac/token.py` which uses only `hashlib`, `hmac`, `base64`, `json`, `time` from stdlib.

### No wecom_service Import (applies to ALL new/modified source files)

`test_no_wecom_import.py` (lines 30-56) uses AST inspection to verify no `wecom_service` import in any qqbot source file. The new `_ed25519.py` and `signature.py` must not import from `wecom_service`. The modified `adapter.py` and `config.py` must not add any `wecom_service` import.

```python
def _imported_modules(source: str) -> list[str]:
    tree = ast.parse(source)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules
```

### Frozen Protocol Method Signature (applies to `adapter.py`)

`verify_and_ack(self, raw: RawInbound) -> AckResponse` is one of 6 frozen ChannelAdapter Protocol methods. `test_contract_freeze_not_violated.py:31-42` asserts:
```python
def test_channel_adapter_method_count_is_6(self) -> None:
    methods = [m for m in dir(ChannelAdapter) if not m.startswith("_")]
    self.assertEqual(len(methods), 6)
    expected = {
        "channel_id",
        "capabilities",
        "verify_and_ack",
        "normalize_inbound",
        "deliver",
        "health",
    }
    self.assertEqual(set(methods), expected)
```
**Do NOT change the method signature.** QQ-specific data flows through `RawInbound.metadata` (input) and `AckResponse.metadata` (output) — both are `JsonObject = dict[str, Any]` (see `protocols.py` lines 38, 46).

### Raw Body Integrity (applies to `signature.py` and `adapter.py`)

The signature is computed over `timestamp + raw_body` where `raw_body` is the **exact HTTP request body bytes**. The raw body must be passed through `RawInbound.metadata["raw_body"]` as `bytes` — never re-serialized JSON. This is confirmed by the official demo vector requiring pretty-printed JSON with `\n` newlines (RESEARCH.md pitfall #3, lines 270-271).

### Reference-Only Secret Storage (applies to `config.py`)

Per AGENTS.md: "Never commit secrets, tokens, runtime databases, logs, customer documents, or raw legal payloads." The config stores `bot_secret_ref` (a reference like `secret://qqbot/bot-secret`), NOT the raw BotSecret. This follows the existing pattern of `app_id_ref`, `app_secret_ref`, `token_secret_ref` — all reference-only fields. Tests use the official public demo secret `naOC0ocQE3shWLAfffVLB1rhYPG7` which is a documentation value, not a production secret.

### Test Framework Convention (applies to both test files)

All qqbot tests use `unittest.TestCase` (stdlib) — no pytest. Follow the pattern from existing test files:
- `from __future__ import annotations` at top
- `import unittest`
- Module-level `def run(coro): return asyncio.run(coro)` for async tests
- Helper builder functions as module-level functions with keyword-only args
- `setUp` method for adapter instantiation
- `self.assertX` assertions (not raw `assert`)
- `if __name__ == "__main__": unittest.main()` at bottom
