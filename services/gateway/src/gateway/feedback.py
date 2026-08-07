"""Feedback normalization handler for the InkStatute Gateway.

Ports the ``FeedbackHandler`` from ``services/lawyer-web-chat`` into the
Gateway, adapting it to the Gateway's auth + tenant pattern.

CRITICAL: ``SkillCandidate.requires_human_review`` must always be ``True``
for route_wrong feedback. The handler must NEVER auto-synthesize or
auto-modify legal conclusion skills. ``metadata.no_auto_modify`` must be
``True``. This satisfies AGENTS.md: "High-risk legal conclusions stay
human-reviewed. Record skill_candidate with requires_human_review=true;
never auto-synthesize or auto-modify legal conclusion skills."
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Mapping

from platform_contract.events import FeedbackEvent, SkillCandidate

from .auth import AuthContext

JsonObject = dict[str, Any]


@dataclass
class FeedbackResult:
    """Result of feedback normalization.

    ``tenant_id`` is an explicit first-class field in the Gateway.
    """

    feedback_id: str
    feedback_event: FeedbackEvent
    action: str
    event_type: str
    tenant_id: str


class GatewayFeedbackHandler:
    """Handle feedback submissions from Gateway clients.

    Reuses the same normalization pattern as ``lawyer-web-chat``:
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
    ) -> FeedbackResult:
        """Normalize and submit feedback.

        Returns a ``FeedbackResult`` with the normalized ``FeedbackEvent``.
        Raises ``ValueError`` for unsupported actions.
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
            "source": "gateway",
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
                "source": "gateway",
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
                proposed_name="gateway.route_review_candidate",
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
            tenant_id=tenant_id or "default",
        )


def handle_submit_feedback_request(
    handler: GatewayFeedbackHandler,
    auth_ctx: AuthContext,
    body: Mapping[str, object],
) -> JsonObject:
    """Gateway endpoint handler for ``POST /v1/feedback``.

    Parses the request body (conversation_id, user_id, action,
    feedback_target, message, turn_id), calls ``handler.submit_feedback()``
    with the auth context's ``tenant_id``, and returns the feedback result
    as a JSON dict. Returns 400 for invalid actions.
    """
    conversation_id = str(body.get("conversation_id") or "")
    user_id = str(body.get("user_id") or "")
    action = str(body.get("action") or "")
    feedback_target = str(body.get("feedback_target") or "")
    message = body.get("message")
    if message is not None:
        message = str(message)
    turn_id = body.get("turn_id")
    if turn_id is not None:
        turn_id = str(turn_id)

    if not conversation_id:
        return _error_response("invalid_request", "conversation_id is required", status=400)
    if not action:
        return _error_response("invalid_request", "action is required", status=400)
    if not feedback_target:
        return _error_response("invalid_request", "feedback_target is required", status=400)

    try:
        result = handler.submit_feedback(
            conversation_id=conversation_id,
            user_id=user_id,
            action=action,
            feedback_target=feedback_target,
            message=message,
            turn_id=turn_id,
            tenant_id=auth_ctx.tenant_id,
        )
    except ValueError:
        return _error_response(
            "invalid_action",
            f"Unsupported feedback action: {action!r}",
            status=400,
        )

    return {
        "feedback_id": result.feedback_id,
        "action": result.action,
        "event_type": result.event_type,
        "tenant_id": result.tenant_id,
        "status": "pending",
        "reference_only": True,
    }


# ---------------------------------------------------------------------------
# Internal helpers (ported from lawyer-web-chat/feedback.py)
# ---------------------------------------------------------------------------


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


def _error_response(code: str, message: str, *, status: int = 400) -> JsonObject:
    return {
        "error": {
            "code": code,
            "message": message,
        },
        "status": status,
    }


__all__ = [
    "FeedbackResult",
    "GatewayFeedbackHandler",
    "handle_submit_feedback_request",
]
