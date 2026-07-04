"""Idempotency helpers for sanitized WeCom callbacks (thin shim over channel_core)."""

from __future__ import annotations

from typing import Any, Mapping

from channel_core.idempotency import channel_idempotency_key, digest_short, string_or_none


def wecom_idempotency_key(callback: Mapping[str, Any]) -> str:
    """Return a stable idempotency key for a sanitized WeCom callback."""

    return channel_idempotency_key(callback, channel_prefix="wecom")


__all__ = ["wecom_idempotency_key", "digest_short", "string_or_none"]
