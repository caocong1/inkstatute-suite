"""Bot degradation aggregator — declarative rules and deterministic output.

This module implements the non-streaming bot degradation layer for V3.
Given a sequence of unified ``RunEvent`` dicts, the pure-function
``aggregate_events`` produces a deterministic :class:`BotDelivery` result.

Each of the 13 unified event categories (15 enum values — tool_call has
three sub-types) has a *declared* degradation category per V3-PRD §3.2:

    SILENT             — session.started          → drop entirely
    BUFFER             — message.delta            → accumulate, deliver on message.completed
    DELIVER            — message.completed        → send as final message/card/file
                        elicitation.requested
                        permission.requested
                        artifact.created
    DISCARD            — thought.delta            → drop (no business value for bots)
    FOLD               — tool_call.started/delta/completed → collapse to business prompt
    FIRST_THEN_SILENT  — plan.updated             → first occurrence delivered, rest silent
                        phase.changed
    ATTACH             — citation.recorded        → append to final delivered message
    ON_FAILURE         — run.state_changed        → only deliver on failure
                        error

The aggregator is a **pure function**: same input always produces the same
output.  No random, no time-dependent behaviour, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .events import JsonObject


# ---------------------------------------------------------------------------
# Degradation categories (8 members per V3-PRD §3.2)
# ---------------------------------------------------------------------------


class DegradationCategory(StrEnum):
    """The 8 bot degradation categories declared in V3-PRD §3.2."""

    SILENT = "silent"
    BUFFER = "buffer"
    DELIVER = "deliver"
    DISCARD = "discard"
    FOLD = "fold"
    FIRST_THEN_SILENT = "first_then_silent"
    ATTACH = "attach"
    ON_FAILURE = "on_failure"


# ---------------------------------------------------------------------------
# Declarative degradation rules — event type → category
# ---------------------------------------------------------------------------

DEGRADATION_RULES: dict[str, DegradationCategory] = {
    "session.started": DegradationCategory.SILENT,
    "message.delta": DegradationCategory.BUFFER,
    "message.completed": DegradationCategory.DELIVER,
    "thought.delta": DegradationCategory.DISCARD,
    "tool_call.started": DegradationCategory.FOLD,
    "tool_call.delta": DegradationCategory.FOLD,
    "tool_call.completed": DegradationCategory.FOLD,
    "plan.updated": DegradationCategory.FIRST_THEN_SILENT,
    "phase.changed": DegradationCategory.FIRST_THEN_SILENT,
    "elicitation.requested": DegradationCategory.DELIVER,
    "permission.requested": DegradationCategory.DELIVER,
    "artifact.created": DegradationCategory.DELIVER,
    "citation.recorded": DegradationCategory.ATTACH,
    "run.state_changed": DegradationCategory.ON_FAILURE,
    "error": DegradationCategory.ON_FAILURE,
}


# ---------------------------------------------------------------------------
# Business-prompt templates (industry-neutral, user-facing Chinese)
# ---------------------------------------------------------------------------

_TOOL_FOLD_PROMPT = "正在检索法规…"
_PLAN_FIRST_PROMPT = "仍在处理"
_FAILURE_PROMPT = "处理失败，请稍后重试或联系管理员"


# ---------------------------------------------------------------------------
# BotDelivery — the deterministic output of the aggregator
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BotDelivery:
    """Deterministic delivery result produced by :func:`aggregate_events`.

    All fields are populated purely from the input event sequence — no
    time-dependent or random behaviour.
    """

    final_message: str | None = None
    intermediate_prompts: list[str] = field(default_factory=list)
    cards: list[JsonObject] = field(default_factory=list)
    files: list[JsonObject] = field(default_factory=list)
    citations: list[JsonObject] = field(default_factory=list)
    error_prompt: str | None = None
    delivered: bool = False


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_degradation_category(event_type: str) -> DegradationCategory | None:
    """Return the degradation category for *event_type*, or ``None`` for
    unknown (e.g. V2) event types.
    """
    return DEGRADATION_RULES.get(event_type)


# ---------------------------------------------------------------------------
# Pure-function aggregator
# ---------------------------------------------------------------------------


def aggregate_events(events: list[dict]) -> BotDelivery:
    """Aggregate a sequence of unified ``RunEvent`` dicts into a
    deterministic :class:`BotDelivery`.

    The function is **pure**: the same input always produces the same
    output.  Events are sorted by ``seq`` ascending before processing so
    that out-of-order delivery does not affect the result.

    Parameters
    ----------
    events:
        A list of plain dicts, each representing a serialized
        :class:`~platform_contract.RunEvent`.  Each dict must have at
        minimum ``event_type`` and ``seq`` keys.  Optional keys used by
        the aggregator include ``payload``, ``message_delta``, and
        ``error``.

    Returns
    -------
    BotDelivery
        The deterministic delivery result.
    """
    # Sort by seq ascending — handles out-of-order events.
    sorted_events = sorted(events, key=lambda e: e.get("seq", 0))

    # Mutable accumulators
    buffer_parts: list[str] = []
    final_message: str | None = None
    intermediate_prompts: list[str] = []
    cards: list[JsonObject] = []
    files: list[JsonObject] = []
    citations: list[JsonObject] = []
    error_prompt: str | None = None
    delivered = False

    # State flags for first-then-silent and fold
    first_plan_or_phase_seen = False
    first_tool_call_seen = False

    for event in sorted_events:
        event_type = event.get("event_type", "")
        category = DEGRADATION_RULES.get(event_type)

        if category is None:
            # Unknown / V2 event type — skip (no V3 degradation rule).
            continue

        payload: JsonObject = event.get("payload") or {}

        if category is DegradationCategory.SILENT:
            continue

        if category is DegradationCategory.DISCARD:
            continue

        if category is DegradationCategory.BUFFER:
            delta = event.get("message_delta")
            if delta is None:
                delta = payload.get("delta")
            if delta:
                buffer_parts.append(delta)
            continue

        if category is DegradationCategory.DELIVER:
            if event_type == "message.completed":
                content = payload.get("content")
                if content:
                    final_message = content
                elif buffer_parts:
                    final_message = "".join(buffer_parts)
                else:
                    # message.completed with no content and no buffered
                    # deltas — nothing to deliver as final message.
                    pass
                delivered = True
            elif event_type in ("elicitation.requested", "permission.requested"):
                cards.append(payload)
                delivered = True
            elif event_type == "artifact.created":
                files.append(payload)
                delivered = True
            continue

        if category is DegradationCategory.FOLD:
            if not first_tool_call_seen:
                intermediate_prompts.append(_TOOL_FOLD_PROMPT)
                first_tool_call_seen = True
            # Subsequent tool_call events are silent.
            continue

        if category is DegradationCategory.FIRST_THEN_SILENT:
            if not first_plan_or_phase_seen:
                intermediate_prompts.append(_PLAN_FIRST_PROMPT)
                first_plan_or_phase_seen = True
            continue

        if category is DegradationCategory.ATTACH:
            citation_list = payload.get("citations")
            if citation_list and isinstance(citation_list, list):
                citations.extend(citation_list)
            continue

        if category is DegradationCategory.ON_FAILURE:
            if event_type == "run.state_changed":
                status = payload.get("status")
                if status == "failed":
                    error_prompt = _FAILURE_PROMPT
                    delivered = True
            elif event_type == "error":
                error_prompt = _FAILURE_PROMPT
                delivered = True
            continue

    # Attach citations to final message if both exist.
    if final_message is not None and citations:
        final_message = _append_citations(final_message, citations)

    return BotDelivery(
        final_message=final_message,
        intermediate_prompts=intermediate_prompts,
        cards=cards,
        files=files,
        citations=citations,
        error_prompt=error_prompt,
        delivered=delivered,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _append_citations(message: str, citations: list[JsonObject]) -> str:
    """Append a formatted reference section to *message*."""
    lines = [message, "", "引用："]
    for i, citation in enumerate(citations, 1):
        source = citation.get("source", "")
        status = citation.get("status", "")
        lines.append(f"[{i}] {source}（{status}）")
    return "\n".join(lines)


__all__ = [
    "DegradationCategory",
    "DEGRADATION_RULES",
    "BotDelivery",
    "aggregate_events",
    "get_degradation_category",
]
