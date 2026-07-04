"""Static token authentication for the Admin Console API.

Reads a static token from the ``ADMIN_API_TOKEN`` environment variable and
validates ``Authorization: Bearer <token>`` headers using
``hmac.compare_digest`` for constant-time comparison.  When the token is not
set or empty, all auth checks fail.
"""

from __future__ import annotations

import hmac
import os
from typing import Mapping

ADMIN_API_TOKEN_ENV = "ADMIN_API_TOKEN"

_BEARER_PREFIX = "Bearer "


def resolve_admin_token(env: Mapping[str, str] | None = None) -> str | None:
    """Return the configured admin token, or ``None`` when absent/empty."""

    source: Mapping[str, str] = env if env is not None else os.environ
    token = source.get(ADMIN_API_TOKEN_ENV, "")
    return token if token else None


def check_auth_header(header_value: str | None, expected_token: str | None) -> bool:
    """Validate a ``Bearer`` auth header against the expected token.

    Returns ``False`` when the token is not configured, the header is missing,
    or the header does not start with ``"Bearer "``.  Uses
    ``hmac.compare_digest`` for constant-time comparison.
    """

    if expected_token is None:
        return False
    if header_value is None or not header_value.startswith(_BEARER_PREFIX):
        return False
    provided = header_value[len(_BEARER_PREFIX):]
    return hmac.compare_digest(provided, expected_token)


def extract_auth_header(headers: Mapping[str, str] | None) -> str | None:
    """Case-insensitive lookup of the ``Authorization`` header."""

    if headers is None:
        return None
    for key, value in headers.items():
        if key.lower() == "authorization":
            return value
    return None


__all__ = [
    "ADMIN_API_TOKEN_ENV",
    "resolve_admin_token",
    "check_auth_header",
    "extract_auth_header",
]
