"""Feedback handler for Lawyer Web Chat.

Normalizes feedback submissions using the same pattern as
``WebSseChannelAdapter.normalize_inbound`` — producing ``FeedbackEvent``
records with proper action classification, skill candidate detection for
route mismatches, and reference-only metadata.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

from platform_contract.events import FeedbackEvent, SkillCandidate


@dataclass
class FeedbackResult:
    """Result of feedback normalization."""

    feedback_id: str
    feedback_event: FeedbackEvent
    action: str
    event_type: str


class FeedbackHandler:
    """Handle feedback submissions from the lawyer web chat.

    Reuses the same normalization pattern as ``WebSseChannelAdapter``:
    - "up" / "thumbs_up" / "like" → rating event
    - "down" / "thumbs_down" / "dislike" → correction event
    - "needs_fix" / "fix" → correction event
    - "route_wrong" / "route_mismatch" → route_mismatch event with skill candidate
    """

    def __init__(self) -> None:
        self._counter = 0

    def submit_feedback(
        self,
        *,
        conversation_id: str,
        user_id: str,
        action: str,
        feedback_target: str,
        message: str | None = None,
        turn_id: str | None = None,
        tenant_id: str | None = None,
        now: int | None = None,
        tenant_filter: Any = None,
    ) -> FeedbackResult:
        """Normalize and submit feedback.

        Returns a ``FeedbackResult`` with the normalized ``FeedbackEvent``.

        ``tenant_filter`` is accepted for API consistency with other handlers.
        The write path already uses ``tenant_id`` for tagging; the filter is
        a no-op for submit operations (it applies to future list/read methods).
        """
        ts = int(now if now is not None else time.time())
        self._counter += 1
        feedback_id = f"feedback-{self._counter}"
        turn_ref = turn_id or f"turn-{conversation_id}-{ts}"
        payload_ref = f"ref://feedback/{conversation_id}/{feedback_id}"

        normalized_action = _normalize_action(action)
        event_type = _action_to_event_type(normalized_action)

        fields_map: dict[str, Any] = {
            "feedback_id": feedback_id,
            "turn_id": turn_ref,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "source": "web_chat",
            "event_type": event_type,
            "status": "pending",
            "created_at": _iso_timestamp(ts),
            "feedback_target": feedback_target,
            "action": normalized_action,
            "message": message,
            "industry_context": {},
            "metadata": {
                "payload_ref": payload_ref,
                "tenant_id": tenant_id,
                "source": "web_chat",
                "reference_only": True,
            },
        }

        if normalized_action == "up":
            fields_map["rating"] = 1.0

        if normalized_action == "route_wrong":
            fields_map["route_mismatch"] = True
            fields_map["skill_candidate"] = SkillCandidate(
                detected=True,
                source="route_mismatch",
                proposed_name="web_chat.route_review_candidate",
                risk_level="high",
                requires_human_review=True,
                evidence=[payload_ref, feedback_target],
                metadata={"no_auto_modify": True},
            )

        feedback_event = _build_feedback_event(fields_map)

        return FeedbackResult(
            feedback_id=feedback_id,
            feedback_event=feedback_event,
            action=normalized_action,
            event_type=event_type,
        )


def _normalize_action(action: str) -> str:
    """Normalize feedback action to canonical form."""
    normalized = action.strip().lower().split(":")[-1]
    aliases = {
        "thumbs_up": "up",
        "like": "up",
        "thumbs_down": "down",
        "dislike": "down",
        "fix": "needs_fix",
        "route_mismatch": "route_wrong",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"up", "down", "needs_fix", "route_wrong"}:
        raise ValueError(f"unsupported feedback action: {action!r}")
    return normalized


def _action_to_event_type(action: str) -> str:
    """Map action to event type."""
    if action == "up":
        return "rating"
    if action == "route_wrong":
        return "route_mismatch"
    return "correction"


def _iso_timestamp(ts: int) -> str:
    """Convert Unix timestamp to ISO-8601 string."""
    from datetime import UTC, datetime
    return datetime.fromtimestamp(ts, tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_feedback_event(fields_map: dict[str, Any]) -> FeedbackEvent:
    """Build a FeedbackEvent from a field mapping, filtering to allowed fields."""
    from dataclasses import fields as dataclass_fields
    allowed = {f.name for f in dataclass_fields(FeedbackEvent)}
    return FeedbackEvent(**{k: v for k, v in fields_map.items() if k in allowed})


__all__ = ["FeedbackHandler", "FeedbackResult"]
