"""Append-only runtime audit records for operator-run WeCom validation."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping


_SECRET_KEY_HINTS = ("secret", "token", "key", "password", "authorization", "cookie")


def append_runtime_audit(
    path: str | Path,
    *,
    kind: str,
    direction: str,
    payload: Any | None = None,
    include_payload: bool = False,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a private JSONL audit event and return the written record.

    The audit file is runtime evidence, not a contract log. It may contain raw
    legal payload text when ``include_payload`` is true, so callers should keep
    it outside the repo and never commit it.
    """

    record = {
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "kind": str(kind),
        "direction": str(direction),
        "payload_summary": _payload_summary(payload),
        "metadata": _redact_secrets(dict(metadata or {})),
    }
    if include_payload:
        record["payload"] = _redact_secrets(payload)

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return record


def parse_bool_env(value: str | None, *, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _payload_summary(payload: Any | None) -> dict[str, Any]:
    text = _stable_json(payload)
    return {
        "sha256_16": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        "length": len(text),
    }


def _stable_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        return str(value)


def _redact_secrets(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(hint in key_text.lower() for hint in _SECRET_KEY_HINTS):
                redacted[key_text] = "[REDACTED]"
            else:
                redacted[key_text] = _redact_secrets(item)
        return redacted
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_secrets(item) for item in value]
    if isinstance(value, str):
        return _redact_known_env_values(value)
    return value


def _redact_known_env_values(text: str) -> str:
    redacted = text
    for name, secret in os.environ.items():
        if not secret or len(secret) < 8:
            continue
        if any(hint in name.lower() for hint in _SECRET_KEY_HINTS):
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


__all__ = ["append_runtime_audit", "parse_bool_env"]
