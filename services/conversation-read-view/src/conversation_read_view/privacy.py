"""Privacy helpers for contract-log-derived read views."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from platform_contract.utils import find_forbidden_key


FORBIDDEN_RAW_PAYLOAD_KEY = "raw_payload"


def find_forbidden_raw_payload_path(value: Any, path: str = "") -> str | None:
    """Return the first exact raw payload key path, if one is present."""
    return find_forbidden_key(value, FORBIDDEN_RAW_PAYLOAD_KEY, path)


def scrub_contract_payload(value: Any) -> Any:
    """Return a JSON-like copy after rejecting exact raw payload fields."""

    forbidden_path = find_forbidden_raw_payload_path(value)
    if forbidden_path is not None:
        raise ValueError(f"contract read views must not expose {FORBIDDEN_RAW_PAYLOAD_KEY} at {forbidden_path}")

    if isinstance(value, Mapping):
        return {str(key): scrub_contract_payload(child) for key, child in value.items()}
    if isinstance(value, list):
        return [scrub_contract_payload(child) for child in value]
    return value


__all__ = [
    "FORBIDDEN_RAW_PAYLOAD_KEY",
    "find_forbidden_raw_payload_path",
    "scrub_contract_payload",
]
