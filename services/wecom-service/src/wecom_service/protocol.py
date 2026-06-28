"""Protocol helpers for sanitized WeCom callback handling."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, Mapping
import xml.etree.ElementTree as ET


class RawPayloadForbiddenError(ValueError):
    """Raised when a callback contains raw payload material."""


def verify_callback_signature(
    token: str,
    timestamp: str,
    nonce: str,
    msg_signature: str,
    encrypted_payload: str,
) -> bool:
    """Verify a WeCom-style callback signature."""

    digest = hashlib.sha1(
        "".join(sorted([token, timestamp, nonce, encrypted_payload])).encode("utf-8")
    ).hexdigest()
    return hmac.compare_digest(digest, msg_signature)


def parse_callback_envelope(callback: Mapping[str, Any]) -> dict[str, Any]:
    """Parse a sanitized callback envelope into normalized scalar fields."""

    fields = _mapping_from_input(callback)
    raw_payload_path = _find_exact_key(fields, "raw_payload")
    if raw_payload_path is not None:
        raise RawPayloadForbiddenError(
            f"WeCom callbacks must use raw_payload_ref, not raw_payload ({raw_payload_path})"
        )

    parsed = {
        "message_id": _first_string(fields, "message_id", "msg_id", "MsgId"),
        "callback_id": _first_string(fields, "callback_id", "CallbackId"),
        "event_key": _first_string(fields, "event_key", "EventKey"),
        "user_id": _first_string(fields, "user_id", "from_user", "FromUserName", "UserID"),
        "conversation_id": _first_string(
            fields,
            "conversation_id",
            "chat_id",
            "ChatId",
            "ConversationId",
            "ToUserName",
        ),
        "message_type": _normalize_message_type(_first_string(fields, "message_type", "msg_type", "MsgType")),
        "event_type": _first_string(fields, "event_type", "Event", "MsgType"),
        "created_at": _first_string(fields, "created_at", "CreateTime"),
        "content": _first_string(fields, "content", "Content"),
        "media_ref": _first_string(fields, "media_ref", "MediaId", "PicUrl", "VoiceId"),
        "raw_payload_ref": _first_string(fields, "raw_payload_ref", "RawPayloadRef"),
    }
    return {key: value for key, value in parsed.items() if value is not None}


def ack_response() -> str:
    """Return the immediate WeCom ACK body."""

    return "success"


def _mapping_from_input(callback: Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(callback, Mapping):
        return callback
    if isinstance(callback, str):
        root = ET.fromstring(callback)
        return {child.tag: child.text for child in list(root)}
    raise TypeError("callback must be a mapping or sanitized XML string")


def _first_string(fields: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = fields.get(key)
        if value is None:
            continue
        if _is_scalar(value):
            text = str(value).strip()
            if text:
                return text
    return None


def _normalize_message_type(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.lower()
    aliases = {
        "event": "button_callback",
        "button": "button_callback",
        "callback": "button_callback",
    }
    return aliases.get(normalized, normalized)


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))


def _find_exact_key(value: Any, needle: str, path: str = "") -> str | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key == needle:
                return child_path
            found = _find_exact_key(child, needle, child_path)
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_exact_key(child, needle, f"{path}[{index}]")
            if found is not None:
                return found
    return None


__all__ = [
    "RawPayloadForbiddenError",
    "ack_response",
    "parse_callback_envelope",
    "verify_callback_signature",
]
