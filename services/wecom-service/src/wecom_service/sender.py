"""WeCom send envelope builders for sanitized service-local tests."""

from __future__ import annotations

from typing import Any

from .output_policy import OutputPolicyDecision, apply_output_policy


def build_text_send_envelope(*, to_user: str, text: str) -> dict[str, Any]:
    """Build a text send envelope after output policy enforcement."""

    decision = apply_output_policy(text)
    envelope = _base_envelope(to_user, decision)
    if decision.action != "block" and decision.visible_text:
        envelope.update(
            {
                "msgtype": "text",
                "text": {"content": decision.visible_text},
            }
        )
    return envelope


def build_file_send_envelope(*, to_user: str, media_id: str, description: str | None = None) -> dict[str, Any]:
    """Build a file send envelope after output policy enforcement."""

    decision = apply_output_policy(description or "InkStatute file delivery")
    envelope = _base_envelope(to_user, decision)
    if decision.action != "block":
        envelope.update(
            {
                "msgtype": "file",
                "file": {"media_id": media_id},
            }
        )
        if decision.visible_text:
            envelope["description"] = decision.visible_text
    return envelope


def build_template_card_envelope(
    *,
    to_user: str,
    card_id: str,
    title: str,
    feedback_target: str,
) -> dict[str, Any]:
    """Build a template-card send envelope after output policy enforcement."""

    decision = apply_output_policy(title)
    envelope = _base_envelope(to_user, decision)
    if decision.action != "block":
        envelope.update(
            {
                "msgtype": "template_card",
                "template_card": {
                    "card_id": card_id,
                    "title": decision.visible_text or title,
                    "feedback_target": feedback_target,
                },
            }
        )
    return envelope


def _base_envelope(to_user: str, decision: OutputPolicyDecision) -> dict[str, Any]:
    return {
        "touser": to_user,
        "policy": {
            "action": decision.action,
            "reason": decision.reason,
            "audit_metadata": decision.audit_metadata,
        },
    }


__all__ = [
    "build_file_send_envelope",
    "build_template_card_envelope",
    "build_text_send_envelope",
]
