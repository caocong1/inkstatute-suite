"""Protocol helpers for sanitized WeCom callback handling."""

from __future__ import annotations

from typing import Any, Mapping


class RawPayloadForbiddenError(ValueError):
    """Raised when a callback contains raw payload material."""


def verify_callback_signature(
    token: str,
    timestamp: str,
    nonce: str,
    msg_signature: str,
    encrypted_payload: str,
) -> bool:
    """Verify a WeCom-style callback signature."""

    raise NotImplementedError


def parse_callback_envelope(callback: Mapping[str, Any]) -> dict[str, Any]:
    """Parse a sanitized callback envelope into normalized scalar fields."""

    raise NotImplementedError


def ack_response() -> str:
    """Return the immediate WeCom ACK body."""

    raise NotImplementedError


__all__ = [
    "RawPayloadForbiddenError",
    "ack_response",
    "parse_callback_envelope",
    "verify_callback_signature",
]
