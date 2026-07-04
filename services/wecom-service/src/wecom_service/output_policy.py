"""Assistant output boundary for ordinary InkStatute WeCom delivery (thin shim over channel_core)."""

from __future__ import annotations

from channel_core.output_policy import OutputPolicyDecision, apply_output_policy as _core_apply


def apply_output_policy(message: str) -> OutputPolicyDecision:
    """Classify backend output before ordinary-user WeCom delivery."""

    return _core_apply(
        message,
        policy_name="inkstatute_wecom_output_boundary",
        replacement_owner="inkstatute_wecom_service",
    )


__all__ = ["OutputPolicyDecision", "apply_output_policy"]
