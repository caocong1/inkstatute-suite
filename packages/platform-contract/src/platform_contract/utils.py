"""Shared utility functions for InkStatute V2 platform code.

Consolidates small helpers that were independently duplicated across
wecom-service, feedback-service, hermes-contract-layer, and
conversation-read-view.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping


def coerce_str(value: Any) -> str | None:
    """Return a stripped string, or ``None`` if *value* is ``None`` or blank."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def mapping_or_empty(value: Any) -> dict[str, Any]:
    """Return ``dict(value)`` when *value* is a Mapping, else ``{}``."""
    return dict(value) if isinstance(value, Mapping) else {}


def find_forbidden_key(value: Any, needle: str, path: str = "") -> str | None:
    """Recursively locate an exact key *needle* in nested data.

    Returns the dot-path of the first match, or ``None``.
    """
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key == needle:
                return child_path
            found = find_forbidden_key(child, needle, child_path)
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = find_forbidden_key(child, needle, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def sha256_short(value: str, *, length: int = 16) -> str:
    """Return the first *length* hex characters of the SHA-256 digest."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def stable_id(prefix: str, *parts: object) -> str:
    """Build a deterministic ``{prefix}-{sha256_short}`` identifier."""
    digest = sha256_short(":".join(str(part) for part in parts))
    return f"{prefix}-{digest}"


def timestamp_bucket(created_at: str) -> str:
    """Normalize an ISO-8601 timestamp to a minute-level UTC bucket."""
    try:
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return created_at[:16]
    normalized = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def json_clone(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep copy of *value* via a JSON round-trip."""
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


def coerce_datetime(value: datetime | str | None) -> datetime:
    """Coerce *value* to a timezone-aware ``datetime`` (defaults to UTC)."""
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def format_timestamp(value: datetime | str | Any) -> str:
    """Format *value* as an ISO-8601 string with a ``Z`` suffix."""
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str):
        if value.endswith("+00:00"):
            return value[:-6] + "Z"
        return value
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def feedback_event_type(action: str) -> str:
    """Map a feedback action string to its contract event type."""
    if action == "up":
        return "rating"
    if action == "route_wrong":
        return "route_mismatch"
    return "correction"


__all__ = [
    "coerce_datetime",
    "coerce_str",
    "feedback_event_type",
    "find_forbidden_key",
    "format_timestamp",
    "json_clone",
    "mapping_or_empty",
    "sha256_short",
    "stable_id",
    "timestamp_bucket",
]
