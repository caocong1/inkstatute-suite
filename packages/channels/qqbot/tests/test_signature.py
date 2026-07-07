"""Unit tests for the QQ Bot signature module pure functions.

Tests key derivation, callback signature verification, validation challenge
signing, and edge cases (short/long BotSecret, empty body, invalid hex).
"""

from __future__ import annotations

import unittest

from inkstatute_channels_qqbot._ed25519 import verify as ed25519_verify
from inkstatute_channels_qqbot.signature import (
    derive_keypair,
    derive_seed,
    handle_validation_challenge,
    verify_callback_signature,
)

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


if __name__ == "__main__":
    unittest.main()
