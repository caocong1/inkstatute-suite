"""Shape-only secret reference normalization for operator config documents.

Validates reference *shapes* only. Does not resolve values, does not read the
process environment, and does not import qqbot-service.
"""

from __future__ import annotations

import re

__all__ = [
    "InvalidSecretRefError",
    "normalize_config_secret_ref",
]

# Bare env-key identifiers and env:NAME suffixes (no secret material in errors).
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# secret:// + one or more slash-separated segments of safe path characters.
# Generalized beyond QQ-only REF_TO_VALUE_ENV maps (hosts resolve at process edge).
_SECRET_URI_RE = re.compile(
    r"^secret://[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)+$"
)


class InvalidSecretRefError(ValueError):
    """Config *_ref value is not an allowed reference shape (message has no secret)."""


def normalize_config_secret_ref(raw: str | None, *, field: str) -> str | None:
    """Strip and validate an operator-config secret reference.

    Accepts ``None``/blank, ``env:NAME``, bare env-key identifiers matching
    ``^[A-Za-z_][A-Za-z0-9_]*$``, or ``secret://`` paths with non-empty
    slash-separated safe segments. Rejects other strings fail-closed without
    echoing the rejected value (so raw secrets planted in ``*_ref`` never
    appear in errors).
    """
    if raw is None:
        return None
    ref = raw.strip()
    if not ref:
        return None

    if ref.startswith("env:"):
        name = ref[4:]
        if not name or not _ENV_NAME_RE.fullmatch(name):
            raise InvalidSecretRefError(f"invalid secret reference shape for {field}")
        return f"env:{name}"

    if ref.startswith("secret://"):
        if not _SECRET_URI_RE.fullmatch(ref):
            raise InvalidSecretRefError(f"invalid secret reference shape for {field}")
        return ref

    if _ENV_NAME_RE.fullmatch(ref):
        return ref

    raise InvalidSecretRefError(f"invalid secret reference shape for {field}")
