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
