"""Auth middleware for the local-only InkStatute Arena Service.

Enforces two layers on every request:

1. **Localhost-only binding** — :meth:`ArenaServiceAuth.require_localhost`
   rejects non-localhost connections with ``403 forbidden_remote`` BEFORE
   any auth check. The service binds to ``127.0.0.1`` and never accepts
   remote connections.
2. **Token auth** — :meth:`ArenaServiceAuth.require_auth` extracts the
   ``Authorization: Bearer <token>`` header (case-insensitive) and
   compares it with the configured token using
   :func:`secrets.compare_digest` (constant-time). Missing or mismatched
   tokens raise :class:`ArenaServiceAuthError` with ``401 unauthorized``.

No endpoint bypasses auth. The ``dispatch`` method calls
``require_localhost`` then ``require_auth`` BEFORE routing to any handler.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Mapping

from .config import ArenaServiceConfig


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Resolved auth context for an Arena Service request."""

    authenticated: bool
    token_valid: bool
    error: str | None


class ArenaServiceAuthError(Exception):
    """Raised when auth or localhost checks fail.

    Attributes:
        status: HTTP status code (401 for auth, 403 for localhost).
        code: Machine-readable error code.
        message: Human-readable error message.
    """

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class ArenaServiceAuth:
    """Auth middleware that wraps all Arena Service endpoint handlers.

    Enforces localhost-only binding and single-token auth. No endpoint
    bypasses these checks.
    """

    def __init__(self, config: ArenaServiceConfig) -> None:
        self._config = config

    def require_auth(self, headers: Mapping[str, str]) -> AuthContext:
        """Validate the Bearer token. Raises on missing/mismatched token.

        Uses :func:`secrets.compare_digest` for constant-time comparison
        to prevent timing attacks.
        """
        auth_header = _get_header(headers, "Authorization")
        if auth_header is None:
            raise ArenaServiceAuthError(
                status=401,
                code="unauthorized",
                message="Missing Authorization header",
            )
        token = _extract_bearer_token(auth_header)
        if token is None:
            raise ArenaServiceAuthError(
                status=401,
                code="unauthorized",
                message="Invalid Authorization header format",
            )
        if not self._config.token:
            raise ArenaServiceAuthError(
                status=401,
                code="unauthorized",
                message="No token configured on the server",
            )
        if not secrets.compare_digest(token, self._config.token):
            raise ArenaServiceAuthError(
                status=401,
                code="unauthorized",
                message="Invalid or mismatched token",
            )
        return AuthContext(
            authenticated=True,
            token_valid=True,
            error=None,
        )

    def check_localhost(self, client_address: str) -> bool:
        """Return ``True`` if the address is a localhost address.

        Accepts ``127.*`` (IPv4 loopback) and ``::1`` (IPv6 loopback).
        """
        return client_address.startswith("127.") or client_address == "::1"

    def require_localhost(self, client_address: str) -> None:
        """Raise ``ArenaServiceAuthError(403, forbidden_remote)`` if non-localhost."""
        if not self.check_localhost(client_address):
            raise ArenaServiceAuthError(
                status=403,
                code="forbidden_remote",
                message=f"Non-localhost connections are not allowed: {client_address}",
            )


def _get_header(headers: Mapping[str, str], name: str) -> str | None:
    """Case-insensitive header lookup."""
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def _extract_bearer_token(auth_header: str) -> str | None:
    """Extract the token from an ``Authorization: Bearer <token>`` header."""
    parts = auth_header.split(None, 1)
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    if not token:
        return None
    return token


__all__ = [
    "ArenaServiceAuth",
    "ArenaServiceAuthError",
    "AuthContext",
]
