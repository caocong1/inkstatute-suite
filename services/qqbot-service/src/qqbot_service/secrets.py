"""Process-edge secret reference resolution for the QQBot host.

Values appear only when callers inject an env mapping. This module never reads
``os.environ`` and never logs resolved values.
"""

from __future__ import annotations

from typing import Mapping

__all__ = ["REF_TO_VALUE_ENV", "resolve_secret_ref"]

# secret:// paths → value env var names (aligned with smoke live naming).
REF_TO_VALUE_ENV: dict[str, str] = {
    "secret://qqbot/app-id": "INKSTATUTE_QQBOT_APP_ID",
    "secret://qqbot/app-secret": "INKSTATUTE_QQBOT_CLIENT_SECRET",
    "secret://qqbot/token": "INKSTATUTE_QQBOT_TOKEN",
    "secret://qqbot/bot-secret": "INKSTATUTE_QQBOT_BOT_SECRET",
}


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
