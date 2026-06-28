"""Deterministic ID helpers for Hermes contract events."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_hash_id(prefix: str, *parts: Any, length: int = 16) -> str:
    """Return a stable, JSON-derived identifier with the requested prefix."""

    payload = json.dumps(
        [_json_safe(part) for part in parts],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}-{digest}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
