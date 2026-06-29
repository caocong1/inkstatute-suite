"""Server-Sent Events helpers for fixture-grade Web/SSE channels."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
import json
from typing import Any, Mapping

from platform_runtime.protocols import RunEvent

JsonObject = dict[str, Any]


def encode_sse_event(event: RunEvent | Mapping[str, Any]) -> str:
    """Encode a runtime event into a deterministic SSE frame."""

    payload = _event_mapping(event)
    _assert_no_forbidden_payload_keys(payload)
    data = json.dumps(_json_ready(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"id: {payload['event_id']}\nevent: {payload['event_type']}\ndata: {data}\n\n"


def _event_mapping(event: RunEvent | Mapping[str, Any]) -> JsonObject:
    if isinstance(event, Mapping):
        payload = dict(event)
    elif is_dataclass(event):
        payload = asdict(event)
    else:
        raise TypeError("event must be a RunEvent or mapping")
    for key in ("event_id", "event_type"):
        if not payload.get(key):
            raise ValueError(f"SSE event requires {key}")
    return payload


def _assert_no_forbidden_payload_keys(value: Any, path: str = "") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
            if normalized in {"rawpayload", "rawbody", "callbackbody"}:
                raise ValueError(f"SSE payload contains forbidden raw payload key at {child_path}")
            _assert_no_forbidden_payload_keys(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_payload_keys(child, f"{path}[{index}]")


def _json_ready(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_json_ready(child) for child in value]
    return value


__all__ = ["encode_sse_event"]
