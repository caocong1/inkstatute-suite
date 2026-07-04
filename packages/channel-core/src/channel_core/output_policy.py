"""Assistant output boundary for ordinary user delivery."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any

from .owned_notices import build_owned_notice


@dataclass(frozen=True)
class OutputPolicyDecision:
    action: str
    reason: str
    visible_text: str | None
    audit_metadata: dict[str, Any]


def apply_output_policy(
    message: str,
    *,
    policy_name: str = "inkstatute_channel_output_boundary",
    replacement_owner: str = "inkstatute_channel_service",
) -> OutputPolicyDecision:
    """Classify backend output before ordinary-user delivery."""

    text = str(message or "")
    normalized = text.lower()

    if _matches(_BLOCK_PATTERNS, normalized):
        return OutputPolicyDecision(
            action="block",
            reason="internal_or_secret_bearing_notice",
            visible_text=None,
            audit_metadata=_audit(text, rule="block_internal_notice", policy_name=policy_name),
        )

    if _matches(_REWRITE_PATTERNS, normalized):
        return OutputPolicyDecision(
            action="rewrite",
            reason="backend_lifecycle_notice",
            visible_text=build_owned_notice("backend_lifecycle"),
            audit_metadata={
                **_audit(text, rule="rewrite_backend_lifecycle", policy_name=policy_name),
                "replacement_owner": replacement_owner,
            },
        )

    return OutputPolicyDecision(
        action="allow",
        reason="business_output",
        visible_text=text,
        audit_metadata=_audit(text, rule="allow_business_output", policy_name=policy_name),
    )


_BLOCK_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"\badmin_notice\b",
        r"\bstack trace\b",
        r"\btraceback\b",
        r"\btoken\s*=",
        r"\b(access[_-]?token|encodingaeskey|api[_-]?key|client[_-]?secret|secret[_-]?key)\b",
        r"\bsecret\s*[:=]",
        r"(^|\s)/(help|status|credits|insights|update|restart|debug|memory)\b",
        r"\bself[- ]?update\b",
        r"\btool progress\b",
        r"\bmemory sync\b",
        r"\bdangerous command\b",
        r"/home/[^ ]+",
        r"\.hermes",
        r"\bprofile path\b",
        r"\bruntime detail\b",
        r"\benv\b.*\b(secret|token|key)\b",
        r"\bdelivery debug\b",
    )
]

_REWRITE_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"\bgateway\b.*\b(online|restart|restarted|shutting down|disconnected|reconnected|failure)\b",
        r"\b(online|restart|restarted|disconnected|reconnected)\b.*\bgateway\b",
        r"\bbackend lifecycle\b",
        r"\bservice restart\b",
    )
]


def _matches(patterns: list[re.Pattern[str]], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _audit(text: str, *, rule: str, policy_name: str) -> dict[str, Any]:
    return {
        "policy": policy_name,
        "rule": rule,
        "input_sha256_16": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        "input_length": len(text),
        "privacy": "no_original_text_stored",
    }


__all__ = ["OutputPolicyDecision", "apply_output_policy"]
