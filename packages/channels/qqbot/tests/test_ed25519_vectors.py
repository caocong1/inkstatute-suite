"""Known-answer tests for the vendored Ed25519 module against official QQ demo vectors.

Verifies that ``_ed25519.py`` (RFC 8032 Section 6.1 reference) produces the
exact public key and signature published in the official QQ Bot documentation
demo vectors, and that tampering / wrong-key / corrupted-signature cases are
rejected.
"""

from __future__ import annotations

import unittest

from inkstatute_channels_qqbot._ed25519 import secret_to_public, sign, verify

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


class Ed25519VectorsTests(unittest.TestCase):
    """Known-answer tests for vendored Ed25519 against official QQ demo vectors."""

    def test_secret_to_public_matches_demo(self) -> None:
        """secret_to_public(DEMO_SEED) produces exactly DEMO_PUBLIC_KEY."""
        public_key = secret_to_public(DEMO_SEED)
        self.assertEqual(len(public_key), 32)
        self.assertListEqual(list(public_key), list(DEMO_PUBLIC_KEY))

    def test_sign_matches_demo_signature(self) -> None:
        """sign(DEMO_SEED, timestamp+body) produces exactly DEMO_SIGNATURE_HEX."""
        msg = DEMO_SIG_TIMESTAMP.encode("utf-8") + DEMO_SIG_BODY
        sig = sign(DEMO_SEED, msg)
        self.assertEqual(len(sig), 64)
        self.assertEqual(sig.hex(), DEMO_SIGNATURE_HEX)

    def test_verify_accepts_demo_signature(self) -> None:
        """verify(DEMO_PUBLIC_KEY, timestamp+body, demo_sig) returns True."""
        msg = DEMO_SIG_TIMESTAMP.encode("utf-8") + DEMO_SIG_BODY
        sig = bytes.fromhex(DEMO_SIGNATURE_HEX)
        self.assertTrue(verify(DEMO_PUBLIC_KEY, msg, sig))

    def test_verify_rejects_tampered_message(self) -> None:
        """verify with 1 byte changed in message returns False."""
        tampered_body = DEMO_SIG_BODY.replace(b"op", b"ip", 1)
        msg = DEMO_SIG_TIMESTAMP.encode("utf-8") + tampered_body
        sig = bytes.fromhex(DEMO_SIGNATURE_HEX)
        self.assertFalse(verify(DEMO_PUBLIC_KEY, msg, sig))

    def test_verify_rejects_wrong_public_key(self) -> None:
        """verify with a wrong public key returns False."""
        wrong_key = bytes(32)  # all zeros — not a valid public key
        msg = DEMO_SIG_TIMESTAMP.encode("utf-8") + DEMO_SIG_BODY
        sig = bytes.fromhex(DEMO_SIGNATURE_HEX)
        self.assertFalse(verify(wrong_key, msg, sig))

    def test_verify_rejects_corrupted_signature(self) -> None:
        """verify with a corrupted signature (flipped byte) returns False."""
        msg = DEMO_SIG_TIMESTAMP.encode("utf-8") + DEMO_SIG_BODY
        sig = bytearray(bytes.fromhex(DEMO_SIGNATURE_HEX))
        sig[0] ^= 0xFF  # flip all bits of first byte
        self.assertFalse(verify(DEMO_PUBLIC_KEY, msg, bytes(sig)))

    def test_verify_rejects_wrong_signature_length(self) -> None:
        """verify with signature length != 64 returns False."""
        msg = DEMO_SIG_TIMESTAMP.encode("utf-8") + DEMO_SIG_BODY
        short_sig = bytes.fromhex(DEMO_SIGNATURE_HEX)[:32]
        self.assertFalse(verify(DEMO_PUBLIC_KEY, msg, short_sig))

    def test_round_trip_sign_verify(self) -> None:
        """Round-trip: sign(seed, msg) -> verify(public, msg, sig) -> True."""
        seed = b"0123456789abcdef0123456789abcdef"
        msg = b"arbitrary message for round-trip test"
        public = secret_to_public(seed)
        sig = sign(seed, msg)
        self.assertEqual(len(sig), 64)
        self.assertTrue(verify(public, msg, sig))

    def test_round_trip_verify_rejects_tampered(self) -> None:
        """Round-trip: tampered message after sign -> verify -> False."""
        seed = b"0123456789abcdef0123456789abcdef"
        msg = b"original message"
        public = secret_to_public(seed)
        sig = sign(seed, msg)
        self.assertFalse(verify(public, b"tampered message", sig))


if __name__ == "__main__":
    unittest.main()
