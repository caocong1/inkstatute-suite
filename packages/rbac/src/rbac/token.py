"""Short-lived HMAC-SHA256 signed tokens with role+tenant claims.

Tokens are ``base64url(payload_json).base64url(hmac_sha256(secret, payload_b64))``.
Verification uses ``hmac.compare_digest`` for constant-time comparison and
rejects expired tokens.  No external dependencies — stdlib only.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from .roles import Role

DEFAULT_TOKEN_TTL_SECONDS = 900


class RbacTokenError(Exception):
    """Raised when an RBAC token is invalid, tampered, or expired."""


@dataclass(frozen=True, slots=True)
class RbacTokenClaims:
    """Claims extracted from a verified RBAC token."""

    role: str
    tenant_id: str
    iat: int
    exp: int


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def issue_token(
    secret: str,
    *,
    role: Role | str,
    tenant_id: str,
    ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
    now: int | None = None,
) -> str:
    """Issue a short-lived HMAC-SHA256 signed token with role+tenant claims.

    Returns ``base64url(payload).base64url(signature)``.
    """
    iat = int(now if now is not None else time.time())
    exp = iat + int(ttl_seconds)
    role_value = role.value if isinstance(role, Role) else str(role)
    payload = {
        "role": role_value,
        "tenant_id": tenant_id,
        "iat": iat,
        "exp": exp,
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    payload_b64 = _b64url_encode(payload_json.encode("utf-8"))
    sig = hmac.new(
        secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{payload_b64}.{sig_b64}"


def verify_token(
    token: str,
    secret: str,
    now: int | None = None,
) -> RbacTokenClaims:
    """Verify an RBAC token's signature and expiry, returning claims.

    Raises ``RbacTokenError`` on invalid format, bad signature, or expiry.
    """
    now_int = int(now if now is not None else time.time())
    if not isinstance(token, str) or token.count(".") != 1:
        raise RbacTokenError("invalid token format")
    payload_b64, sig_b64 = token.split(".")
    try:
        payload_json = _b64url_decode(payload_b64).decode("utf-8")
        provided_sig = _b64url_decode(sig_b64)
    except Exception as exc:
        raise RbacTokenError("invalid token encoding") from exc
    expected_sig = hmac.new(
        secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        raise RbacTokenError("invalid signature")
    try:
        payload = json.loads(payload_json)
    except Exception as exc:
        raise RbacTokenError("invalid payload json") from exc
    try:
        exp = int(payload["exp"])
        iat = int(payload["iat"])
        role = str(payload["role"])
        tenant_id = str(payload["tenant_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RbacTokenError("invalid payload fields") from exc
    if exp <= now_int:
        raise RbacTokenError("token expired")
    return RbacTokenClaims(role=role, tenant_id=tenant_id, iat=iat, exp=exp)


__all__ = [
    "DEFAULT_TOKEN_TTL_SECONDS",
    "RbacTokenClaims",
    "RbacTokenError",
    "issue_token",
    "verify_token",
]
