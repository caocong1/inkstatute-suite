"""Unit tests for the QQ Bot signature module pure functions.

Tests key derivation, callback signature verification, validation challenge
signing, and edge cases (short/long BotSecret, empty body, invalid hex).
Also includes adapter integration tests for ``verify_and_ack`` signature
verification, 401 rejection, and op=13 validation challenge handling.
"""

from __future__ import annotations

import asyncio
import unittest

from inkstatute_channels_qqbot import QQBotChannelAdapter, QQBotChannelConfig
from inkstatute_channels_qqbot._ed25519 import verify as ed25519_verify
from inkstatute_channels_qqbot.signature import (
    derive_keypair,
    derive_seed,
    handle_validation_challenge,
    verify_callback_signature,
)
from platform_runtime.protocols import RawInbound

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


class DeriveSeedTests(unittest.TestCase):
    """Tests for derive_seed (repeat-to-32-bytes algorithm)."""

    def test_derive_seed_demo_secret(self) -> None:
        """derive_seed produces the 32-byte demo seed from the demo BotSecret."""
        seed = derive_seed(DEMO_BOT_SECRET)
        self.assertEqual(len(seed), 32)
        self.assertEqual(seed, DEMO_SEED)

    def test_derive_seed_short_secret_repeats(self) -> None:
        """Short BotSecret (< 32 bytes) is repeated to reach 32 bytes."""
        short_secret = "abc"  # 3 bytes -> repeated to >= 32 -> truncated to 32
        seed = derive_seed(short_secret)
        self.assertEqual(len(seed), 32)
        # "abc" repeated: "abcabcabc..." -> first 32 bytes
        expected = (short_secret.encode("utf-8") * 12)[:32]
        self.assertEqual(seed, expected)

    def test_derive_seed_long_secret_truncates(self) -> None:
        """Long BotSecret (>= 32 bytes) is truncated to 32 bytes."""
        long_secret = "x" * 40  # 40 bytes -> truncated to 32
        seed = derive_seed(long_secret)
        self.assertEqual(len(seed), 32)
        self.assertEqual(seed, (b"x" * 40)[:32])


class DeriveKeypairTests(unittest.TestCase):
    """Tests for derive_keypair."""

    def test_derive_keypair_public_key_matches_demo(self) -> None:
        """derive_keypair produces a public key matching DEMO_PUBLIC_KEY."""
        public_key, seed = derive_keypair(DEMO_BOT_SECRET)
        self.assertListEqual(list(public_key), list(DEMO_PUBLIC_KEY))
        self.assertEqual(seed, DEMO_SEED)

    def test_derive_keypair_returns_32_byte_keys(self) -> None:
        """Both public_key and seed are 32 bytes."""
        public_key, seed = derive_keypair(DEMO_BOT_SECRET)
        self.assertEqual(len(public_key), 32)
        self.assertEqual(len(seed), 32)


class VerifyCallbackSignatureTests(unittest.TestCase):
    """Tests for verify_callback_signature."""

    def test_verify_accepts_valid_demo_signature(self) -> None:
        """verify_callback_signature accepts the valid demo signature."""
        result = verify_callback_signature(
            DEMO_PUBLIC_KEY, DEMO_SIGNATURE_HEX, DEMO_SIG_TIMESTAMP, DEMO_SIG_BODY
        )
        self.assertTrue(result)

    def test_verify_rejects_invalid_hex(self) -> None:
        """verify_callback_signature with invalid hex returns False (no exception)."""
        result = verify_callback_signature(
            DEMO_PUBLIC_KEY, "not-valid-hex!!", DEMO_SIG_TIMESTAMP, DEMO_SIG_BODY
        )
        self.assertFalse(result)

    def test_verify_rejects_wrong_signature_length(self) -> None:
        """verify_callback_signature with wrong signature length returns False."""
        short_hex = DEMO_SIGNATURE_HEX[:64]  # 32 bytes instead of 64
        result = verify_callback_signature(
            DEMO_PUBLIC_KEY, short_hex, DEMO_SIG_TIMESTAMP, DEMO_SIG_BODY
        )
        self.assertFalse(result)

    def test_verify_rejects_tampered_body(self) -> None:
        """verify_callback_signature with tampered body returns False."""
        tampered_body = DEMO_SIG_BODY.replace(b"op", b"ip", 1)
        result = verify_callback_signature(
            DEMO_PUBLIC_KEY, DEMO_SIGNATURE_HEX, DEMO_SIG_TIMESTAMP, tampered_body
        )
        self.assertFalse(result)

    def test_verify_empty_body(self) -> None:
        """verify_callback_signature works with empty raw_body (timestamp + empty)."""
        public_key, seed = derive_keypair(DEMO_BOT_SECRET)
        from inkstatute_channels_qqbot._ed25519 import sign as ed25519_sign

        msg = DEMO_SIG_TIMESTAMP.encode("utf-8") + b""
        sig = ed25519_sign(seed, msg)
        result = verify_callback_signature(
            public_key, sig.hex(), DEMO_SIG_TIMESTAMP, b""
        )
        self.assertTrue(result)


