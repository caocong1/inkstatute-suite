"""Neutral assistant output boundary for runtime-visible stream text."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
from enum import StrEnum
from typing import Mapping

from platform_contract.enums import RunEventType
from platform_contract.events import JsonObject


class BoundaryAction(StrEnum):
    ALLOW = "allow"
    REWRITE = "rewrite"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class BoundaryDecision:
    action: BoundaryAction
    visible_text: str | None = None
    audit_metadata: JsonObject = field(default_factory=dict)
    reason: str = "business_output"


_ALLOWED_STREAM_EVENT_TYPES = frozenset({
    RunEventType.STATE_CHANGED.value,
    RunEventType.MESSAGE_DELTA.value,
    RunEventType.STEP_STARTED.value,
    RunEventType.STEP_COMPLETED.value,
    RunEventType.ARTIFACT_CREATED.value,
    RunEventType.APPROVAL_REQUESTED.value,
})


class DefaultAssistantOutputBoundary:
    """Apply generic output policy before ordinary-user visibility."""

    def apply(
        self,
        visibility_target: str,
        text: str | None = None,
        event_metadata: Mapping[str, object] | None = None,
        event_type: str | None = None,
    ) -> BoundaryDecision:
        if event_type is not None and event_type not in _ALLOWED_STREAM_EVENT_TYPES:
            return BoundaryDecision(
                action=BoundaryAction.BLOCK,
                visible_text=None,
                audit_metadata={"rule_id": "event_type_not_allowed", "event_type": event_type},
                reason="event_type_not_allowed",
            )
        del visibility_target, event_metadata
        visible_text = "" if text is None else str(text)
        normalized = visible_text.lower()

        matched = _first_match(_HARD_BLOCK_RULES, normalized)
        if matched is not None:
            return BoundaryDecision(
                action=BoundaryAction.BLOCK,
                visible_text=None,
                audit_metadata=_audit(visible_text, rule_id=matched),
                reason=matched,
            )

        matched = _first_match(_REWRITE_RULES, normalized)
        if matched is not None:
            return BoundaryDecision(
                action=BoundaryAction.REWRITE,
                visible_text=_OWNED_SERVICE_NOTICE,
                audit_metadata={
                    **_audit(visible_text, rule_id=matched),
                    "replacement_owner": "inkstatute_runtime",
                },
                reason=matched,
            )

        matched = _first_match(_OPERATOR_COMMAND_RULES, normalized)
        if matched is not None:
            return BoundaryDecision(
                action=BoundaryAction.BLOCK,
                visible_text=None,
                audit_metadata=_audit(visible_text, rule_id=matched),
                reason=matched,
            )

        return BoundaryDecision(
            action=BoundaryAction.ALLOW,
            visible_text=visible_text,
            audit_metadata=_audit(visible_text, rule_id="business_output"),
            reason="business_output",
        )


_OWNED_SERVICE_NOTICE = "InkStatute is processing your request. Please wait for the next update."


_HARD_BLOCK_RULES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (rule_id, re.compile(pattern))
    for rule_id, pattern in (
        ("secret_like", r"\b(?:access|refresh|api|client|encoding)[_-]?(?:token|key|secret)\b"),
        ("secret_like", r"\b(?:token|secret|key)\s*[:=]"),
        ("internal_path", r"(?:^|\s)(?:/[^ \n\t]+){2,}"),
        ("internal_path", r"[a-z]:\\[^ \n\t]+"),
        ("debug_trace", r"\b(?:admin_notice|stack trace|traceback|delivery debug|runtime detail)\b"),
        ("provider_leak", r"\b(?:model[:\s]|provider[:\s]|api[_-]?key|quota|token[_\s-]?usage)(?!\w)"),
        ("api_error", r"\b(?:api key invalid|quota exceeded|rate limit retry|insufficient quota)\b"),
        ("function_trace", r"\b(?:function call|tool output|token usage report|function_call_result)\b"),
    )
)

_OPERATOR_COMMAND_RULES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (rule_id, re.compile(pattern))
    for rule_id, pattern in (
        ("operator_command", r"(?:^|\s)/[a-z][a-z0-9_-]*\b"),
    )
)

_REWRITE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (rule_id, re.compile(pattern))
    for rule_id, pattern in (
        ("backend_lifecycle", r"\b(?:self[- ]?update|restart(?:ed)?|reconnect(?:ed)?|disconnect(?:ed)?|shutting down)\b"),
        ("tool_progress", r"\b(?:tool progress|internal retrieval|memory sync|tool call)\b"),
        ("approval_request", r"\b(?:dangerous command|approval required|requires approval)\b"),
        ("debug_trace", r"\b(?:debug|diagnostic)\b"),
        ("rate_limit_notice", r"\b(?:rate[_ ]?limit(?:ed|ing)?|too many requests|retrying(?: after)? \d+)\b"),
        ("context_window", r"\b(?:context (?:window|length) (?:exceeded|limit)|maximum context|token limit)\b"),
    )
)


def _first_match(rules: tuple[tuple[str, re.Pattern[str]], ...], text: str) -> str | None:
    for rule_id, pattern in rules:
        if pattern.search(text):
            return rule_id
    return None


def _audit(text: str, *, rule_id: str) -> JsonObject:
    return {
        "rule_id": rule_id,
        "input_hash_prefix": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        "input_length": len(text),
        "privacy": "no_original_text_stored",
    }


__all__ = [
    "BoundaryAction",
    "BoundaryDecision",
    "DefaultAssistantOutputBoundary",
]
