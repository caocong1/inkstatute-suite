"""Normalize sanitized WeCom callbacks into platform contract event dictionaries."""

from __future__ import annotations

from typing import Any, Mapping

from platform_contract.utils import (
    coerce_str,
    feedback_event_type as _feedback_event_type,
    mapping_or_empty,
    stable_id,
)

from .idempotency import wecom_idempotency_key
from .protocol import parse_callback_envelope

MESSAGE_TYPES = {"text", "file", "image", "voice", "button_callback"}
FEEDBACK_ACTIONS = {"up", "down", "needs_fix", "route_wrong"}


def normalize_wecom_turn(callback: Mapping[str, Any], *, received_at: str) -> dict[str, Any]:
    """Return an AgentTurn-shaped dictionary for a sanitized WeCom callback."""

    parsed = parse_callback_envelope(callback)
    message_type = _message_type(parsed.get("message_type"))
    idempotency_key = wecom_idempotency_key({**dict(callback), **parsed, "channel": "wecom"})
    raw_payload_ref = coerce_str(parsed.get("raw_payload_ref"))
    message_id = coerce_str(parsed.get("message_id"))
    conversation_id = _required(parsed, "conversation_id")
    user_id = _required(parsed, "user_id")

    event: dict[str, Any] = {
        "turn_id": coerce_str(callback.get("TurnId") or callback.get("turn_id"))
        or stable_id("turn", message_id or idempotency_key, conversation_id, user_id),
        "conversation_id": conversation_id,
        "channel": "wecom",
        "user_id": user_id,
        "message_type": message_type,
        "received_at": received_at,
        "industry_context": mapping_or_empty(callback.get("industry_context")),
        "metadata": {
            "idempotency_key": idempotency_key,
            "raw_payload_ref": raw_payload_ref,
            "source_event": "wecom_callback",
            "source_status": "sanitized_callback",
            "message_id": message_id,
            "content_source_status": "source_confirmed" if parsed.get("content") else "unavailable",
            "attachments_source_status": "source_confirmed_ref_only"
            if message_type in {"file", "image", "voice"}
            else "not_applicable",
        },
    }
    if message_type == "text" and parsed.get("content") is not None:
        event["content"] = parsed["content"]

    attachments = _attachments(callback, parsed, message_type)
    if attachments:
        event["attachments"] = attachments

    output_constraints = mapping_or_empty(callback.get("output_constraints"))
    if output_constraints:
        event["output_constraints"] = output_constraints

    return event


def normalize_wecom_feedback_callback(callback: Mapping[str, Any], *, created_at: str) -> dict[str, Any]:
    """Return a FeedbackEvent-shaped dictionary for a sanitized WeCom button callback."""

    parsed = parse_callback_envelope(callback)
    idempotency_key = wecom_idempotency_key({**dict(callback), **parsed, "event_type": "feedback"})
    action = _feedback_action(callback, parsed)
    feedback_target = coerce_str(
        callback.get("feedback_target")
        or callback.get("FeedbackTarget")
        or parsed.get("message_id")
        or parsed.get("event_key")
    )
    if feedback_target is None:
        raise ValueError("feedback callback requires feedback_target, message_id, or event_key")

    conversation_id = _required(parsed, "conversation_id")
    user_id = _required(parsed, "user_id")
    turn_id = coerce_str(callback.get("TurnId") or callback.get("turn_id")) or stable_id(
        "turn", conversation_id, user_id, feedback_target
    )
    raw_payload_ref = coerce_str(parsed.get("raw_payload_ref"))

    event: dict[str, Any] = {
        "feedback_id": coerce_str(callback.get("feedback_id") or callback.get("FeedbackId"))
        or stable_id("feedback", idempotency_key),
        "turn_id": turn_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "source": "card_button",
        "event_type": _feedback_event_type(action),
        "status": "pending",
        "created_at": created_at,
        "feedback_target": feedback_target,
        "action": action,
        "raw_payload_ref": raw_payload_ref,
        "industry_context": mapping_or_empty(callback.get("industry_context")),
        "metadata": {
            "idempotency_key": idempotency_key,
            "source_event": "wecom_button_callback",
            "source_status": "sanitized_callback",
            "event_key": parsed.get("event_key"),
            "no_auto_modify": action == "route_wrong",
        },
    }

    result_id = coerce_str(callback.get("result_id") or callback.get("ResultId"))
    if result_id is not None:
        event["result_id"] = result_id
    message = coerce_str(callback.get("message") or callback.get("comment"))
    if message is not None:
        event["message"] = message
    if action == "up":
        event["rating"] = 1.0
    if action == "route_wrong":
        event["route_mismatch"] = True
        event["skill_candidate"] = {
            "detected": True,
            "source": "route_mismatch",
            "proposed_name": coerce_str(callback.get("proposed_skill")) or "lawfirm.route_review_candidate",
            "risk_level": "high",
            "requires_human_review": True,
            "evidence": [item for item in (raw_payload_ref, feedback_target) if item is not None],
            "metadata": {
                "no_auto_modify": True,
                "source_status": "wecom_callback_sanitized",
            },
        }

    return event


def _attachments(
    callback: Mapping[str, Any],
    parsed: Mapping[str, Any],
    message_type: str,
) -> list[dict[str, Any]]:
    if message_type not in {"file", "image", "voice"}:
        return []
    media_ref = coerce_str(parsed.get("media_ref") or callback.get("MediaId"))
    if media_ref is None:
        return []
    attachment: dict[str, Any] = {
        "attachment_id": media_ref,
        "kind": message_type,
        "uri": f"wecom-media://{media_ref}",
        "metadata": {
            "raw_payload_ref": parsed.get("raw_payload_ref"),
            "source_status": "media_reference_only",
            "bytes_stored": False,
        },
    }
    name = coerce_str(callback.get("FileName") or callback.get("filename") or callback.get("name"))
    if name is not None:
        attachment["name"] = name
    mime_type = coerce_str(callback.get("mime_type") or callback.get("MimeType"))
    if mime_type is not None:
        attachment["mime_type"] = mime_type
    return [attachment]


def _message_type(value: Any) -> str:
    text = (coerce_str(value) or "text").lower()
    if text not in MESSAGE_TYPES:
        raise ValueError(f"unsupported WeCom message_type {value!r}")
    return text


def _feedback_action(callback: Mapping[str, Any], parsed: Mapping[str, Any]) -> str:
    raw = coerce_str(
        callback.get("action")
        or callback.get("feedback_action")
        or callback.get("button_action")
        or parsed.get("event_key")
    )
    action = (raw or "needs_fix").split(":")[-1].lower()
    aliases = {
        "thumbs_up": "up",
        "like": "up",
        "thumbs_down": "down",
        "dislike": "down",
        "fix": "needs_fix",
        "route_mismatch": "route_wrong",
    }
    action = aliases.get(action, action)
    if action not in FEEDBACK_ACTIONS:
        raise ValueError(f"unsupported WeCom feedback action {raw!r}")
    return action


def _required(values: Mapping[str, Any], key: str) -> str:
    value = coerce_str(values.get(key))
    if value is None:
        raise ValueError(f"missing required WeCom callback field {key}")
    return value


__all__ = [
    "normalize_wecom_feedback_callback",
    "normalize_wecom_turn",
]
