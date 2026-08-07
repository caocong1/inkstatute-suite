"""Five-phase progress contract and event-to-phase mapping table.

Defines the canonical five-phase progression (research → intake →
retrieval → draft → review) that the ``phase.changed`` event carries,
plus mapping tables from unified event types to phases and from phases
to UI concepts (thinking / tool / streaming / review).

The mapping is industry-neutral and follows V3-PRD §3.1–§3.2.
"""

from __future__ import annotations

from enum import StrEnum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FivePhase(StrEnum):
    """Canonical five-phase progression for V3 agent runs.

    Order: research → intake → retrieval → draft → review.
    The ``phase.changed`` event (``PhaseChangedPayload``) carries the
    current phase as a string matching one of these values.
    """

    RESEARCH = "research"
    INTAKE = "intake"
    RETRIEVAL = "retrieval"
    DRAFT = "draft"
    REVIEW = "review"


class UiConcept(StrEnum):
    """Four UI rendering concepts that phases map to.

    Derived from V3-PRD §3.1:
    - ``agent_thought_chunk`` → thinking
    - ``tool_call_update`` → tool
    - ``agent_message_chunk`` → streaming
    - review → review
    """

    THINKING = "thinking"
    TOOL = "tool"
    STREAMING = "streaming"
    REVIEW = "review"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Canonical forward-only phase order.
PHASE_ORDER: list[FivePhase] = [
    FivePhase.RESEARCH,
    FivePhase.INTAKE,
    FivePhase.RETRIEVAL,
    FivePhase.DRAFT,
    FivePhase.REVIEW,
]

#: Mapping from unified event type string values to their primary phase.
#:
#: Event types not listed here are not phase-specific:
#: - ``phase.changed`` — it *is* the phase change event itself
#: - ``run.state_changed`` — lifecycle event, not phase-specific
#: - ``error`` — can occur in any phase
EVENT_TYPE_TO_PHASE: dict[str, FivePhase] = {
    # Thinking / reasoning happens during research
    "thought.delta": FivePhase.RESEARCH,
    # Session start begins research
    "session.started": FivePhase.RESEARCH,
    # Plan formation and clarification happen during intake
    "plan.updated": FivePhase.INTAKE,
    "elicitation.requested": FivePhase.INTAKE,
    # Tool calls and permissions for retrieval
    "tool_call.started": FivePhase.RETRIEVAL,
    "tool_call.delta": FivePhase.RETRIEVAL,
    "tool_call.completed": FivePhase.RETRIEVAL,
    "permission.requested": FivePhase.RETRIEVAL,
    # Streaming the draft response
    "message.delta": FivePhase.DRAFT,
    "message.completed": FivePhase.DRAFT,
    # Artifact produced and citations verified during review
    "artifact.created": FivePhase.REVIEW,
    "citation.recorded": FivePhase.REVIEW,
}

#: Mapping from phases to UI concepts.
#:
#: Both RESEARCH and INTAKE map to THINKING because the agent's
#: reasoning and plan formation are rendered as "thinking" in the UI.
#: RETRIEVAL maps to TOOL (tool-call UI).  DRAFT maps to STREAMING
#: (streaming message).  REVIEW maps to REVIEW (review panel).
PHASE_TO_UI_CONCEPT: dict[FivePhase, UiConcept] = {
    FivePhase.RESEARCH: UiConcept.THINKING,
    FivePhase.INTAKE: UiConcept.THINKING,
    FivePhase.RETRIEVAL: UiConcept.TOOL,
    FivePhase.DRAFT: UiConcept.STREAMING,
    FivePhase.REVIEW: UiConcept.REVIEW,
}


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def is_valid_transition(current: FivePhase, next_phase: FivePhase) -> bool:
    """Return ``True`` if *next_phase* is the same as *current* or comes
    after *current* in :data:`PHASE_ORDER`.

    For V3 MVP, phase progression is forward-only: phases can advance or
    stay, but not go backward.
    """
    return PHASE_ORDER.index(next_phase) >= PHASE_ORDER.index(current)


def get_phase_for_event_type(event_type: str) -> FivePhase | None:
    """Look up the primary :class:`FivePhase` for *event_type*.

    Returns ``None`` for unmapped event types (``phase.changed``,
    ``run.state_changed``, ``error``, or any unknown type).
    """
    return EVENT_TYPE_TO_PHASE.get(event_type)


def get_ui_concept_for_phase(phase: FivePhase) -> UiConcept:
    """Look up the :class:`UiConcept` for *phase*."""
    return PHASE_TO_UI_CONCEPT[phase]
