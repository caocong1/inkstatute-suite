"""Idempotency helpers for sanitized WeCom callbacks."""

from __future__ import annotations

from typing import Any, Mapping

from platform_contract.utils import coerce_str, sha256_short


def wecom_idempotency_key(callback: Mapping[str, Any]) -> str:
    """Return a stable idempotency key for a sanitized callback."""

    stable_fields = (
        ("message", callback.get("message_id") or callback.get("msg_id") or callback.get("MsgId")),
        ("callback", callback.get("callback_id") or callback.get("event_key") or callback.get("EventKey")),
        ("feedback", callback.get("feedback_id")),
    )
    for field_name, value in stable_fields:
        text = coerce_str(value)
        if text is not None:
            return f"wecom:{field_name}:{sha256_short(text, length=24)}"

    fallback_parts = (
        coerce_str(callback.get("channel")) or "wecom",
        coerce_str(callback.get("user_id") or callback.get("FromUserName")) or "unknown-user",
        coerce_str(callback.get("conversation_id") or callback.get("chat_id") or callback.get("ChatId"))
        or "unknown-conversation",
        coerce_str(callback.get("created_at") or callback.get("CreateTime")) or "unknown-time",
        coerce_str(callback.get("event_type") or callback.get("MsgType") or callback.get("Event")) or "unknown-event",
    )
    return f"wecom:fallback:{sha256_short(':'.join(fallback_parts), length=24)}"


__all__ = ["wecom_idempotency_key"]
