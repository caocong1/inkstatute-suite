"""ColdStartInterviewOrchestrator — sequential elicitation for the 5-step
cold-start interview.

The orchestrator manages the multi-round cold-start interview, emitting
:class:`ElicitationRequestedPayload` objects in sequence.  Each step maps
to one ``elicitation.requested`` event with 2-4 questions (enforced by
:func:`validate_question_count`).

The orchestrator is **stateless** between calls — it receives an
:class:`InterviewState` and returns a new (immutable) state.  The caller
(Gateway, Plan 99-03) is responsible for persisting the state between
rounds and converting the returned :class:`ElicitationRequestedPayload`
into an actual ``RunEvent``.

The orchestrator does **not** create any ``RunEvent`` directly — it
returns :class:`ElicitationRequestedPayload` objects that the caller
converts to events (binding constraint: no practice profiles in the
contract event log).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platform_contract.events import JsonObject
from platform_contract.unified_events import (
    ElicitationQuestion,
    ElicitationRequestedPayload,
)

from .model import PracticeProfile
from .store import PracticeProfileStore


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InterviewStep:
    """A single step in the cold-start interview.

    Attributes
    ----------
    step_id
        Unique identifier for the step (e.g. ``"identity-team"``).
    intro
        Chinese intro text displayed to the user before the questions.
    questions
        2-4 :class:`ElicitationQuestion` objects for this step.
    """

    step_id: str
    intro: str
    questions: list[ElicitationQuestion]


@dataclass(frozen=True, slots=True)
class InterviewState:
    """Immutable state of an in-progress cold-start interview.

    Attributes
    ----------
    tenant_id
        The tenant whose profile is being configured.
    plugin
        The plugin name (e.g. ``"commercial-legal"``).
    current_step_index
        Zero-based index of the current step.  When
        ``current_step_index >= len(steps)``, the interview is complete.
    completed_steps
        List of step_ids that have been completed (in order).
    answers
        Nested dict: ``step_id → question_id → answer``.
    """

    tenant_id: str
    plugin: str
    current_step_index: int = 0
    completed_steps: list[str] = field(default_factory=list)
    answers: dict[str, dict[str, str]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ColdStartInterviewOrchestrator
# ---------------------------------------------------------------------------


class ColdStartInterviewOrchestrator:
    """Manages the 5-step cold-start interview via sequential elicitation.

    The orchestrator is constructed with a :class:`PracticeProfileStore`
    and a list of :class:`InterviewStep` definitions.  For
    commercial-legal, use :data:`COMMERCIAL_LEGAL_INTERVIEW_STEPS`.

    The orchestrator is stateless between calls — all state is carried
    in the :class:`InterviewState` that is passed and returned.
    """

    def __init__(
        self,
        store: PracticeProfileStore,
        steps: list[InterviewStep],
    ) -> None:
        self._store = store
        self._steps = steps

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def steps(self) -> list[InterviewStep]:
        """The interview step definitions."""
        return self._steps

    @property
    def total_steps(self) -> int:
        """Total number of steps in the interview."""
        return len(self._steps)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, tenant_id: str, plugin: str) -> InterviewState:
        """Begin a new cold-start interview.

        Returns an :class:`InterviewState` with ``current_step_index=0``,
        ``completed_steps=[]``, and ``answers={}``.
        """
        return InterviewState(
            tenant_id=tenant_id,
            plugin=plugin,
            current_step_index=0,
            completed_steps=[],
            answers={},
        )

    def get_current_elicitation(
        self, state: InterviewState
    ) -> ElicitationRequestedPayload:
        """Return the elicitation payload for the current step.

        Raises :class:`ValueError` if the interview is already complete.
        """
        if self.is_complete(state):
            raise ValueError(
                "Interview is already complete — no more steps to elicit."
            )
        step = self._steps[state.current_step_index]
        interrupt_id = self._make_interrupt_id(state, step.step_id)
        return ElicitationRequestedPayload(
            interrupt_id=interrupt_id,
            intro=step.intro,
            questions=list(step.questions),
            resume_state_ref=f"interview-{state.tenant_id}-{state.plugin}",
            metadata={
                "step_id": step.step_id,
                "step_index": state.current_step_index,
                "total_steps": self.total_steps,
            },
        )

    def submit_answers(
        self,
        state: InterviewState,
        answers: dict[str, str],
    ) -> InterviewState:
        """Record answers for the current step and advance to the next.

        Returns a new :class:`InterviewState` with the current step's
        answers recorded, ``current_step_index`` incremented, and the
        step_id added to ``completed_steps``.

        Raises :class:`ValueError` if the interview is already complete.
        """
        if self.is_complete(state):
            raise ValueError(
                "Interview is already complete — cannot submit more answers."
            )
        step = self._steps[state.current_step_index]

        # Build new answers dict (immutable update)
        new_answers: dict[str, dict[str, str]] = {
            k: dict(v) for k, v in state.answers.items()
        }
        new_answers[step.step_id] = dict(answers)

        new_completed = list(state.completed_steps) + [step.step_id]

        return InterviewState(
            tenant_id=state.tenant_id,
            plugin=state.plugin,
            current_step_index=state.current_step_index + 1,
            completed_steps=new_completed,
            answers=new_answers,
        )

    def is_complete(self, state: InterviewState) -> bool:
        """Return ``True`` when all steps have been completed."""
        return state.current_step_index >= len(self._steps)

    def finalize(self, state: InterviewState) -> PracticeProfile:
        """Construct a :class:`PracticeProfile` from collected answers.

        Writes the profile to the store via ``store.upsert`` and returns
        it.  The profile has ``temporary_mode=False``.

        Raises :class:`ValueError` if the interview is not complete.
        """
        if not self.is_complete(state):
            raise ValueError(
                "Cannot finalize an incomplete interview — "
                f"step {state.current_step_index + 1} of {self.total_steps} "
                "is still pending."
            )

        profile = self._build_profile(state)
        self._store.upsert(state.tenant_id, profile)
        return profile

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_interrupt_id(
        self, state: InterviewState, step_id: str
    ) -> str:
        """Generate a deterministic interrupt_id for a step.

        Format: ``interview-<tenant_id>-<plugin>-<step_id>``
        """
        return f"interview-{state.tenant_id}-{state.plugin}-{step_id}"

    def _build_profile(self, state: InterviewState) -> PracticeProfile:
        """Construct a :class:`PracticeProfile` from the collected answers.

        Maps interview answers to the appropriate profile fields based on
        the step and question IDs.
        """
        identity: JsonObject = {}
        user_role: JsonObject = {}
        integrations: JsonObject = {}
        escalation_matrix: JsonObject = {}
        document_style: JsonObject = {}
        shared_guardrails: JsonObject = {}
        plugin_config: JsonObject = {}

        answers = state.answers

        # Step 1: identity-team
        id_answers = answers.get("identity-team", {})
        if "identity-team.company_name" in id_answers:
            identity["org_name"] = id_answers["identity-team.company_name"]
        if "identity-team.entity_type" in id_answers:
            identity["entity_type"] = id_answers["identity-team.entity_type"]
        if "identity-team.team_size" in id_answers:
            identity["team_size"] = id_answers["identity-team.team_size"]
        if "identity-team.counterparty_type" in id_answers:
            identity["counterparty_type"] = id_answers[
                "identity-team.counterparty_type"
            ]

        # Step 2: review-stance
        rs_answers = answers.get("review-stance", {})
        if "review-stance.risk_appetite" in rs_answers:
            plugin_config["风险偏好"] = rs_answers["review-stance.risk_appetite"]
        if "review-stance.primary_side" in rs_answers:
            side = rs_answers["review-stance.primary_side"]
            if side == "甲方":
                plugin_config["主要立场"] = "甲方"
            elif side == "乙方":
                plugin_config["主要立场"] = "乙方"
            else:
                plugin_config["主要立场"] = "两方都有"

        # Step 3: escalation-rules
        esc_answers = answers.get("escalation-rules", {})
        if "escalation-rules.junior_threshold" in esc_answers:
            escalation_matrix["junior_threshold"] = esc_answers[
                "escalation-rules.junior_threshold"
            ]
        if "escalation-rules.auto_escalation_triggers" in esc_answers:
            triggers_raw = esc_answers["escalation-rules.auto_escalation_triggers"]
            triggers = [t for t in triggers_raw.split("|") if t]
            escalation_matrix["auto_escalation_triggers"] = triggers
            escalation_matrix["auto_escalation"] = len(triggers) > 0

        # Step 4: document-style
        ds_answers = answers.get("document-style", {})
        if "document-style.revision_tone" in ds_answers:
            document_style["revision_tone"] = ds_answers[
                "document-style.revision_tone"
            ]
        if "document-style.citation_preference" in ds_answers:
            document_style["citation_style"] = ds_answers[
                "document-style.citation_preference"
            ]

        # Step 5: jurisdiction-profile
        jp_answers = answers.get("jurisdiction-profile", {})
        if "jurisdiction-profile.governing_law" in jp_answers:
            shared_guardrails["jurisdiction_identification"] = jp_answers[
                "jurisdiction-profile.governing_law"
            ]
        if "jurisdiction-profile.special_zones" in jp_answers:
            zones_raw = jp_answers["jurisdiction-profile.special_zones"]
            zones = [z for z in zones_raw.split("|") if z]
            shared_guardrails["special_jurisdiction_zones"] = zones

        # Default user_role — the interview doesn't explicitly ask for role
        # in the 5-step commercial-legal flow; default to 律师.
        if not user_role:
            user_role = {"role": "律师", "lawyer_contact": ""}

        return PracticeProfile(
            tenant_id=state.tenant_id,
            plugin=state.plugin,
            identity=identity,
            user_role=user_role,
            integrations=integrations,
            escalation_matrix=escalation_matrix,
            document_style=document_style,
            shared_guardrails=shared_guardrails,
            plugin_configs={state.plugin: plugin_config} if plugin_config else {},
            temporary_mode=False,
            updated_at=None,
        )


__all__ = [
    "ColdStartInterviewOrchestrator",
    "InterviewState",
    "InterviewStep",
]
