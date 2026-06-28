"""WeCom send envelope builders for sanitized service-local tests."""

from __future__ import annotations

from typing import Any


def build_text_send_envelope(*, to_user: str, text: str) -> dict[str, Any]:
    """Build a text send envelope after output policy enforcement."""

    raise NotImplementedError


def build_file_send_envelope(*, to_user: str, media_id: str, description: str | None = None) -> dict[str, Any]:
    """Build a file send envelope after output policy enforcement."""

    raise NotImplementedError


def build_template_card_envelope(
    *,
    to_user: str,
    card_id: str,
    title: str,
    feedback_target: str,
) -> dict[str, Any]:
    """Build a template-card send envelope after output policy enforcement."""

    raise NotImplementedError


__all__ = [
    "build_file_send_envelope",
    "build_template_card_envelope",
    "build_text_send_envelope",
]
