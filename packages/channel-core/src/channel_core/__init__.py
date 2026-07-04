"""Channel-generic logic shared across InkStatute channel adapters."""

from __future__ import annotations

from .active_task_router import (
    ActiveTaskRoute,
    ActiveTaskRoutingDecision,
    AdapterTaskCapabilities,
    route_active_task_turn,
)
from .delivery_guard import DeliveryCompletionAssessment, assess_delivery_completion
from .idempotency import channel_idempotency_key, digest_short, string_or_none
from .owned_notices import OWNED_NOTICE_TEMPLATES, NoticeKind, build_owned_notice
from .output_policy import OutputPolicyDecision, apply_output_policy

__all__ = [
    "ActiveTaskRoute",
    "ActiveTaskRoutingDecision",
    "AdapterTaskCapabilities",
    "DeliveryCompletionAssessment",
    "NoticeKind",
    "OWNED_NOTICE_TEMPLATES",
    "OutputPolicyDecision",
    "apply_output_policy",
    "assess_delivery_completion",
    "build_owned_notice",
    "channel_idempotency_key",
    "digest_short",
    "route_active_task_turn",
    "string_or_none",
]