class HandleValidationChallengeTests(unittest.TestCase):
    """Tests for handle_validation_challenge (op=13)."""

    def test_returns_plain_token_and_signature(self) -> None:
        """handle_validation_challenge returns dict with plain_token and signature."""
        result = handle_validation_challenge(
            DEMO_BOT_SECRET, "test-plain-token", "1725442341"
        )
        self.assertIn("plain_token", result)
        self.assertIn("signature", result)
        self.assertEqual(result["plain_token"], "test-plain-token")

    def test_signature_is_128_char_hex(self) -> None:
        """handle_validation_challenge signature is a valid 128-char hex string."""
        result = handle_validation_challenge(
            DEMO_BOT_SECRET, "test-plain-token", "1725442341"
        )
        sig = result["signature"]
        self.assertEqual(len(sig), 128)
        # Verify it's valid hex
        bytes.fromhex(sig)

    def test_round_trip_sign_verify(self) -> None:
        """Challenge signature can be verified with verify(public_key, msg, sig)."""
        plain_token = "Arq0D5A61EgUu4OxUvOp"
        event_ts = "1725442341"
        result = handle_validation_challenge(DEMO_BOT_SECRET, plain_token, event_ts)
        public_key, _ = derive_keypair(DEMO_BOT_SECRET)
        msg = (event_ts + plain_token).encode("utf-8")
        sig = bytes.fromhex(result["signature"])
        self.assertTrue(ed25519_verify(public_key, msg, sig))

    def test_round_trip_rejects_tampered(self) -> None:
        """Challenge signature verification fails with tampered message."""
        plain_token = "Arq0D5A61EgUu4OxUvOp"
        event_ts = "1725442341"
        result = handle_validation_challenge(DEMO_BOT_SECRET, plain_token, event_ts)
        public_key, _ = derive_keypair(DEMO_BOT_SECRET)
        tampered_msg = (event_ts + "wrong-token").encode("utf-8")
        sig = bytes.fromhex(result["signature"])
        self.assertFalse(ed25519_verify(public_key, tampered_msg, sig))


def run(coro):
    return asyncio.run(coro)


def make_signed_raw(
    *,
    body: bytes = DEMO_SIG_BODY,
    timestamp: str = DEMO_SIG_TIMESTAMP,
    signature_hex: str = DEMO_SIGNATURE_HEX,
    bot_secret: str = DEMO_BOT_SECRET,
    payload: dict | None = None,
    idempotency_key: str | None = "qqbot-sig-idem-1",
) -> RawInbound:
    """Construct a RawInbound with signature headers in metadata."""
    meta: dict = {
        "x_signature_ed25519": signature_hex,
        "x_signature_timestamp": timestamp,
        "request_body": body,
        "bot_secret": bot_secret,
    }
    if payload is not None:
        meta["payload"] = payload
    return RawInbound(
        channel_id="qqbot",
        payload_ref="fixture://qqbot/inbound/signed-1",
        received_at="2026-07-07T00:00:00Z",
        idempotency_key=idempotency_key,
        metadata=meta,
    )


