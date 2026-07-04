"""Delivery-completion guardrails for live WeCom task flows (thin shim over channel_core)."""

from __future__ import annotations

from channel_core.delivery_guard import DeliveryCompletionAssessment, assess_delivery_completion

__all__ = ["DeliveryCompletionAssessment", "assess_delivery_completion"]
