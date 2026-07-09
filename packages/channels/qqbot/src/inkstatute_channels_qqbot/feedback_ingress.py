"""Pure QQ Bot INTERACTION → FeedbackEvent ingress helper.

Hosts compose FeedbackEvent dicts into the feedback queue package via
PYTHONPATH. This module stays free of WeCom service imports and network IO.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from .normalization import (
    QQBotEventCategory,
    normalize_interaction_event,
    parse_envelope,
)

__all__ = ["handle_feedback_callback"]


def handle_feedback_callback(
    callback: Mapping[str, Any],
    *,
    received_at: str,
    payload_ref: str | None = None,
) -> dict[str, Any]:
    """Normalize an INTERACTION_CREATE callback into FeedbackEvent evidence.

    Returns:
        ``{"status": "skipped", "category": ...}`` for non-interaction envelopes.
        ``{"status": "normalized", "feedback_event", "feedback_dict", "idempotency_key"}``
        for INTERACTION_CREATE.
    """
    event = parse_envelope(callback)
    if event.category != QQBotEventCategory.INTERACTION:
        return {"status": "skipped", "category": event.category.value}

    feedback = normalize_interaction_event(
        event,
        created_at=received_at,
        payload_ref=payload_ref,
    )
    feedback_dict = asdict(feedback)
    return {
        "status": "normalized",
        "feedback_event": feedback,
        "feedback_dict": feedback_dict,
        "idempotency_key": feedback.metadata.get("idempotency_key"),
    }
