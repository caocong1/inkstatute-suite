"""QQ Bot egress sender — text/markdown/keyboard envelopes.

Pure envelope builders with output-boundary enforcement. Passive-reply
window, injectable message transport, and HTTP send land in a later plan.
Stdlib + channel_core only; dependencies = [] invariant preserved.
"""

from __future__ import annotations

from typing import Any

from channel_core.output_policy import OutputPolicyDecision, apply_output_policy

FEEDBACK_ACTIONS = ("up", "down", "needs_fix", "route_wrong")

_FEEDBACK_LABELS = {
    "up": "有帮助",
    "down": "需改进",
    "needs_fix": "需要修正",
    "route_wrong": "路由错误",
}

_WIRE_AUDIT_KEYS = frozenset({"policy", "inkstatute"})


def _base_envelope(
    decision: OutputPolicyDecision,
    *,
    msg_id: str,
    msg_seq: int,
) -> dict[str, Any]:
    return {
        "msg_id": msg_id,
        "msg_seq": msg_seq,
        "policy": {
            "action": decision.action,
            "reason": decision.reason,
            "audit_metadata": decision.audit_metadata,
        },
    }


def build_text_envelope(
    *,
    content: str,
    msg_id: str,
    msg_seq: int = 1,
) -> dict[str, Any]:
    """Build a QQ text send envelope (msg_type=0) after output policy."""

    decision = apply_output_policy(content)
    envelope = _base_envelope(decision, msg_id=msg_id, msg_seq=msg_seq)
    if decision.action != "block" and decision.visible_text:
        envelope.update({"msg_type": 0, "content": decision.visible_text})
    return envelope


def build_markdown_envelope(
    *,
    content: str,
    msg_id: str,
    msg_seq: int = 1,
) -> dict[str, Any]:
    """Build a QQ markdown send envelope (msg_type=2) after output policy."""

    decision = apply_output_policy(content)
    envelope = _base_envelope(decision, msg_id=msg_id, msg_seq=msg_seq)
    if decision.action != "block" and decision.visible_text:
        envelope.update(
            {
                "msg_type": 2,
                "markdown": {"content": decision.visible_text},
                "content": "",
            }
        )
    return envelope


def build_feedback_keyboard_envelope(
    *,
    title: str,
    feedback_target: str,
    msg_id: str,
    msg_seq: int = 1,
) -> dict[str, Any]:
    """Build markdown + keyboard feedback card (msg_type=2) after output policy."""

    decision = apply_output_policy(title)
    envelope = _base_envelope(decision, msg_id=msg_id, msg_seq=msg_seq)
    if decision.action == "block":
        return envelope

    visible = decision.visible_text or "请评价本次回复"
    buttons: list[dict[str, Any]] = []
    for action in FEEDBACK_ACTIONS:
        label = _FEEDBACK_LABELS[action]
        buttons.append(
            {
                "id": action,
                "render_data": {
                    "label": label,
                    "visited_label": label,
                    "style": 1,
                },
                "action": {
                    "type": 1,
                    "permission": {"type": 2},
                    "data": action,
                    "unsupport_tips": "请升级 QQ 后重试",
                },
            }
        )

    envelope.update(
        {
            "msg_type": 2,
            "markdown": {"content": visible},
            "keyboard": {"content": {"rows": [{"buttons": buttons}]}},
            "inkstatute": {"feedback_target": feedback_target},
        }
    )
    return envelope


def strip_for_wire(envelope: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy without audit-only keys for QQ OpenAPI POST."""

    return {key: value for key, value in envelope.items() if key not in _WIRE_AUDIT_KEYS}


__all__ = [
    "FEEDBACK_ACTIONS",
    "build_feedback_keyboard_envelope",
    "build_markdown_envelope",
    "build_text_envelope",
    "strip_for_wire",
]