class QQBotAdapterSignatureTests(unittest.TestCase):
    """Adapter integration tests for verify_and_ack signature verification."""

    def setUp(self) -> None:
        self.adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=True, bot_secret_ref="ref://qqbot/bot-secret")
        )

    def test_valid_signature_accepted(self) -> None:
        """verify_and_ack with a valid signature returns accepted=True, 200."""
        ack = run(self.adapter.verify_and_ack(make_signed_raw()))
        self.assertTrue(ack.accepted)
        self.assertEqual(ack.status_code, 200)
        self.assertEqual(ack.metadata["signature_status"], "verified")

    def test_missing_signature_headers_rejected_401(self) -> None:
        """verify_and_ack with missing signature headers returns 401."""
        raw = RawInbound(
            channel_id="qqbot",
            payload_ref="fixture://qqbot/inbound/unsigned-1",
            received_at="2026-07-07T00:00:00Z",
            idempotency_key="qqbot-sig-idem-missing",
            metadata={"payload": {"type": "message"}},
        )
        ack = run(self.adapter.verify_and_ack(raw))
        self.assertFalse(ack.accepted)
        self.assertEqual(ack.status_code, 401)
        self.assertEqual(ack.metadata["signature_status"], "missing")

    def test_invalid_signature_rejected_401(self) -> None:
        """verify_and_ack with an invalid signature returns 401."""
        ack = run(
            self.adapter.verify_and_ack(
                make_signed_raw(signature_hex="00" * 64)
            )
        )
        self.assertFalse(ack.accepted)
        self.assertEqual(ack.status_code, 401)
        self.assertEqual(ack.metadata["signature_status"], "invalid")

    def test_tampered_request_body_rejected_401(self) -> None:
        """verify_and_ack with a tampered request_body returns 401."""
        tampered = DEMO_SIG_BODY.replace(b"op", b"ip", 1)
        ack = run(
            self.adapter.verify_and_ack(make_signed_raw(body=tampered))
        )
        self.assertFalse(ack.accepted)
        self.assertEqual(ack.status_code, 401)
        self.assertEqual(ack.metadata["signature_status"], "invalid")

    def test_op13_validation_challenge_response(self) -> None:
        """verify_and_ack with op=13 returns validation_challenge_response."""
        plain_token = "Arq0D5A61EgUu4OxUvOp"
        event_ts = "1725442341"
        challenge_body = (
            b'{"d":{"plain_token":"' + plain_token.encode()
            + b'","event_ts":"' + event_ts.encode() + b'"},"op":13}'
        )
        # Sign the challenge body so the signature verifies.
        public_key, seed = derive_keypair(DEMO_BOT_SECRET)
        from inkstatute_channels_qqbot._ed25519 import sign as ed25519_sign

        msg = DEMO_SIG_TIMESTAMP.encode("utf-8") + challenge_body
        sig_hex = ed25519_sign(seed, msg).hex()

        payload = {
            "op": 13,
            "d": {"plain_token": plain_token, "event_ts": event_ts},
        }
        raw = make_signed_raw(
            body=challenge_body,
            signature_hex=sig_hex,
            payload=payload,
            idempotency_key="qqbot-sig-idem-op13",
        )
        ack = run(self.adapter.verify_and_ack(raw))
        self.assertTrue(ack.accepted)
        self.assertEqual(ack.status_code, 200)
        self.assertEqual(ack.metadata["signature_status"], "verified")
        challenge = ack.metadata.get("validation_challenge_response")
        self.assertIsNotNone(challenge)
        assert challenge is not None
        self.assertIn("plain_token", challenge)
        self.assertIn("signature", challenge)
        self.assertEqual(challenge["plain_token"], plain_token)

    def test_bot_secret_not_configured_preserves_stub(self) -> None:
        """When bot_secret_ref is None, stub behavior is preserved."""
        adapter = QQBotChannelAdapter(QQBotChannelConfig(enabled=True))
        ack = run(adapter.verify_and_ack(make_signed_raw()))
        self.assertTrue(ack.accepted)
        self.assertEqual(ack.status_code, 200)
        self.assertEqual(ack.metadata["signature_status"], "secret_ref_required")

    def test_channel_disabled_returns_503(self) -> None:
        """When channel is disabled, 503 behavior is preserved."""
        adapter = QQBotChannelAdapter(
            QQBotChannelConfig(enabled=False, bot_secret_ref="ref://qqbot/bot-secret")
        )
        ack = run(adapter.verify_and_ack(make_signed_raw()))
        self.assertFalse(ack.accepted)
        self.assertEqual(ack.status_code, 503)


if __name__ == "__main__":
    unittest.main()
