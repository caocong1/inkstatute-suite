"""Assistant output boundary for ordinary InkStatute WeCom delivery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OutputPolicyDecision:
    action: str
    reason: str
    visible_text: str | None
    audit_metadata: dict[str, Any]


def apply_output_policy(message: str) -> OutputPolicyDecision:
    """Classify backend output before ordinary-user WeCom delivery."""

    raise NotImplementedError


__all__ = ["OutputPolicyDecision", "apply_output_policy"]
