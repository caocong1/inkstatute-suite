"""Channel-generic idempotency key helpers."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence


def channel_idempotency_key(
    callback: Mapping[str, Any],
    *,
    channel_prefix: str = "channel",
    stable_fields: Sequence[tuple[str, Sequence[str]]] | None = None,
    fallback_field_aliases: Mapping[str, Sequence[str]] | None = None,
) -> str:
    """Return a stable idempotency key for a sanitized channel callback.

    Tries stable fields (message_id, callback_id, feedback_id) first, then
    falls back to a composite digest of channel/user/conversation/time/event.
    """

    if stable_fields is None:
        stable_fields = (
            ("message", ("message_id", "msg_id", "MsgId")),
            ("callback", ("callback_id", "event_key", "EventKey")),
            ("feedback", ("feedback_id",)),
        )

    for field_name, aliases in stable_fields:
        for alias in aliases:
            text = string_or_none(callback.get(alias))
            if text is not None:
                return f"{channel_prefix}:{field_name}:{digest_short(text)}"

    if fallback_field_aliases is None:
        fallback_field_aliases = {
            "channel": ("channel",),
            "user": ("user_id", "FromUserName"),
            "conversation": ("conversation_id", "chat_id", "ChatId"),
            "created_at": ("created_at", "CreateTime"),
            "event_type": ("event_type", "MsgType", "Event"),
        }

    fallback_parts: list[str] = []
    for _label, aliases in fallback_field_aliases.items():
        part: str | None = None
        for alias in aliases:
            part = string_or_none(callback.get(alias))
            if part is not None:
                break
        fallback_parts.append(part or "unknown")

    return f"{channel_prefix}:fallback:{digest_short(':'.join(fallback_parts))}"


def digest_short(value: str) -> str:
    """SHA-256 hexdigest truncated to 24 chars."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def string_or_none(value: Any) -> str | None:
    """Return a stripped non-empty string or None."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


__all__ = ["channel_idempotency_key", "digest_short", "string_or_none"]
