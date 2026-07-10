"""Process-edge secret reference resolution for the QQBot host.

Values appear only when callers inject an env mapping. This module never reads
``os.environ`` and never logs resolved values.
"""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import Mapping

__all__ = [
    "InvalidSecretRefError",
    "REF_TO_VALUE_ENV",
    "normalize_config_secret_ref",
    "resolve_secret_ref",
]

# secret:// paths → value env var names (aligned with smoke live naming).
# Frozen so importers cannot redirect resolution at runtime.
REF_TO_VALUE_ENV: Mapping[str, str] = MappingProxyType(
    {
        "secret://qqbot/app-id": "INKSTATUTE_QQBOT_APP_ID",
        "secret://qqbot/app-secret": "INKSTATUTE_QQBOT_CLIENT_SECRET",
        "secret://qqbot/token": "INKSTATUTE_QQBOT_TOKEN",
        "secret://qqbot/bot-secret": "INKSTATUTE_QQBOT_BOT_SECRET",
    }
)

# Bare env-key identifiers and env:NAME suffixes (no secret material in errors).
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class InvalidSecretRefError(ValueError):
    """Config *_REF value is not an allowed reference shape (message has no secret)."""


def normalize_config_secret_ref(raw: str | None, *, field: str) -> str | None:
    """Strip and validate a host config secret reference.

    Accepts ``None``/blank, ``env:NAME``, known ``secret://qqbot/…`` paths, or a
    bare env-key identifier. Rejects other strings fail-closed without echoing
    the rejected value (so raw secrets planted in ``*_REF`` never appear in
    errors or on the config object).
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
        if ref not in REF_TO_VALUE_ENV:
            raise InvalidSecretRefError(f"invalid secret reference shape for {field}")
        return ref

    if _ENV_NAME_RE.fullmatch(ref):
        return ref

    raise InvalidSecretRefError(f"invalid secret reference shape for {field}")


def resolve_secret_ref(ref: str | None, env: Mapping[str, str]) -> str | None:
    """Return the secret value for ``ref`` from the injected ``env`` mapping.

    Resolution order:
    1. Empty/None → None (fail closed).
    2. ``env:NAME`` → ``env[NAME]``.
    3. ``secret://…`` → mapped value env key, then lookup.
    4. If ``ref`` is itself a key in ``env``, return that value.
    5. Otherwise → None (fail closed). Never raises with secret material.
    """
    if not ref:
        return None

    if ref.startswith("env:"):
        key = ref[4:]
        if not key:
            return None
        value = env.get(key, "")
        return value or None

    if ref.startswith("secret://"):
        key = REF_TO_VALUE_ENV.get(ref)
        if key is None:
            return None
        value = env.get(key, "")
        return value or None

    if ref in env:
        value = env.get(ref, "")
        return value or None

    return None
