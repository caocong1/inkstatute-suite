"""Signed CSRF tokens bound to identity and route (PROV-01..04).

Stdlib-only nonce+HMAC-SHA256 token helpers. Tokens bind the nonce, caller
role, tenant, and exact route into a deterministic canonical payload, signed
with HMAC-SHA256 and verified with ``hmac.compare_digest``.

Signing key resolution:
- When ``signing_key`` is provided (production: the RBAC token secret shared
  across processes), tokens are signed with that key, enabling cross-process
  validity in multi-worker deployments.
- When ``signing_key`` is ``None`` (RBAC disabled or tests), a process-local
  key generated at module import is used. This is a fallback for single-process
  deployments and tests only — multi-worker deployments with RBAC disabled will
  have tokens fail across workers.

Security invariants:
- The canonical payload uses sorted compact JSON so there is no delimiter
  ambiguity between nonce, role, tenant, and route.
- Validation fails closed on non-string, missing, malformed, empty, or
  extra-part tokens.
- No tokens, key material, identity headers, or failures are logged.
- No nonce state is persisted, and no cookies/sessions are added. Phase 78 owns
  the complete existing-surface CSRF audit; this module fully protects the new
  Phase 76 POST routes only.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from typing import Any

from rbac import Identity

__all__ = ["issue_csrf_token", "validate_csrf_token"]

# Process-local 32-byte fallback signing key for single-process / test use.
# Production callers pass signing_key=rbac_secret for cross-process validity.
_PROCESS_KEY: bytes = secrets.token_bytes(32)


def _b64url_encode(data: bytes) -> str:
    """URL-safe base64 encoding without padding (form-safe)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes | None:
    """URL-safe base64 decoding; returns ``None`` on any decode failure."""
    try:
        padding = "=" * (-len(text) % 4)
        return base64.urlsafe_b64decode(text + padding)
    except Exception:
        return None


def _resolve_key(signing_key: str | None) -> bytes:
    """Return the signing key bytes — injected key or the private process key."""
    if signing_key is not None:
        return signing_key.encode("utf-8")
    return _PROCESS_KEY


def _canonical_payload(
    nonce: str, identity: Identity, route: str
) -> bytes:
    """Build a deterministic, length-safe canonical payload (sorted compact JSON).

    Binding nonce, ``identity.role.value``, ``identity.tenant_id``, and the
    exact route without delimiter ambiguity.
    """
    payload = {
        "nonce": nonce,
        "role": identity.role.value,
        "tenant": identity.tenant_id,
        "route": route,
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return encoded.encode("utf-8")


def _sign(key: bytes, payload: bytes) -> str:
    """Compute HMAC-SHA256 and return a URL-safe base64 signature."""
    digest = hmac.new(key, payload, hashlib.sha256).digest()
    return _b64url_encode(digest)


def issue_csrf_token(
    identity: Identity,
    route: str,
    *,
    signing_key: str | None = None,
    nonce: str | None = None,
) -> str:
    """Issue a URL/form-safe nonce+HMAC-SHA256 CSRF token.

    Returns ``{nonce}.{signature}`` where the signature binds the nonce,
    ``identity.role.value``, ``identity.tenant_id``, and the exact ``route``.
    A fresh URL-safe random nonce is generated when none is supplied. The
    ``signing_key`` parameter is used in production (passing the shared RBAC
    secret for cross-process validity); when omitted, a process-local fallback
    key is used (single-process / test only).
    """
    raw_nonce = nonce if nonce is not None else secrets.token_urlsafe(16)
    key = _resolve_key(signing_key)
    payload = _canonical_payload(raw_nonce, identity, route)
    signature = _sign(key, payload)
    return f"{raw_nonce}.{signature}"


def validate_csrf_token(
    token: Any,
    identity: Identity,
    route: str,
    *,
    signing_key: str | None = None,
) -> bool:
    """Validate a CSRF token against the identity and exact route.

    Returns ``True`` only when the token is well-formed and the recomputed
    signature matches with ``hmac.compare_digest``. Fails closed on non-string,
    missing, malformed, empty, or extra-part tokens. A token fails for a changed
    nonce/signature, role, tenant, or route.
    """
    if not isinstance(token, str) or not token:
        return False
    parts = token.split(".")
    if len(parts) != 2:
        return False
    nonce, provided_sig = parts
    if not nonce or not provided_sig:
        return False
    key = _resolve_key(signing_key)
    payload = _canonical_payload(nonce, identity, route)
    expected_sig = _sign(key, payload)
    return hmac.compare_digest(provided_sig, expected_sig)
