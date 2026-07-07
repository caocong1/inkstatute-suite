"""QQ Bot gateway envelope parser and event normalizer.

Parses the QQ Bot gateway envelope {op, t, d} into typed event categories
and normalizes C2C/group messages into AgentTurn and INTERACTION_CREATE
into FeedbackEvent. Pure functions — no network IO, no cross-channel imports.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, fields as dc_fields, is_dataclass
from enum import StrEnum
from typing import Any, Mapping

from platform_contract.events import AgentTurn, FeedbackEvent, SkillCandidate

JsonObject = dict[str, Any]


class QQBotEventCategory(StrEnum):
    """Typed event category for QQ Bot gateway envelopes."""

    C2C_MESSAGE = "c2c_message"
    GROUP_AT_MESSAGE = "group_at_message"
    INTERACTION = "interaction"
    VALIDATION_CHALLENGE = "validation_challenge"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class QQBotEvent:
    """Parsed QQ Bot gateway event."""

    category: QQBotEventCategory
    op: int
    event_type: str | None
    data: Mapping[str, Any]
    event_id: str | None
    raw_payload_ref: str | None = None


def parse_envelope(payload: Mapping[str, Any]) -> QQBotEvent:
    """Parse a QQ Bot gateway envelope {op, t, d} into a typed event.

    Defensive: missing op/t/d coerced to defaults; unknown op/t combos
    dispatch to UNKNOWN without crashing; non-Mapping d coerced to {}.
    """
    op = int(payload.get("op", -1))
    t = _optional_string(payload.get("t"))
    d = payload.get("d")
    if not isinstance(d, Mapping):
        d = {}
    event_id = _optional_string(payload.get("id"))

    if op == 13:
        category = QQBotEventCategory.VALIDATION_CHALLENGE
    elif op == 0 and t == "C2C_MESSAGE_CREATE":
        category = QQBotEventCategory.C2C_MESSAGE
    elif op == 0 and t == "GROUP_AT_MESSAGE_CREATE":
        category = QQBotEventCategory.GROUP_AT_MESSAGE
    elif op == 0 and t == "INTERACTION_CREATE":
        category = QQBotEventCategory.INTERACTION
    else:
        category = QQBotEventCategory.UNKNOWN

    return QQBotEvent(
        category=category,
        op=op,
        event_type=t,
        data=d,
        event_id=event_id,
        raw_payload_ref=_optional_string(payload.get("raw_payload_ref")),
    )


# ---------------------------------------------------------------------------
# Local helpers (replicated from adapter.py to keep normalization.py standalone)
# ---------------------------------------------------------------------------


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _required_string(values: Mapping[str, Any], key: str) -> str:
    value = _optional_string(values.get(key))
    if value is None:
        raise ValueError(f"QQBot payload requires {key}")
    return value


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(":".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _dataclass_from_mapping(cls: type[Any], values: Mapping[str, Any]) -> Any:
    if not is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass")
    allowed = {item.name for item in dc_fields(cls)}
    return cls(**{key: value for key, value in values.items() if key in allowed})


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


# ---------------------------------------------------------------------------
# @-bot prefix stripping and feedback action mapping
# ---------------------------------------------------------------------------


def _strip_at_mention(content: str) -> str:
    """Strip @bot mention prefix from group message content."""
    stripped = re.sub(r"^@\S+\s*", "", content.strip())
    return stripped.strip()


_FEEDBACK_ALIASES: dict[str, str] = {
    "thumbs_up": "up",
    "like": "up",
    "thumbs_down": "down",
    "dislike": "down",
    "fix": "needs_fix",
    "route_mismatch": "route_wrong",
}

_VALID_FEEDBACK_ACTIONS = {"up", "down", "needs_fix", "route_wrong"}


def _feedback_action_from_button(button_data: str) -> str:
    """Map a button_data string to a FeedbackAction via alias dict."""
    action = button_data.lower()
    action = _FEEDBACK_ALIASES.get(action, action)
    if action not in _VALID_FEEDBACK_ACTIONS:
        raise ValueError(f"unsupported QQBot feedback action {action!r}")
    return action


def _feedback_event_type(action: str) -> str:
    """Map a feedback action to a FeedbackEventType string."""
    if action == "up":
        return "rating"
    if action == "route_wrong":
        return "route_mismatch"
    return "correction"


# ---------------------------------------------------------------------------
# Event normalization: message events -> AgentTurn
# ---------------------------------------------------------------------------


def normalize_message_event(
    event: QQBotEvent,
    *,
    received_at: str,
    payload_ref: str | None = None,
) -> AgentTurn:
    """Normalize C2C_MESSAGE_CREATE or GROUP_AT_MESSAGE_CREATE into AgentTurn."""
    d = event.data

    if event.category == QQBotEventCategory.C2C_MESSAGE:
        scene = "c2c"
        user_openid = _required_string(d.get("author", {}), "user_openid")
        scene_id = user_openid
        content = _optional_string(d.get("content")) or ""
    elif event.category == QQBotEventCategory.GROUP_AT_MESSAGE:
        scene = "group"
        user_openid = _required_string(d.get("author", {}), "member_openid")
        scene_id = _required_string(d, "group_openid")
        raw_content = _optional_string(d.get("content")) or ""
        content = _strip_at_mention(raw_content)
    else:
        raise ValueError(f"normalize_message_event does not support {event.category}")

    message_id = _optional_string(d.get("id")) or ""
    conversation_id = f"qqbot:{scene}:{scene_id}:{user_openid}"
    turn_id = _stable_id("qqbot-turn", message_id or conversation_id)

    return AgentTurn(
        turn_id=turn_id,
        conversation_id=conversation_id,
        channel="qqbot",
        user_id=user_openid,
        message_type="text",
        received_at=received_at,
        content=content if content else None,
        metadata={
            "source_event": event.event_type or "qqbot_message",
            "source_status": "sanitized_callback",
            "scene": scene,
            "scene_id": scene_id,
            "message_id": message_id,
            "raw_payload_ref": payload_ref or event.raw_payload_ref,
            "content_source_status": "stripped" if event.category == QQBotEventCategory.GROUP_AT_MESSAGE else "direct",
        },
    )


# ---------------------------------------------------------------------------
# Event normalization: interaction events -> FeedbackEvent
# ---------------------------------------------------------------------------


def normalize_interaction_event(
    event: QQBotEvent,
    *,
    created_at: str,
    payload_ref: str | None = None,
) -> FeedbackEvent:
    """Normalize INTERACTION_CREATE into FeedbackEvent with source='card_button'."""
    d = event.data
    chat_type = int(d.get("chat_type", -1))

    if chat_type == 2:  # c2c
        scene = "c2c"
        user_openid = _optional_string(d.get("user_openid")) or ""
        scene_id = user_openid
    elif chat_type == 1:  # group
        scene = "group"
        user_openid = _optional_string(d.get("group_member_openid")) or ""
        scene_id = _optional_string(d.get("group_openid")) or ""
    else:
        # guild (chat_type=0) or unknown — minimal handling
        scene = "guild"
        data_obj = d.get("data", {})
        if not isinstance(data_obj, Mapping):
            data_obj = {}
        resolved = data_obj.get("resolved") or data_obj.get("resoloved") or {}
        if not isinstance(resolved, Mapping):
            resolved = {}
        user_openid = _optional_string(resolved.get("user_id")) or ""
        scene_id = _optional_string(d.get("channel_id")) or ""

    # Extract button_data (handle doc typo "resoloved" vs "resolved")
    data_obj = d.get("data", {})
    if not isinstance(data_obj, Mapping):
        data_obj = {}
    resolved = data_obj.get("resolved") or data_obj.get("resoloved") or {}
    if not isinstance(resolved, Mapping):
        resolved = {}
    button_data = _optional_string(resolved.get("button_data")) or ""
    button_id = _optional_string(resolved.get("button_id"))

    action = _feedback_action_from_button(button_data)
    event_type = _feedback_event_type(action)
    interaction_id = _optional_string(d.get("id")) or event.event_id or ""
    conversation_id = f"qqbot:{scene}:{scene_id}:{user_openid}"
    feedback_id = _stable_id("qqbot-feedback", interaction_id or conversation_id)
    turn_id = _stable_id("qqbot-turn", interaction_id)

    fields_map: JsonObject = {
        "feedback_id": feedback_id,
        "turn_id": turn_id,
        "conversation_id": conversation_id,
        "user_id": user_openid,
        "source": "card_button",
        "event_type": event_type,
        "status": "pending",
        "created_at": created_at,
        "action": action,
        "feedback_target": _optional_string(resolved.get("message_id")) or interaction_id,
        "raw_payload_ref": payload_ref or event.raw_payload_ref,
        "metadata": {
            "source_event": "INTERACTION_CREATE",
            "source_status": "sanitized_callback",
            "scene": scene,
            "interaction_id": interaction_id,
            "button_id": button_id,
            "button_data": button_data,
            "chat_type": chat_type,
            "raw_payload_ref": payload_ref or event.raw_payload_ref,
            "no_auto_modify": action == "route_wrong",
        },
    }

    if action == "up":
        fields_map["rating"] = 1.0
    if action == "route_wrong":
        fields_map["route_mismatch"] = True
        fields_map["skill_candidate"] = SkillCandidate(
            detected=True,
            source="route_mismatch",
            proposed_name="qqbot.route_review_candidate",
            risk_level="high",
            requires_human_review=True,
            evidence=[payload_ref or event.raw_payload_ref or "", interaction_id],
            metadata={"no_auto_modify": True},
        )

    return _dataclass_from_mapping(FeedbackEvent, fields_map)
