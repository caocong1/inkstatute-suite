"""Idempotency helpers for sanitized WeCom callbacks."""

from __future__ import annotations

from typing import Any, Mapping


def wecom_idempotency_key(callback: Mapping[str, Any]) -> str:
    """Return a stable idempotency key for a sanitized callback."""

    raise NotImplementedError


__all__ = ["wecom_idempotency_key"]
