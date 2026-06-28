"""Idempotency helpers for sanitized WeCom callbacks."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping


def wecom_idempotency_key(callback: Mapping[str, Any]) -> str:
    """Return a stable idempotency key for a sanitized callback."""

    stable_fields = (
        ("message", callback.get("message_id") or callback.get("msg_id") or callback.get("MsgId")),
        ("callback", callback.get("callback_id") or callback.get("event_key") or callback.get("EventKey")),
        ("feedback", callback.get("feedback_id")),
    )
    for field_name, value in stable_fields:
        text = _string(value)
        if text is not None:
            return f"wecom:{field_name}:{_digest(text)}"

    fallback_parts = (
        _string(callback.get("channel")) or "wecom",
        _string(callback.get("user_id") or callback.get("FromUserName")) or "unknown-user",
        _string(callback.get("conversation_id") or callback.get("chat_id") or callback.get("ChatId"))
        or "unknown-conversation",
        _string(callback.get("created_at") or callback.get("CreateTime")) or "unknown-time",
        _string(callback.get("event_type") or callback.get("MsgType") or callback.get("Event")) or "unknown-event",
    )
    return f"wecom:fallback:{_digest(':'.join(fallback_parts))}"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


__all__ = ["wecom_idempotency_key"]
