"""Normalize sanitized WeCom callbacks into platform contract event dictionaries."""

from __future__ import annotations

from typing import Any, Mapping


def normalize_wecom_turn(callback: Mapping[str, Any], *, received_at: str) -> dict[str, Any]:
    """Return an AgentTurn-shaped dictionary for a sanitized WeCom callback."""

    raise NotImplementedError


def normalize_wecom_feedback_callback(callback: Mapping[str, Any], *, created_at: str) -> dict[str, Any]:
    """Return a FeedbackEvent-shaped dictionary for a sanitized WeCom button callback."""

    raise NotImplementedError


__all__ = [
    "normalize_wecom_feedback_callback",
    "normalize_wecom_turn",
]
