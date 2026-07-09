"""Pure QQ Bot INTERACTION → FeedbackEvent ingress helper.

Hosts compose FeedbackEvent dicts into the feedback queue package via
PYTHONPATH. This module stays free of WeCom service imports and network IO
except for the optional post-normalize ``ensure_interaction_ack`` path, which
reuses ``sender.ack_interaction`` only when prior ACK status is ``pending_host``.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any, Mapping

from .normalization import (
    QQBotEventCategory,
    normalize_interaction_event,
    parse_envelope,
)
from .sender import SendError, ack_interaction

__all__ = ["handle_feedback_callback", "ensure_interaction_ack"]


class _StaticTokenManager:
    """Minimal token_manager duck-type for hosts that pass a raw access_token."""

    def __init__(self, token: str) -> None:
        self._token = token

    async def get_token(self) -> str:
        return self._token


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


def ensure_interaction_ack(
    interaction_id: str | None = None,
    *,
    prior_ack_metadata: Mapping[str, Any] | None = None,
    ack_metadata: Mapping[str, Any] | None = None,
    message_transport: Any = None,
    transport: Any = None,
    access_token: str | None = None,
    token_manager: Any = None,
    code: int = 0,
) -> dict[str, Any]:
    """Complete interaction ACK after normalize (FEEDBACK-02 no-op-if-sent).

    Default: if Phase 65 already set ``interaction_ack_status=="sent"``, return
    noop without PUT. Only call ``ack_interaction`` when status is
    ``pending_host`` and a live transport + token are available.

    Never ACK unverified callbacks — callers must invoke only after signature
    verification / successful normalize. Does not re-implement verify_and_ack.
    """
    meta = dict(prior_ack_metadata or ack_metadata or {})
    status = str(meta.get("interaction_ack_status") or "")
    required = meta.get("interaction_ack_required")
    resolved_id = interaction_id or meta.get("interaction_id")
    xport = message_transport if message_transport is not None else transport

    evidence: dict[str, Any] = {
        "interaction_id": resolved_id,
        "interaction_ack_status": status or None,
        "prior_ack_status": status or None,
    }

    # Explicitly not required (non-interaction / invalid signature path) → never PUT.
    if required is False:
        evidence["status"] = "skipped"
        return evidence

    if status == "sent":
        evidence["status"] = "noop"
        evidence["interaction_ack_status"] = "sent"
        return evidence

    if status == "skipped_fixture":
        evidence["status"] = "skipped"
        evidence["interaction_ack_status"] = "skipped_fixture"
        return evidence

    # Only pending_host may trigger a deferred PUT; failed/unknown → no PUT.
    if status != "pending_host":
        evidence["status"] = "noop" if not status else "skipped"
        return evidence

    if not resolved_id or xport is None:
        evidence["status"] = "skipped"
        evidence["interaction_ack_status"] = "pending_host"
        evidence["interaction_ack_issue_code"] = "qqbot_interaction_ack_missing_transport"
        return evidence

    mgr = token_manager
    if mgr is None:
        if not access_token:
            evidence["status"] = "skipped"
            evidence["interaction_ack_status"] = "pending_host"
            evidence["interaction_ack_issue_code"] = "qqbot_interaction_ack_missing_token"
            return evidence
        mgr = _StaticTokenManager(access_token)

    try:
        _run_ack(
            interaction_id=str(resolved_id),
            token_manager=mgr,
            transport=xport,
            code=code,
        )
        evidence["status"] = "sent"
        evidence["interaction_ack_status"] = "sent"
        return evidence
    except SendError as exc:
        if getattr(exc, "qq_code", None) == 3:
            evidence["status"] = "sent"
            evidence["interaction_ack_status"] = "sent"
            evidence["interaction_ack_issue_code"] = "qqbot_interaction_ack_duplicate"
            return evidence
        evidence["status"] = "failed"
        evidence["interaction_ack_status"] = "failed"
        evidence["interaction_ack_issue_code"] = "qqbot_interaction_ack_failed"
        evidence["interaction_ack_error"] = str(exc)
        qq_code = getattr(exc, "qq_code", None)
        status_code = getattr(exc, "status_code", None)
        if qq_code is not None:
            evidence["interaction_ack_qq_code"] = qq_code
        if status_code is not None:
            evidence["interaction_ack_status_code"] = status_code
        return evidence


def _run_ack(
    *,
    interaction_id: str,
    token_manager: Any,
    transport: Any,
    code: int,
) -> dict[str, Any]:
    """Run async ack_interaction from sync ensure_interaction_ack."""
    coro = ack_interaction(
        interaction_id=interaction_id,
        token_manager=token_manager,
        transport=transport,
        code=code,
    )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError(
        "ensure_interaction_ack cannot be called from a running event loop; "
        "await sender.ack_interaction directly or call from sync context"
    )
