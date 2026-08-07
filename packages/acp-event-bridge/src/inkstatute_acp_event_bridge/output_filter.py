"""ACP-specific output boundary rules — ALLOW / REWRITE / BLOCK decisions.

This module implements ACP-specific output boundary rules that run as a
**pre-filter** before the existing
:class:`platform_runtime.output_boundary.DefaultAssistantOutputBoundary`.

The processing order is:

1. **ACP pre-filter** (this module) — cheapest check: event-type-based
   default-deny, then content-pattern-based block/rewrite for ACP backend
   noise categories.
2. **Existing boundary** (:class:`DefaultAssistantOutputBoundary`) —
   secret patterns, internal paths, provider leaks, operator commands,
   debug traces.

This implements the "output boundary enforced twice" requirement from
AGENTS.md: the bridge is the first enforcement point, the gateway is the
second.

Blocked content categories (requirement ACP-05):
    meta, gateway, system, update, command, help,
    available_commands_update, terminal

Default-deny policy:
    Unknown ACP notification types are blocked by default.  Only event
    types in :data:`ACP_ALLOWED_EVENT_TYPES` may pass through the filter.

Reference-first logging:
    All audit metadata stores only a hash prefix + length — no original
    text is stored in any :class:`FilterDecision`.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from platform_contract.enums import RunEventType
from platform_runtime.output_boundary import DefaultAssistantOutputBoundary


# ---------------------------------------------------------------------------
# Action enum
# ---------------------------------------------------------------------------


class FilterAction(StrEnum):
    """Action taken by the ACP output filter."""

    ALLOW = "allow"
    REWRITE = "rewrite"
    BLOCK = "block"


# ---------------------------------------------------------------------------
# Decision dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FilterDecision:
    """The result of filtering a single event through the ACP output filter.

    Attributes
    ----------
    action
        The filter action: ``"allow"``, ``"rewrite"``, or ``"block"``.
    visible_content
        The content to show to the user.  ``None`` for BLOCK decisions.
        For ALLOW, this is the original (unmodified) content.  For
        REWRITE, this is the business-friendly replacement text.
    audit_metadata
        Reference-first audit metadata.  Contains ``rule_id``,
        ``input_hash_prefix`` (SHA-256 first 16 hex chars),
        ``input_length``, and ``privacy``.  **No original text is
        stored.**
    reason
        Human-readable reason for the decision (typically the rule_id).
    """

    action: str
    visible_content: str | None
    audit_metadata: dict[str, Any]
    reason: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The 8 blocked content category prefixes (requirement ACP-05).
#: These are ACP backend noise that must never reach ordinary users.
ACP_BLOCKED_CONTENT_CATEGORIES: frozenset[str] = frozenset({
    "meta:",
    "gateway:",
    "system:",
    "update:",
    "command:",
    "help:",
    "available_commands_update:",
    "terminal:",
})

#: Explicit allowlist of unified event types that may pass through the
#: filter.  Any event type NOT in this set is blocked by default
#: (default-deny policy).
ACP_ALLOWED_EVENT_TYPES: frozenset[str] = frozenset({
    RunEventType.MESSAGE_DELTA_V3.value,        # "message.delta"
    RunEventType.MESSAGE_COMPLETED.value,        # "message.completed"
    RunEventType.THOUGHT_DELTA.value,            # "thought.delta"
    RunEventType.TOOL_CALL_STARTED_V3.value,     # "tool_call.started"
    RunEventType.TOOL_CALL_DELTA.value,          # "tool_call.delta"
    RunEventType.TOOL_CALL_COMPLETED_V3.value,   # "tool_call.completed"
    RunEventType.PLAN_UPDATED.value,             # "plan.updated"
    RunEventType.PHASE_CHANGED.value,            # "phase.changed"
    RunEventType.ELICITATION_REQUESTED.value,    # "elicitation.requested"
    RunEventType.PERMISSION_REQUESTED.value,     # "permission.requested"
    RunEventType.ARTIFACT_CREATED_V3.value,      # "artifact.created"
    RunEventType.CITATION_RECORDED.value,        # "citation.recorded"
    RunEventType.RUN_STATE_CHANGED.value,        # "run.state_changed"
    RunEventType.ERROR.value,                    # "error"
    RunEventType.SESSION_STARTED.value,          # "session.started"
})

#: Regex patterns for ACP-specific blocked content (case-insensitive).
#: These match the blocked category prefixes in content text.
_ACP_BLOCK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (rule_id, re.compile(pattern, re.IGNORECASE))
    for rule_id, pattern in (
        ("meta_notice", r"\bmeta\s*:"),
        ("gateway_notice", r"\bgateway\s*:"),
        ("system_notice", r"\bsystem\s*:"),
        ("update_notice", r"\bupdate\s*:"),
        ("command_notice", r"\bcommand\s*:"),
        ("help_notice", r"\bhelp\s*:"),
        ("available_commands_update", r"\bavailable_commands_update\b"),
        ("terminal_notice", r"\bterminal\s*:"),
    )
)

#: Regex patterns for content that should be rewritten to a
#: business-friendly notice instead of blocked.
_ACP_REWRITE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (rule_id, re.compile(pattern, re.IGNORECASE))
    for rule_id, pattern in (
        (
            "backend_lifecycle",
            r"\b(?:reconnect(?:ed|ing)?|disconnect(?:ed|ing)?|shutting down|restart(?:ed|ing)?)\b",
        ),
    )
)

#: Business-friendly replacement text for rewritten content.
_BUSINESS_REWRITE_NOTICE = "InkStatute 正在处理您的请求，请等待下一条更新。"


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------


def _audit(text: str, *, rule_id: str) -> dict[str, Any]:
    """Return reference-first audit metadata.

    Stores only a hash prefix and length — **no original text**.
    """
    return {
        "rule_id": rule_id,
        "input_hash_prefix": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        "input_length": len(text),
        "privacy": "no_original_text_stored",
    }


# ---------------------------------------------------------------------------
# Notification extraction helper
# ---------------------------------------------------------------------------


def _extract_update(notification: dict) -> dict | None:
    """Extract the ``update`` dict from an ACP notification.

    Handles both the ``session/update`` notification format (with
    ``params.update``) and direct update dicts (where the notification
    itself *is* the update).
    """
    params = notification.get("params")
    if isinstance(params, dict):
        update = params.get("update")
        if isinstance(update, dict):
            return update
    update = notification.get("update")
    if isinstance(update, dict):
        return update
    return None


# ---------------------------------------------------------------------------
# Filter class
# ---------------------------------------------------------------------------


class ACPOutputFilter:
    """ACP-specific output boundary filter.

    Produces a :class:`FilterDecision` (ALLOW / REWRITE / BLOCK) for each
    event passing through the bridge.  This is the first enforcement
    point of the "output boundary enforced twice" requirement.

    The filter uses a **default-deny** policy for unknown event types
    (explicit allowlist for known types) and blocks 8 ACP backend noise
    content categories.
    """

    def filter_event(
        self,
        event_type: str,
        content: str | None,
        event_metadata: dict | None = None,
    ) -> FilterDecision:
        """Filter a single event through the ACP output boundary.

        Parameters
        ----------
        event_type
            The unified event type string (e.g. ``"message.delta"``).
        content
            The content text to filter.  May be ``None`` or empty.
        event_metadata
            Optional event metadata (currently unused, reserved for
            future extension).

        Returns
        -------
        FilterDecision
            The filter decision with action, visible content, and
            reference-first audit metadata.
        """
        del event_metadata  # reserved for future use

        # (a) Default-deny: event type not in allowlist → BLOCK
        if event_type not in ACP_ALLOWED_EVENT_TYPES:
            audit_text = event_type
            return FilterDecision(
                action=FilterAction.BLOCK.value,
                visible_content=None,
                audit_metadata=_audit(audit_text, rule_id="event_type_not_allowed"),
                reason="event_type_not_allowed",
            )

        # (b) No content to filter → ALLOW
        if content is None or content == "":
            return FilterDecision(
                action=FilterAction.ALLOW.value,
                visible_content=content,
                audit_metadata={
                    "rule_id": "empty_content",
                    "input_hash_prefix": hashlib.sha256(b"").hexdigest()[:16],
                    "input_length": 0,
                    "privacy": "no_original_text_stored",
                },
                reason="empty_content",
            )

        # (c) Normalize for pattern matching
        normalized = content.lower()

        # (d) Check block patterns
        for rule_id, pattern in _ACP_BLOCK_PATTERNS:
            if pattern.search(normalized):
                return FilterDecision(
                    action=FilterAction.BLOCK.value,
                    visible_content=None,
                    audit_metadata=_audit(content, rule_id=rule_id),
                    reason=rule_id,
                )

        # (e) Check rewrite patterns
        for rule_id, pattern in _ACP_REWRITE_PATTERNS:
            if pattern.search(normalized):
                return FilterDecision(
                    action=FilterAction.REWRITE.value,
                    visible_content=_BUSINESS_REWRITE_NOTICE,
                    audit_metadata=_audit(content, rule_id=rule_id),
                    reason=rule_id,
                )

        # (f) No patterns matched → ALLOW
        return FilterDecision(
            action=FilterAction.ALLOW.value,
            visible_content=content,
            audit_metadata=_audit(content, rule_id="business_output"),
            reason="business_output",
        )

    def filter_notification(self, notification: dict) -> FilterDecision:
        """Filter a raw ACP notification dict.

        Extracts the event type and content from the notification and
        delegates to :meth:`filter_event`.

        For ``elicitation/create`` and ``session/request_permission``
        notifications, always returns ALLOW — these are user-facing
        interactive events that must reach the user.

        Parameters
        ----------
        notification
            The raw ACP JSON-RPC notification dict.

        Returns
        -------
        FilterDecision
            The filter decision.
        """
        method = notification.get("method", "")

        # Elicitation and permission requests always pass through
        # to the user — they are interactive events that must not
        # be blocked or rewritten.
        if method == "elicitation/create":
            return FilterDecision(
                action=FilterAction.ALLOW.value,
                visible_content=None,
                audit_metadata={
                    "rule_id": "elicitation_passthrough",
                    "input_hash_prefix": hashlib.sha256(
                        method.encode("utf-8")
                    ).hexdigest()[:16],
                    "input_length": len(method),
                    "privacy": "no_original_text_stored",
                },
                reason="elicitation_passthrough",
            )

        if method == "session/request_permission":
            return FilterDecision(
                action=FilterAction.ALLOW.value,
                visible_content=None,
                audit_metadata={
                    "rule_id": "permission_passthrough",
                    "input_hash_prefix": hashlib.sha256(
                        method.encode("utf-8")
                    ).hexdigest()[:16],
                    "input_length": len(method),
                    "privacy": "no_original_text_stored",
                },
                reason="permission_passthrough",
            )

        # Extract event type and content from session/update
        update = _extract_update(notification)
        if update is not None:
            update_type = update.get("type", "")
            # Map update type to unified event type
            type_map = {
                "agent_message_chunk": RunEventType.MESSAGE_DELTA_V3.value,
                "agent_message": RunEventType.MESSAGE_COMPLETED.value,
                "agent_thought_chunk": RunEventType.THOUGHT_DELTA.value,
                "plan": RunEventType.PLAN_UPDATED.value,
                "plan_update": RunEventType.PLAN_UPDATED.value,
                "elicitation": RunEventType.ELICITATION_REQUESTED.value,
                "status": RunEventType.RUN_STATE_CHANGED.value,
            }
            event_type = type_map.get(update_type, "")
            content = update.get("content", "")
            if not content:
                content = update.get("delta", "")
            return self.filter_event(event_type, content)

        # Unrecognized notification format — default-deny
        return FilterDecision(
            action=FilterAction.BLOCK.value,
            visible_content=None,
            audit_metadata=_audit(str(method), rule_id="unrecognized_notification"),
            reason="unrecognized_notification",
        )

    def apply_with_existing_boundary(
        self,
        event_type: str,
        content: str | None,
        existing_boundary: DefaultAssistantOutputBoundary,
    ) -> FilterDecision:
        """Apply the ACP pre-filter, then the existing boundary.

        The ACP pre-filter runs first (cheapest check — type-based, no
        text scanning for unknown types).  If the pre-filter returns
        BLOCK or REWRITE, the existing boundary is **not** called
        (short-circuit).  If the pre-filter returns ALLOW, the existing
        :meth:`DefaultAssistantOutputBoundary.apply` method is called
        for the second layer of filtering.

        This implements the "output boundary enforced twice" requirement
        from AGENTS.md.

        Parameters
        ----------
        event_type
            The unified event type string.
        content
            The content text to filter.
        existing_boundary
            An instance of
            :class:`DefaultAssistantOutputBoundary` for the second
            enforcement layer.

        Returns
        -------
        FilterDecision
            The combined decision from both enforcement layers.
        """
        # Layer 1: ACP pre-filter
        acp_decision = self.filter_event(event_type, content)

        # Short-circuit: if ACP filter blocks or rewrites, don't call
        # the existing boundary
        if acp_decision.action != FilterAction.ALLOW.value:
            return acp_decision

        # Layer 2: existing boundary
        # Map unified event type to the existing boundary's expected
        # event types.  The existing boundary uses V2-style event types
        # (e.g. "message_delta" not "message.delta"), so we pass
        # event_type as-is and let the boundary decide.
        boundary_decision = existing_boundary.apply(
            visibility_target="user",
            text=content,
            event_type=None,  # Let the boundary do content-based checks
        )

        # Convert BoundaryDecision to FilterDecision
        return FilterDecision(
            action=boundary_decision.action.value
            if hasattr(boundary_decision.action, "value")
            else str(boundary_decision.action),
            visible_content=boundary_decision.visible_text,
            audit_metadata=boundary_decision.audit_metadata,
            reason=boundary_decision.reason,
        )


__all__ = [
    "FilterAction",
    "FilterDecision",
    "ACP_BLOCKED_CONTENT_CATEGORIES",
    "ACP_ALLOWED_EVENT_TYPES",
    "ACPOutputFilter",
]
