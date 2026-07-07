"""QQ Bot signature verification and op=13 validation challenge handling.

Provides Ed25519 key derivation from a BotSecret string (repeat-to-32-bytes
algorithm), webhook callback signature verification over ``timestamp + raw_body``,
and op=13 validation challenge signing. Uses the vendored ``_ed25519`` module
internally — no external crypto packages (stdlib only).
"""

from __future__ import annotations

from ._ed25519 import secret_to_public, sign, verify

__all__ = [
    "derive_seed",
    "derive_keypair",
    "verify_callback_signature",
    "handle_validation_challenge",
]


def derive_seed(bot_secret: str) -> bytes:
    """Derive a 32-byte Ed25519 seed from a BotSecret string.

    The BotSecret is encoded as UTF-8, repeated until it reaches at least
    32 bytes, then truncated to 32 bytes. This matches the official QQ Bot
    key derivation algorithm.

    Raises ``ValueError`` if ``bot_secret`` is empty or not a string —
    callers must validate before calling.
    """
    if not isinstance(bot_secret, str) or not bot_secret:
        raise ValueError("bot_secret must be a non-empty string")
    seed = bot_secret.encode("utf-8")
    while len(seed) < 32:
        seed = seed * 2
    return seed[:32]


def derive_keypair(bot_secret: str) -> tuple[bytes, bytes]:
    """Derive an Ed25519 keypair from a BotSecret string.

    Returns ``(public_key, seed)`` where ``seed`` is the 32-byte Ed25519
    private key (seed) and ``public_key`` is the 32-byte compressed public key.
    """
    seed = derive_seed(bot_secret)
    public_key = secret_to_public(seed)
    return (public_key, seed)


def verify_callback_signature(
    public_key: bytes,
    signature_hex: str,
    timestamp: str,
    raw_body: bytes,
) -> bool:
    """Verify an ``X-Signature-Ed25519`` over ``timestamp + raw_body``.

    Returns ``True`` if the signature is valid, ``False`` otherwise (including
    invalid hex, wrong signature length, type errors, or failed verification).
    Never raises on malformed input — callers can safely reject without crash.
    """
    try:
        sig = bytes.fromhex(signature_hex)
    except (ValueError, TypeError, AttributeError):
        return False
    if len(sig) != 64:
        return False
    try:
        msg = timestamp.encode("utf-8") + raw_body
    except (AttributeError, TypeError):
        return False
    return verify(public_key, msg, sig)


def handle_validation_challenge(
    bot_secret: str,
    plain_token: str,
    event_ts: str,
) -> dict[str, str]:
    """Sign ``event_ts + plain_token`` for the op=13 validation challenge.

    Returns ``{"plain_token": plain_token, "signature": sig_hex}`` to be sent
    as the validation response body. The signature is a 128-char hex string
    (64-byte Ed25519 signature).
    """
    _, seed = derive_keypair(bot_secret)
    msg = (event_ts + plain_token).encode("utf-8")
    sig = sign(seed, msg)
    return {"plain_token": plain_token, "signature": sig.hex()}
